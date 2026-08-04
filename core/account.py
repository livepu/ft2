# 账户管理模块
#
# 两个账户实现，共享相同的下单计算逻辑，差异仅在执行层：
#
#   AccountManager  — 完整账户，维护 TradeRecord + snapshots，支持事后分析
#   FastAccount     — 轻量账户，仅维护现金 + 持仓，跳过 TradeRecord/快照
#
# 架构：
#   order_percent ── 计算层 (nav → 截断 → commission → lot_size → volume) ──┐
#   order_volume  ── 验证层 (lot_size → price)                            ──┤
#                                                                           │
#   AccountManager._process_order  ← TradeRecord + snapshot + 现金更新     │
#   FastAccount._process_order     ← 现金 + 持仓更新 (无 TradeRecord)      │
#
# 设计原则：计算逻辑完全一致，FastAccount 只替换执行层，策略代码零改动。
#
#这个类是带东八时区的，逐一其他数据要时区一致
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from .storage import context
from .symbol_classifier import classify_symbol
import numpy as np


# ============================================================================
# 枚举常量 - 参考掘金SDK规范
# ============================================================================

class OrderSide:
    """买卖方向"""
    Unknown = 0
    Buy = 1      # 买入
    Sell = 2     # 卖出

    @staticmethod
    def to_str(side: int) -> str:
        """转换为字符串"""
        return 'buy' if side == OrderSide.Buy else 'sell'


class PositionEffect:
    """开平标志"""
    Unknown = 0
    Open = 1           # 开仓
    Close = 2          # 平仓
    CloseToday = 3      # 平今仓
    CloseYesterday = 4  # 平昨仓


class PositionSide:
    """持仓方向"""
    Unknown = 0
    Long = 1     # 多方向
    Short = 2    # 空方向


class OrderType:
    """委托类型"""
    Unknown = 0
    Limit = 1          # 限价委托
    Market = 2         # 市价委托


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class ContractSpec:
    """期货合约规格数据类

    [新增] 2026-08-04 期货支持 — 由策略 on_init 通过 register_contract() 注册。
    字段命名对齐掘金官网：multiplier/margin_ratio 见 get_symbols(日度交易信息)，
    price_tick/delisted_date 见 get_symbol_infos(标的基本信息)。

    Args:
        symbol: 合约代码，如 'RB2510.SHF'
        multiplier: 合约乘数（每手对应标的单位数量），如螺纹钢=10、沪深300=300
        margin_ratio: 保证金比例，如 0.08（开仓保证金 = 价格×乘数×margin_ratio×手数）
        price_tick: 最小变动价位，如螺纹钢=1.0
        exchange: 交易所：SHFE/DCE/CZCE/CFFEX/INE
        delisted_date: 最后交易日（对齐掘金 get_symbol_infos.delisted_date）
    """
    symbol: str
    multiplier: int
    margin_ratio: float
    price_tick: float = 1.0
    exchange: str = ''
    delisted_date: str = ''


@dataclass
class FuturePosition:
    """期货双向持仓（多空可共存，即锁仓）。

    [新增] 2026-08-04 重构：期货持仓从裸 dict 升级为类型化结构，
    把增/减仓、估值、保证金占用逻辑收进类方法，消除 AccountManager
    中分散的 sec_type 分支判断。

    字段对齐 gm 持仓回报模型：
        long_volume / long_volume_today / long_cost      (多头: 总/今/均价)
        short_volume / short_volume_today / short_cost   (空头: 总/今/均价)
    """

    long_volume: int = 0
    long_volume_today: int = 0
    long_cost: float = 0.0
    short_volume: int = 0
    short_volume_today: int = 0
    short_cost: float = 0.0

    @property
    def sec_type(self) -> str:
        """品种标记，供外部判断期货持仓"""
        return 'future'

    @property
    def total_volume(self) -> int:
        """多空总手数（持仓天数判定用）"""
        return self.long_volume + self.short_volume

    def is_empty(self) -> bool:
        """多空均为零"""
        return self.long_volume == 0 and self.short_volume == 0

    def open_long(self, volume: int, price: float):
        """开多：加权均价，今仓同步增加"""
        new_vol = self.long_volume + volume
        self.long_cost = ((self.long_cost * self.long_volume + price * volume) / new_vol
                          if new_vol > 0 else 0.0)
        self.long_volume = new_vol
        self.long_volume_today += volume

    def open_short(self, volume: int, price: float):
        """开空：加权均价，今仓同步增加"""
        new_vol = self.short_volume + volume
        self.short_cost = ((self.short_cost * self.short_volume + price * volume) / new_vol
                           if new_vol > 0 else 0.0)
        self.short_volume = new_vol
        self.short_volume_today += volume

    def close_long(self, volume: int, today_volume: int = None):
        """平多。today_volume=None 时按 FIFO 先平今仓（对齐掘金"期货默认平今"）；
        CloseToday 传 today_volume=volume；CloseYesterday 传 today_volume=0。"""
        if today_volume is None:
            today_volume = min(self.long_volume_today, volume)
        self.long_volume_today -= today_volume
        self.long_volume -= volume

    def close_short(self, volume: int, today_volume: int = None):
        """平空，语义同 close_long"""
        if today_volume is None:
            today_volume = min(self.short_volume_today, volume)
        self.short_volume_today -= today_volume
        self.short_volume -= volume

    def float_pnl(self, price: float, multiplier: int) -> float:
        """浮动盈亏：多头(现价-成本)、空头(成本-现价) × 乘数 × 手数"""
        pnl = 0.0
        if self.long_volume > 0:
            pnl += (price - self.long_cost) * multiplier * self.long_volume
        if self.short_volume > 0:
            pnl += (self.short_cost - price) * multiplier * self.short_volume
        return pnl

    def used_margin(self, price: float, multiplier: int, margin_ratio: float) -> float:
        """已用保证金 = (多头+空头) × 价格 × 乘数 × 保证金率"""
        return (self.long_volume + self.short_volume) * price * multiplier * margin_ratio

    def to_dict(self) -> Dict:
        """转 dict（get_position 对外输出用）"""
        return {
            'long_volume': self.long_volume,
            'long_volume_today': self.long_volume_today,
            'long_cost': round(self.long_cost, 3),
            'short_volume': self.short_volume,
            'short_volume_today': self.short_volume_today,
            'short_cost': round(self.short_cost, 3),
            'sec_type': self.sec_type,
        }


@dataclass
class PositionSnapshot:
    """持仓快照数据类"""
    symbol: str
    volume: float
    cost_price: float
    price: float
    created_at: datetime


@dataclass
class AccountSnapshot:
    """账户快照数据类"""
    cash: float
    nav: float
    created_at: datetime
    positions: Dict[str, PositionSnapshot] = field(default_factory=dict)
    # [新增] 2026-08-04 期货专用字段（仅期货持仓时非零）
    margin_used: float = 0.0   # 已用保证金（当前所有期货持仓占用）
    float_pnl: float = 0.0     # 浮动盈亏（未平仓期货按现价重估）


@dataclass
class TradeRecord:
    """成交记录数据类 - 兼容掘金规范"""
    created_at: datetime
    symbol: str
    price: float
    volume: float
    side: int                        # 买卖方向: 1=买入, 2=卖出
    position_effect: int             # 开平标志: 1=开仓, 2=平仓
    position_side: int = PositionSide.Long  # 持仓方向: 1=多, 2=空
    order_type: int = OrderType.Limit  # 委托类型: 1=限价, 2=市价
    fee: float = 0.0
    order_id: str = ''
    filled_volume: float = 0.0        # 已成交数量
    amount: float = 0.0              # 成交金额
    # [新增] 2026-05-30 信号备注，可追溯每笔交易触发原因（如 "温度计75度买入"）
    note: str = ''


# ============================================================================
# _OrderMixin — 下单共用逻辑 (AccountManager / FastAccount 共享，股票+期货)
# ============================================================================

class _OrderMixin:
    """下单共用逻辑 — AccountManager 与 FastAccount 共享（股票+期货）。

    设计原则（对齐文件头）：计算逻辑完全一致，两个账户只替换执行层。

    [订单层] order_volume/order_percent/order_value 签名统一（对齐掘金 GM），
      参数顺序/验证链/期货分叉单份维护（杜绝两端签名错位）；
      股票执行层差异走 _process_stock_order hook，
      Sell 比例持仓读取走 _get_stock_position_volume hook。

    [期货层] 纯计算/持仓操作集中于此，持仓统一用 FuturePosition 对象：

      - 合约规格：register_contract / _get_contract
      - 保证金：_calc_margin / _get_used_margin / _get_available_cash
      - 手续费：_calc_future_commission
      - 校验：FUTURE_ORDER_MATRIX / _validate_future_order
      - 执行：_process_future_order（成交记录差异走 _record_future_trade hook）
      - 持仓：_update_future_position（操作 FuturePosition）
      - 目标持仓：order_target_volume/value/percent + long/short/target

    账务模型（对齐真实期货账户，做法B）：
      cash        = 账面资金（初始 + 已实现盈亏 - 手续费），保证金不从此扣减
      margin_used = 已用保证金（遍历持仓动态计算）
      float_pnl   = 未平仓浮动盈亏（按现价重估）
      available   = cash - margin_used - frozen
      nav         = cash + float_pnl   ← 真实权益（保证金只是占用，仍在 cash 内）

    开仓：校验 available ≥ 保证金+手续费 → cash -= 手续费 → 持仓增加（margin_used 自动上升）
    平仓：cash += 平仓盈亏 - 手续费 → 持仓减少（margin_used 自动下降）
    与方案文档差异：文档"开仓扣保证金/平仓释放"会把持仓期 NAV 低估保证金，
    此处保证金不进出 cash，NAV 始终 = cash + 浮盈，持仓期权益正确。
    """

    # ─────────────────────────────────────────────
    # 订单层（签名统一对齐掘金 GM，两端共享）
    # ─────────────────────────────────────────────

    def order_volume(
        self,
        symbol: str,
        volume: int,
        side: int,
        order_type: int = OrderType.Limit,
        position_effect: int = PositionEffect.Open,
        price: float = None,
        note: str = '',
    ) -> str:
        """按指定数量委托（统一版，AccountManager/FastAccount 共享）。

        参数顺序对齐掘金 GM：order_volume/order_value/order_percent 的通用签名
        为 (symbol, 数量, side, order_type, position_effect, price)。

        期货分叉：side+position_effect 组合校验 → _process_future_order（保证金路径）；
        股票路径：执行层差异走 _process_stock_order hook。

        Args:
            symbol: 交易品种代码
            volume: 委托数量（正数）
            side: 买卖方向，OrderSide.Buy=1买入, OrderSide.Sell=2卖出
            order_type: 委托类型，OrderType.Limit=限价, OrderType.Market=市价（回测中实际无区别）
            position_effect: 开平标志，PositionEffect.Open=开仓, PositionEffect.Close=平仓
            price: 委托价格，默认为当前价格

        Returns:
            str: 订单ID（期货校验失败返回空字符串）
        """
        if not isinstance(volume, (int, float)) or volume <= 0:
            raise ValueError("Order volume must be a positive number")

        # 品种自动识别交易单位
        lot_size = self._get_lot_size(symbol)
        volume = int(volume / lot_size) * lot_size
        if volume == 0:
            raise ValueError("Volume rounded to zero by lot_size")

        if side not in (OrderSide.Buy, OrderSide.Sell):
            raise ValueError(f"Invalid side value: {side}, must be OrderSide.Buy or OrderSide.Sell")

        price = price or self._get_price(symbol)
        if price <= 0:
            raise ValueError(f"Invalid price {price} for {symbol}")

        # 期货分叉：校验 side+position_effect 组合合法性 → 保证金路径
        #   对齐掘金 GM：期货用 (side, position_effect) 表达开平方向，支持做空。
        #   Buy+Open=开多 / Sell+Close=平多 / Sell+Open=开空 / Buy+Close=平空
        if self._is_future(symbol):
            error = self._validate_future_order(symbol, volume, side, position_effect)
            if error:
                print(f"订单失败: {error}")
                return ''
            return self._process_future_order(symbol, volume, side, position_effect,
                                              order_type, price, note)

        # 股票路径：执行层由子类提供
        return self._process_stock_order(symbol, volume, side, position_effect,
                                         order_type, price, note)

    def order_percent(
        self,
        symbol: str,
        percent: float,
        side: int,
        order_type: int = OrderType.Limit,
        position_effect: int = PositionEffect.Open,
        price: float = None,
        note: str = '',
    ) -> str:
        """按账户净值比例委托（统一版，AccountManager/FastAccount 共享）。

        参数顺序对齐掘金 GM。期货按可用资金×percent 计算手数（_order_percent_future），
        股票按 nav×percent 计算金额。

        Args:
            symbol: 交易品种代码
            percent: 委托比例，0-1之间（正数）
            side: 买卖方向，OrderSide.Buy=1买入, OrderSide.Sell=2卖出
            order_type: 委托类型，OrderType.Limit=限价, OrderType.Market=市价
            position_effect: 开平标志，PositionEffect.Open=开仓, PositionEffect.Close=平仓
            price: 委托价格，默认为当前价格

        Returns:
            str: 订单ID

        Raises:
            ValueError: 比例超出范围，或计算出的数量为0
        """
        if not 0 < abs(percent) <= 1:
            raise ValueError("Percent must be between -1 and 1 (non-zero)")

        # 期货分叉：基于可用资金(而非总权益)×percent 计算手数
        if self._is_future(symbol):
            return self._order_percent_future(symbol, percent, side, position_effect,
                                              order_type, price, note)

        nav = self.get_account()['nav']

        order_amount = nav * abs(percent)

        if side == OrderSide.Buy:
            available_amount = self.cash
            if order_amount > available_amount:
                order_amount = available_amount

        price = price or self._get_price(symbol)
        if price <= 0:
            raise ValueError(f"Invalid price {price} for {symbol}")

        lot_size = self._get_lot_size(symbol)  # 品种自动识别交易单位

        if side == OrderSide.Buy:
            commission = max(
                round(order_amount * self.fee_config['commission_rate'], 2),
                self.fee_config['min_commission']
            )
            available_amount = order_amount - commission
            volume = int(available_amount / price)
            volume = int(volume / lot_size) * lot_size     # 对齐交易单位
        else:
            current_pos = self._get_stock_position_volume(symbol)   # 执行层 hook
            volume = int(current_pos * abs(percent))
            volume = int(volume / lot_size) * lot_size     # 对齐交易单位

        if volume == 0:
            raise ValueError("Calculated order volume is zero")

        return self.order_volume(symbol, volume, side, order_type, position_effect, price, note)

    def order_value(
        self,
        symbol: str,
        value: float,
        side: int,
        order_type: int = OrderType.Limit,
        position_effect: int = PositionEffect.Open,
        price: float = None,
        note: str = '',
    ) -> str:
        """按指定价值委托（统一版，对齐掘金 GM order_value）。

        计算方式（与掘金一致）：volume = value / price，向下取整到最小交易单位。

        Args:
            symbol: 交易品种代码
            value: 委托价值（金额）
            side: 买卖方向
            order_type: 委托类型
            position_effect: 开平标志
            price: 委托价格，默认为当前价格
        """
        price = price or self._get_price(symbol)
        if price <= 0:
            raise ValueError(f"Invalid price {price} for {symbol}")

        volume = int(value / price)
        lot_size = self._get_lot_size(symbol)
        volume = int(volume / lot_size) * lot_size
        if volume == 0:
            raise ValueError("Calculated order volume is zero")

        return self.order_volume(symbol, volume, side, order_type, position_effect, price, note)

    def _process_stock_order(self, symbol: str, volume: int, side: int,
                             position_effect: int, order_type: int,
                             price: float, note: str = '') -> str:
        """股票订单执行层 hook — 由子类实现。

        AccountManager：生成 order_id → _process_order（TradeRecord+快照）
        FastAccount：直接 _process_order（现金+持仓，轻量）
        """
        raise NotImplementedError("_process_stock_order 必须由子类实现")

    def _get_stock_position_volume(self, symbol: str) -> float:
        """股票持仓数量 hook — 由子类实现（Sell 比例委托用）。

        AccountManager：持仓 dict {'volume', 'cost_price'} → ['volume']
        FastAccount：持仓 float → 直接返回
        """
        raise NotImplementedError("_get_stock_position_volume 必须由子类实现")

    def register_contract(self, symbol: str, multiplier: int, margin_ratio: float,
                          price_tick: float = 1.0, exchange: str = '',
                          delisted_date: str = ''):
        """
        注册期货合约规格。期货下单前必须注册，否则拒绝成交。

        参数命名对齐掘金官网：multiplier/margin_ratio(get_symbols)、
        price_tick/delisted_date(get_symbol_infos)。策略 on_init 中调用：

            context.account.register_contract('RB2510.SHF',
                multiplier=10, margin_ratio=0.08, price_tick=1.0)

        Args:
            symbol: 合约代码，如 'RB2510.SHF'
            multiplier: 合约乘数，如螺纹钢=10、沪深300=300
            margin_ratio: 保证金比例，如 0.08
            price_tick: 最小变动价位，默认 1.0
            exchange: 交易所：SHFE/DCE/CZCE/CFFEX/INE
            delisted_date: 最后交易日
        """
        self._contracts[symbol] = ContractSpec(
            symbol=symbol,
            multiplier=multiplier,
            margin_ratio=margin_ratio,
            price_tick=price_tick,
            exchange=exchange,
            delisted_date=delisted_date,
        )

    def _is_future(self, symbol: str) -> bool:
        """判断是否期货合约（通过品种分类器后缀识别）"""
        return classify_symbol(symbol) == 'future'

    def _get_contract(self, symbol: str) -> ContractSpec:
        """获取已注册的合约规格，未注册则报错（消除各处重复的 spec None 检查）"""
        spec = self._contracts.get(symbol)
        if spec is None:
            raise ValueError(f"合约 {symbol} 未注册规格，请先调用 register_contract()")
        return spec

    def _calc_margin(self, symbol: str, price: float, volume: int) -> float:
        """计算开仓所需保证金 = 价格 × 乘数 × 保证金率 × 手数"""
        spec = self._get_contract(symbol)
        return round(price * spec.multiplier * spec.margin_ratio * volume, 2)

    def _get_used_margin(self) -> float:
        """计算当前所有期货持仓的已用保证金（动态遍历，无需手动增减）"""
        total = 0.0
        for symbol, pos in self.positions.items():
            if not isinstance(pos, FuturePosition):
                continue
            spec = self._contracts.get(symbol)
            if spec is None:
                continue
            try:
                price = self._get_price(symbol)
            except (ValueError, KeyError):
                continue
            if price <= 0:
                continue
            total += pos.used_margin(price, spec.multiplier, spec.margin_ratio)
        return round(total, 2)

    def _get_available_cash(self) -> float:
        """可用资金 = 现金 - 已用保证金 - 冻结资金（getattr 兼容无 frozen 属性的 FastAccount）"""
        return round(self.cash - self._get_used_margin() - getattr(self, 'frozen', 0.0), 2)

    def _calc_future_commission(self, symbol: str, price: float, volume: int,
                                position_effect: int) -> float:
        """计算期货手续费。

        支持两种计费模式（fee_config['per_symbol'][symbol]）：
            per_lot    按手收费：每手固定金额（期货最常见）
            per_value  按成交额收费：合约价值 × 费率
        未配置合约费率时回退到股票默认佣金逻辑。
        """
        ps = self.fee_config.get('per_symbol', {}).get(symbol)
        if ps is None:
            # 无合约级配置 → 走默认（按成交金额，兼容旧配置）
            return max(
                round(price * volume * self.fee_config['commission_rate'], 2),
                self.fee_config['min_commission']
            )

        mode = ps.get('commission_mode', 'per_value')
        is_open = position_effect == PositionEffect.Open

        if mode == 'per_lot':
            if is_open:
                rate = ps.get('open_commission_per_lot') or ps.get('commission_per_lot', 3.0)
            elif position_effect == PositionEffect.CloseToday:
                rate = ps.get('close_today_per_lot') or ps.get('close_commission_per_lot') \
                       or ps.get('commission_per_lot', 3.0)
            else:
                rate = ps.get('close_commission_per_lot') or ps.get('commission_per_lot', 3.0)
            return round(rate * volume, 2)

        # per_value 按成交额
        spec = self._get_contract(symbol)
        contract_value = price * spec.multiplier * volume
        if is_open:
            rate = ps.get('open_commission_rate', ps.get('commission_rate', 0.0001))
        elif position_effect == PositionEffect.CloseToday:
            rate = ps.get('close_today_rate') or ps.get('close_commission_rate', 0.0001)
        else:
            rate = ps.get('close_commission_rate', ps.get('commission_rate', 0.0001))
        return max(round(contract_value * rate, 2), ps.get('min_commission', 0))

    # 期货下单合法性矩阵： (side, position_effect) → (操作语义, 需持仓条件, order_business)
    #   order_business 对齐掘金 gm OrderBusiness_FUTURE_* (10-17)：
    #   10=FUTURE_BUY_OPEN, 11=FUTURE_SELL_CLOSE, 12=FUTURE_SELL_CLOSE_TODAY,
    #   13=FUTURE_SELL_CLOSE_YESTERDAY, 14=FUTURE_SELL_OPEN, 15=FUTURE_BUY_CLOSE,
    #   16=FUTURE_BUY_CLOSE_TODAY, 17=FUTURE_BUY_CLOSE_YESTERDAY
    FUTURE_ORDER_MATRIX = {
        (OrderSide.Buy,  PositionEffect.Open):           ("开多", None, 10),
        (OrderSide.Sell, PositionEffect.Close):          ("平多", 'long', 11),
        (OrderSide.Sell, PositionEffect.CloseToday):     ("平今多", 'long_today', 12),
        (OrderSide.Sell, PositionEffect.CloseYesterday): ("平昨多", 'long_yesterday', 13),
        (OrderSide.Sell, PositionEffect.Open):           ("开空", None, 14),
        (OrderSide.Buy,  PositionEffect.Close):          ("平空", 'short', 15),
        (OrderSide.Buy,  PositionEffect.CloseToday):     ("平今空", 'short_today', 16),
        (OrderSide.Buy,  PositionEffect.CloseYesterday): ("平昨空", 'short_yesterday', 17),
    }

    def _validate_future_order(self, symbol: str, volume: int, side: int,
                               position_effect: int) -> Optional[str]:
        """校验期货下单合法性，返回 None 表示通过，否则返回错误描述。

        校验项：
          1. (side, position_effect) 是否为合法组合（含做空）
          2. 合约是否已注册规格
          3. 平仓时对应方向持仓是否充足
        """
        key = (side, position_effect)
        rule = self.FUTURE_ORDER_MATRIX.get(key)
        if rule is None:
            return f"无效的期货下单组合: side={side}, position_effect={position_effect}"

        semantic, required, _ = rule

        if symbol not in self._contracts:
            return f"合约 {symbol} 未注册规格，请先 register_contract()"

        if required is None:  # 开仓无需检查持仓
            return None

        pos = self.positions.get(symbol)
        if not isinstance(pos, FuturePosition):
            return f"平仓失败: {symbol} 无期货持仓 ({semantic})"

        if required == 'long':
            total = pos.long_volume
        elif required == 'long_today':
            total = pos.long_volume_today
        elif required == 'long_yesterday':
            total = pos.long_volume - pos.long_volume_today
        elif required == 'short':
            total = pos.short_volume
        elif required == 'short_today':
            total = pos.short_volume_today
        elif required == 'short_yesterday':
            total = pos.short_volume - pos.short_volume_today
        else:
            total = 0

        if total < volume:
            return f"平仓不足: 需要 {volume} 手, 可平 {total} 手 ({semantic})"

        return None

    def _order_percent_future(self, symbol: str, percent: float, side: int,
                              position_effect: int, order_type: int,
                              price: float, note: str) -> str:
        """order_percent 的期货路径：基于可用资金 × percent 计算手数。

        对齐掘金 GM：期货 percent 基于可用资金（而非总权益），
        手数 = 可用资金×percent / (价格×乘数×保证金率)。
        """
        available = self._get_available_cash()
        order_amount = available * abs(percent)
        price = price or self._get_price(symbol)
        if price <= 0:
            raise ValueError(f"Invalid price {price} for {symbol}")
        spec = self._get_contract(symbol)
        margin_per_lot = price * spec.multiplier * spec.margin_ratio
        volume = int(order_amount / margin_per_lot)
        if volume == 0:
            raise ValueError("Calculated order volume is zero")
        return self.order_volume(symbol, volume, side, order_type, position_effect, price, note)

    def _process_future_order(self, symbol: str, volume: int, side: int,
                              position_effect: int, order_type: int,
                              price: float, note: str = '') -> int:
        """执行期货订单（核心新方法）。

        流程：
          开仓：计算保证金 → 验资 → 扣手续费 → 更新双向持仓
          平仓：结算盈亏(以持仓均价) → 扣手续费 → 更新双向持仓
        保证金不进出 cash（见类注释账务模型），margin_used 由持仓动态计算。
        成交记录通过 _record_future_trade hook 差异化解耦：
          AccountManager → TradeRecord；FastAccount → 空。
        """
        spec = self._get_contract(symbol)

        commission = self._calc_future_commission(symbol, price, volume, position_effect)

        if position_effect == PositionEffect.Open:
            # ── 开仓 ──
            margin_required = self._calc_margin(symbol, price, volume)
            available = self._get_available_cash()
            if available < margin_required + commission:
                print(f"期货开仓失败: 需要保证金 {margin_required:.0f} + 手续费 {commission:.2f}, "
                      f"可用资金 {available:.2f}")
                return 0
            self.cash = round(self.cash - commission, 2)
            self._update_future_position(symbol, volume, price, side, position_effect)
        else:
            # ── 平仓 ──
            pos = self.positions.get(symbol)
            if not isinstance(pos, FuturePosition):
                print(f"期货平仓失败: {symbol} 无持仓")
                return 0
            if side == OrderSide.Sell:
                # 平多：盈亏 = (现价 - 成本) × 乘数 × 手数
                pnl = (price - pos.long_cost) * spec.multiplier * volume
            else:
                # 平空：盈亏 = (成本 - 现价) × 乘数 × 手数
                pnl = (pos.short_cost - price) * spec.multiplier * volume
            self.cash = round(self.cash + pnl - commission, 2)
            self._update_future_position(symbol, volume, price, side, position_effect)

        # ── 成交记录 hook ──
        self._record_future_trade(
            symbol=symbol, volume=volume, side=side,
            position_effect=position_effect, order_type=order_type,
            price=price, commission=commission, multiplier=spec.multiplier, note=note,
        )
        return volume

    def _record_future_trade(self, **kwargs):
        """成交记录 hook 默认空实现；AccountManager 覆写为 TradeRecord。"""
        pass

    def _update_future_position(self, symbol: str, volume: int, price: float,
                                side: int, position_effect: int):
        """更新期货双向持仓（操作 FuturePosition，多空可共存/锁仓）。

        8 种 (side, position_effect) 组合折叠为 FuturePosition 的方法调用：
            open_long / open_short / close_long / close_short
        Close(默认平仓) 按 FIFO 先平今仓，与掘金"期货默认平今"一致；
        CloseToday / CloseYesterday 通过 today_volume 参数区分。
        """
        pos = self.positions.get(symbol)
        if not isinstance(pos, FuturePosition):
            pos = FuturePosition()

        key = (side, position_effect)

        if key == (OrderSide.Buy, PositionEffect.Open):
            pos.open_long(volume, price)                       # 开多
        elif key == (OrderSide.Sell, PositionEffect.Open):
            pos.open_short(volume, price)                      # 开空
        elif key == (OrderSide.Sell, PositionEffect.Close):
            pos.close_long(volume)                             # 平多(FIFO先平今)
        elif key == (OrderSide.Sell, PositionEffect.CloseToday):
            pos.close_long(volume, today_volume=volume)        # 平今多
        elif key == (OrderSide.Sell, PositionEffect.CloseYesterday):
            pos.close_long(volume, today_volume=0)             # 平昨多
        elif key == (OrderSide.Buy, PositionEffect.Close):
            pos.close_short(volume)                            # 平空(FIFO先平今)
        elif key == (OrderSide.Buy, PositionEffect.CloseToday):
            pos.close_short(volume, today_volume=volume)       # 平今空
        elif key == (OrderSide.Buy, PositionEffect.CloseYesterday):
            pos.close_short(volume, today_volume=0)            # 平昨空

        # 清理零持仓
        if pos.is_empty():
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = pos

    # ── 目标持仓系列（对齐掘金 GM order_target_*，用 position_side 而非 side）──

    def order_target_volume(self, symbol: str, volume: int, position_side: int,
                            order_type: int = OrderType.Market,
                            price: float = None, note: str = '') -> str:
        """调仓到目标持仓量（对齐掘金 GM order_target_volume）。

        对齐掘金：目标持仓函数用 position_side(Long/Short) 而非 side(Buy/Sell)，
        不需要传 position_effect，系统根据目标与当前持仓量自动判断开仓/平仓。

        Args:
            symbol: 合约代码
            volume: 期望的最终持仓手数（≥0）
            position_side: 持仓方向，PositionSide.Long=多仓 / PositionSide.Short=空仓
            order_type: 委托类型，默认市价
        """
        if not self._is_future(symbol):
            raise ValueError("order_target_volume 仅支持期货合约")
        if volume < 0:
            raise ValueError("目标持仓量不能为负")
        if position_side not in (PositionSide.Long, PositionSide.Short):
            raise ValueError(f"position_side 必须为 PositionSide.Long/Short, got {position_side}")

        pos = self.positions.get(symbol)
        long_vol = pos.long_volume if isinstance(pos, FuturePosition) else 0
        short_vol = pos.short_volume if isinstance(pos, FuturePosition) else 0

        if position_side == PositionSide.Long:
            # 目标多头：先平空（避免锁仓）再调整多头
            if short_vol > 0:
                self.order_volume(symbol, short_vol, OrderSide.Buy, order_type,
                                  PositionEffect.Close, price, note + ' (平空)')
            delta = volume - long_vol
            if delta > 0:
                return self.order_volume(symbol, delta, OrderSide.Buy, order_type,
                                         PositionEffect.Open, price, note)
            if delta < 0:
                return self.order_volume(symbol, -delta, OrderSide.Sell, order_type,
                                         PositionEffect.Close, price, note)
        else:
            # 目标空头：先平多（避免锁仓）再调整空头
            if long_vol > 0:
                self.order_volume(symbol, long_vol, OrderSide.Sell, order_type,
                                  PositionEffect.Close, price, note + ' (平多)')
            delta = volume - short_vol
            if delta > 0:
                return self.order_volume(symbol, delta, OrderSide.Sell, order_type,
                                         PositionEffect.Open, price, note)
            if delta < 0:
                return self.order_volume(symbol, -delta, OrderSide.Buy, order_type,
                                         PositionEffect.Close, price, note)
        return ''

    def order_target_value(self, symbol: str, value: float, position_side: int,
                           order_type: int = OrderType.Market,
                           price: float = None, note: str = '') -> str:
        """调仓到目标持仓价值（对齐掘金 GM order_target_value）。

        目标手数 = value / (价格×乘数)，再调 order_target_volume。
        """
        price = price or self._get_price(symbol)
        spec = self._get_contract(symbol)
        per_lot = price * spec.multiplier
        target_volume = int(value / per_lot) if per_lot > 0 else 0
        return self.order_target_volume(symbol, target_volume, position_side,
                                        order_type, price, note)

    def order_target_percent(self, symbol: str, percent: float, position_side: int,
                             order_type: int = OrderType.Market,
                             price: float = None, note: str = '') -> str:
        """调仓到目标持仓比例（对齐掘金 GM order_target_percent）。

        目标价值 = nav × percent → 目标手数 = 目标价值 / (价格×乘数)。
        """
        if not 0 < abs(percent) <= 1:
            raise ValueError("Percent must be between -1 and 1 (non-zero)")
        price = price or self._get_price(symbol)
        spec = self._get_contract(symbol)
        nav = self.get_account()['nav']
        target_value = nav * abs(percent)
        per_lot = price * spec.multiplier
        target_volume = int(target_value / per_lot) if per_lot > 0 else 0
        return self.order_target_volume(symbol, target_volume, position_side,
                                        order_type, price, note)

    # ── 便捷包装（方案文档接口，语义与 order_target_volume 一致）──

    def order_target_long(self, symbol: str, target_lots: int,
                          order_type: int = OrderType.Market,
                          price: float = None, note: str = '') -> str:
        """目标多头持仓 N 手（便捷方法，等价 order_target_volume(..., PositionSide.Long)）"""
        return self.order_target_volume(symbol, target_lots, PositionSide.Long,
                                        order_type, price, note)

    def order_target_short(self, symbol: str, target_lots: int,
                           order_type: int = OrderType.Market,
                           price: float = None, note: str = '') -> str:
        """目标空头持仓 N 手（便捷方法，等价 order_target_volume(..., PositionSide.Short)）"""
        return self.order_target_volume(symbol, target_lots, PositionSide.Short,
                                        order_type, price, note)

    def order_target(self, symbol: str, long_lots: int = 0, short_lots: int = 0,
                     order_type: int = OrderType.Market,
                     price: float = None, note: str = '') -> str:
        """同时设定多空目标：先调空再调多（避免锁仓）"""
        self.order_target_volume(symbol, short_lots, PositionSide.Short,
                                 order_type, price, note + ' (空)')
        return self.order_target_volume(symbol, long_lots, PositionSide.Long,
                                        order_type, price, note + ' (多)')


# ============================================================================
# 账户管理类
# ============================================================================

class AccountManager(_OrderMixin):
    """
    账户管理器 — 时间轴驱动的资金、持仓、交易记录和快照管理

    snapshots[0] 恒为初始盘前快照（Engine.run() 循环前创建），后续快照由每根 bar 驱动追加。

    AccountManager
    ├── __init__()              # 初始化：资金/持仓/trade_records/snapshots/费用配置
    │
    ├── [快照操作]              # 时间轴状态切片
    │   ├── init_snapshot()     #  创建初始盘前快照（Engine.run() 循环前调用一次）
    │   ├── take_snapshot()     #  创建快照 → snapshots.append()（纯追加，不排序/不去重）
    │   └── load_snapshot()     #  从快照恢复账户状态（资金+持仓）
    │
    ├── [交易操作]              # 策略 on_bar 中调用，成交后自动触发 take_snapshot()
    │   ├── order_percent()     #  按净值比例下单 → 金额→数量 → 调用 order_volume()
    │   ├── order_volume()      #  按指定数量下单 → 调用 _process_order()
    │   ├── _process_order()    #  [私有] 费用计算 → 验资/验券 → 扣款/收款 → 记录 TradeRecord
    │   └── _update_position()  #  [私有] 均价法更新持仓（买入加权均价，卖出扣减数量）
    │
    ├── [查询操作]              # 策略中获取实时状态，优先从最新快照反查
    │   ├── get_account()       #  查询账户现金+净值（从 snapshots 反查 ≤ query_time 的快照）
    │   ├── get_position()      #  查询持仓（单品种返回 dict，全部返回 Dict[str,dict]）
    │   └── get_orders()        #  查询成交记录（支持时间区间过滤）
    │
    └── [底层支撑]
        ├── _get_lot_size()    #  [私有] 品种自动识别交易单位 (stock/etf→100, index→1, 其他→0.1)
        └── _get_price()       #  [私有] 从 context 缓存获取当前价格（多频率逐次查找）
    """
    
    FREQ_ORDER = ['1m', '60s', '5m', '300s', '15m', '900s', '30m', '1800s', '60m', '3600s', '1d']

    def __init__(
        self,
        init_cash: float = 1e6,
        fee_config: Dict = None,
    ):
        """
        初始化账户管理器
        
        Args:
            init_cash: 初始资金，默认100万
            fee_config: 费用配置，包含佣金率、印花税率、最低佣金
        """
        self.cash = round(init_cash, 2)
        self.positions: Dict[str, Dict] = {}
        self.trade_records: List[TradeRecord] = []
        self.snapshots: List[AccountSnapshot] = []
        self.fee_config = fee_config or {
            'commission_rate': 0.0,
            'stamp_tax_rate': 0.0,
            'min_commission': 0.0,
        }
        # [新增] 2026-06-23 代码→品种名称映射，由 Engine._drive_timeline 注入
        #   _process_order 创建 TradeRecord 时自动查表填充 symbol_name，策略层无感知
        self._symbol_names: Dict[str, str] = {}
        # [新增] 2026-08-04 期货支持
        self._contracts: Dict[str, ContractSpec] = {}   # 合约规格注册表 (symbol → ContractSpec)
        self.frozen: float = 0.0                        # 冻结资金（为条件单预留，当前恒为 0）

    # ------------------------------------------------------------------------
    # 快照操作
    # ------------------------------------------------------------------------

    def init_snapshot(self, created_at: datetime):
        """
        创建初始盘前快照（仅在回测开始前调用一次）
        
        snapshots[0] 语义固定：表示首笔交易前的账户状态（初始资金，零持仓）
        时间锚定在首根 bar 的前一日，确保基准日期独立于任何交易日
        
        Args:
            created_at: 快照时间，由引擎传入（通常 = 首根 bar 的 eob - 1 天）
        """
        snapshot = AccountSnapshot(
            cash=self.cash,
            nav=self.cash,
            created_at=created_at,
            positions={}
        )
        self.snapshots.append(snapshot)

    def take_snapshot(self, created_at: datetime = None) -> AccountSnapshot:
        """
        创建账户快照
        
        Args:
            created_at: 快照时间，默认为当前上下文时间
            
        Returns:
            AccountSnapshot: 账户快照对象
        """
        if created_at is None:
            created_at = context.now

        pos_snapshots = {}
        total_assets = self.cash          # 股票部分累加市值
        total_float_pnl = 0.0             # [新增] 2026-08-04 期货浮动盈亏

        for symbol, pos in self.positions.items():
            try:
                price = self._get_price(symbol)
            except (ValueError, KeyError):
                continue
            if price <= 0:
                continue

            # [新增] 2026-08-04 期货：NAV 只记浮动盈亏（保证金仍占用 cash 内）
            if isinstance(pos, FuturePosition):
                spec = self._contracts.get(symbol)
                if spec is None:
                    continue
                total_float_pnl += pos.float_pnl(price, spec.multiplier)
                pos_snap = PositionSnapshot(
                    symbol=symbol,
                    volume=pos.total_volume,   # 多空总量（持仓天数判定用）
                    cost_price=0.0,
                    price=price,
                    created_at=created_at,
                )
                pos_snapshots[symbol] = pos_snap
                continue

            pos_snap = PositionSnapshot(
                symbol=symbol,
                volume=pos['volume'],
                cost_price=round(pos['cost_price'], 3),
                price=price,
                created_at=created_at
            )
            pos_snapshots[symbol] = pos_snap
            total_assets += pos['volume'] * price

        total_assets = round(total_assets + total_float_pnl, 2)
        snapshot = AccountSnapshot(
            cash=self.cash,
            nav=total_assets,
            created_at=created_at,
            positions=pos_snapshots,
            margin_used=self._get_used_margin(),
            float_pnl=round(total_float_pnl, 2),
        )
        self.snapshots.append(snapshot)

        return snapshot

    def load_snapshot(self, snapshot: AccountSnapshot):
        """
        从快照恢复账户状态
        
        Args:
            snapshot: 账户快照对象
        """
        self.cash = round(snapshot.cash, 2)
        self.positions = {
            sym: {'volume': pos.volume, 'cost_price': round(pos.cost_price, 3)}
            for sym, pos in snapshot.positions.items()
        }
        self.current_time = snapshot.created_at

    # ------------------------------------------------------------------------
    # 交易操作
    # ------------------------------------------------------------------------

    # [重构] 2026-08-04 下单方法移入 _OrderMixin（register_contract/order_volume/
    #   order_percent/order_value 单份维护，杜绝两端签名错位）。
    #   此处仅覆写股票执行层 hook，期货路径由 mixin 统一提供。

    def _process_stock_order(self, symbol: str, volume: int, side: int,
                             position_effect: int, order_type: int,
                             price: float, note: str = '') -> str:
        """[覆写] 股票订单执行：生成 order_id → _process_order（TradeRecord+快照）"""
        order_id = f"order_{len(self.trade_records)+1}"
        self._process_order(symbol, volume, side, position_effect, order_type,
                            price, order_id, note)
        return order_id

    def _get_stock_position_volume(self, symbol: str) -> float:
        """[覆写] 股票持仓数量（AccountManager 持仓为 dict {'volume','cost_price'}）"""
        pos = self.positions.get(symbol)
        return pos['volume'] if isinstance(pos, dict) else 0

    def _process_order(
        self,
        symbol: str,
        volume: int,
        side: int,
        position_effect: int,
        order_type: int,
        price: float,
        order_id: str,
        note: str = '',
    ) -> int:
        """
        处理订单执行

        Args:
            symbol: 交易品种代码
            volume: 委托数量（正数）
            side: 买卖方向，OrderSide.Buy=1, OrderSide.Sell=2
            position_effect: 开平标志
            order_type: 委托类型
            price: 委托价格
            order_id: 订单ID

        Returns:
            int: 实际成交数量，0表示未成交
        """
        commission = max(
            round(price * volume * self.fee_config['commission_rate'], 2),
            self.fee_config['min_commission']
        )
        stamp_tax = round(price * volume * self.fee_config['stamp_tax_rate'], 2) if side == OrderSide.Sell else 0
        total_fee = round(commission + stamp_tax, 2)

        if side == OrderSide.Buy:
            total_cost = round(volume * price + total_fee, 2)
            if self.cash < total_cost:
                print(f"订单 {order_id} 买入 {symbol} 失败，资金不足。需要 {total_cost}，可用资金 {self.cash}")
                return 0
            self.cash = round(self.cash - total_cost, 2)
            self._update_position(symbol, volume, price, total_fee, OrderSide.Buy)
        else:
            current_pos = self.positions.get(symbol, {'volume': 0})
            if current_pos['volume'] < volume:
                print(f"订单 {order_id} 卖出 {symbol} 失败，持仓不足。需要 {volume}，当前持仓 {current_pos['volume']}")
                return 0
            self.cash = round(self.cash + volume * price - total_fee, 2)
            self._update_position(symbol, volume, price, total_fee, OrderSide.Sell)

        self.trade_records.append(TradeRecord(
            created_at=context.now,
            symbol=symbol,
            price=price,
            volume=volume,
            side=side,
            position_effect=position_effect,
            position_side=PositionSide.Long,
            order_type=order_type,
            fee=total_fee,
            order_id=order_id,
            filled_volume=volume,
            amount=price * volume,
            note=note,
        ))
        return volume

    def _update_position(self, symbol: str, volume: int, price: float, total_fee: float, side: int):
        """
        更新持仓信息

        Args:
            symbol: 交易品种代码
            volume: 成交数量（正数）
            price: 成交价格
            total_fee: 总费用
            side: 买卖方向，OrderSide.Buy=1, OrderSide.Sell=2
        """
        pos = self.positions.get(symbol, {'volume': 0, 'cost_price': 0})
        if side == OrderSide.Buy:
            new_volume = pos['volume'] + volume
            total_purchase_cost = pos['volume'] * pos['cost_price'] + volume * price + total_fee
            new_cost = total_purchase_cost / new_volume
            pos['volume'] = new_volume
            pos['cost_price'] = round(new_cost, 3)
        else:
            pos['volume'] -= volume
            if pos['volume'] == 0:
                del self.positions[symbol]
                return
        self.positions[symbol] = pos

    # [新增] 2026-08-04 期货支持：核心逻辑见 _OrderMixin（AccountManager/FastAccount 共享）
    #   账务模型：保证金不进出 cash，NAV = cash + 浮盈，详见 mixin 注释。
    # [重构] 2026-08-04 期货方法已移入 _OrderMixin，此处仅覆写成交记录 hook。

    def _record_future_trade(self, symbol: str, volume: int, side: int,
                             position_effect: int, order_type: int,
                             price: float, commission: float,
                             multiplier: int, note: str = ''):
        """[覆写] 期货成交记录 → TradeRecord（FastAccount 走 mixin 默认空实现）"""
        order_id = f"order_{len(self.trade_records)+1}"
        self.trade_records.append(TradeRecord(
            created_at=context.now,
            symbol=symbol,
            price=price,
            volume=volume,
            side=side,
            position_effect=position_effect,
            position_side=PositionSide.Long if side == OrderSide.Buy else PositionSide.Short,
            order_type=order_type,
            fee=commission,
            order_id=order_id,
            filled_volume=volume,
            amount=round(price * multiplier * volume, 2),
            note=note,
        ))

    # ------------------------------------------------------------------------
    # 查询操作
    # ------------------------------------------------------------------------

    def get_account(self, query_time: datetime = None) -> Dict:
        """
        获取账户信息
        
        Args:
            query_time: 查询时间，默认为当前上下文时间
            
        Returns:
            Dict: 包含cash、nav、created_at的字典
        """
        query_time = context.now if query_time is None else query_time

        if not self.snapshots:
            return self._account_dict(self.cash, self.cash, query_time,
                                      margin_used=self._get_used_margin())

        snapshot = next(
            (s for s in reversed(self.snapshots) if s.created_at <= query_time),
            None
        )

        if snapshot is None:
            return self._account_dict(self.cash, self.cash, query_time,
                                      margin_used=self._get_used_margin())

        margin_used = getattr(snapshot, 'margin_used', 0.0)
        float_pnl = getattr(snapshot, 'float_pnl', 0.0)
        return self._account_dict(snapshot.cash, snapshot.nav, snapshot.created_at,
                                  margin_used=margin_used, float_pnl=float_pnl)

    def _account_dict(self, cash: float, nav: float, created_at: datetime,
                      margin_used: float = 0.0, float_pnl: float = 0.0) -> Dict:
        """构造 get_account 返回字典（三分支共用，消除重复）。

        字段：cash/nav/created_at + 期货扩展(available/margin_used/float_pnl/risk_ratio)
        """
        return {
            'cash': cash,
            'nav': nav,
            'created_at': created_at,
            # [新增] 2026-08-04 期货字段：可用资金/已用保证金/浮动盈亏/风险度
            'available': round(cash - margin_used - self.frozen, 2),
            'margin_used': margin_used,
            'float_pnl': float_pnl,
            'risk_ratio': round(margin_used / nav, 4) if nav > 0 else 0.0,
        }

    def get_position(self, symbol: str = None) -> Dict:
        """
        获取持仓信息
        
        Args:
            symbol: 交易品种代码，为None时返回所有持仓
            
        Returns:
            Dict: 单个品种返回{'volume', 'cost_price'}，所有品种返回字典
        """
        if not self.snapshots:
            positions = self.positions.copy()
        else:
            last_snapshot = self.snapshots[-1]
            positions = {
                sym: {'volume': pos.volume, 'cost_price': pos.cost_price}
                for sym, pos in last_snapshot.positions.items()
            }

        if symbol:
            # [新增] 2026-08-04 期货：返回多空分列（多空可共存）
            if self._is_future(symbol):
                live = self.positions.get(symbol)
                if isinstance(live, FuturePosition):
                    return live.to_dict()
                return {'long_volume': 0, 'long_volume_today': 0, 'long_cost': 0.0,
                        'short_volume': 0, 'short_volume_today': 0, 'short_cost': 0.0,
                        'sec_type': 'future'}
            pos = positions.get(symbol, {'volume': 0, 'cost_price': 0})
            pos['cost_price'] = round(pos['cost_price'], 3)
            return pos

        # [新增] 2026-08-04 期货持仓合入全量结果（多空分列）
        for sym in list(positions.keys()):
            if self._is_future(sym):
                live = self.positions.get(sym)
                positions[sym] = live.to_dict() if isinstance(live, FuturePosition) else {
                    'long_volume': 0, 'short_volume': 0, 'long_cost': 0.0,
                    'short_cost': 0.0, 'sec_type': 'future'}
        for pos in positions.values():
            if pos.get('sec_type') != 'future':
                pos['cost_price'] = round(pos.get('cost_price', 0), 3)
        return positions

    def get_orders(
        self,
        start_query_time: datetime = None,
        end_query_time: datetime = None
    ) -> List[TradeRecord]:
        """
        获取成交记录
        
        Args:
            start_query_time: 查询起始时间
            end_query_time: 查询结束时间
            
        Returns:
            List[TradeRecord]: 成交记录列表
        """
        trades = self.trade_records

        if start_query_time:
            trades = [t for t in trades if t.created_at >= start_query_time]
        if end_query_time:
            trades = [t for t in trades if t.created_at <= end_query_time]

        return trades.copy()

    # ------------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------------

    def _get_lot_size(self, symbol: str) -> float:
        """
        根据品种类型返回默认交易单位

        fee_config.lot_size 显式配置优先，否则自动识别：
            stock/etf → 100（整手）
            index     → 1（无约束）
            其他       → 0.1（保留一位小数）
        """
        if self.fee_config.get('lot_size') is not None:
            return self.fee_config['lot_size']
        sec_type = classify_symbol(symbol)
        if sec_type in ('stock', 'etf'):
            return 100
        if sec_type == 'index':
            return 1
        if sec_type == 'future':    # [新增] 2026-08-04 期货 1 手 = 1 张
            return 1
        return 0.1

    def _get_price(self, symbol: str) -> float:
        """
        获取品种当前价格
        
        Args:
            symbol: 交易品种代码
            
        Returns:
            float: 当前价格
            
        Raises:
            ValueError: 品种未订阅或无法获取有效价格
        """
        action_time = context.now
        subscribed_freqs = {freq for (s, freq) in context._subscribed if s == symbol}
        if not subscribed_freqs:
            raise ValueError(f"品种 {symbol} 未订阅任何频率数据")

        frequencies = [f for f in self.FREQ_ORDER if f in subscribed_freqs]
        # [修复] 2026-05-30 补充不在 FREQ_ORDER 中的自定义频率（如 m10）
        frequencies += [f for f in subscribed_freqs if f not in self.FREQ_ORDER]

        for freq in frequencies:
            try:
                raw_data = context.data(
                    symbol=symbol,
                    frequency=freq,
                    count=3,
                    fields='close,eob',
                )

                if isinstance(raw_data, pd.DataFrame):
                    data = raw_data.to_dict('records')
                else:
                    data = raw_data

                for d in reversed(data):
                    if d['eob'] <= action_time:
                        price = d['close']
                        if not isinstance(price, (float, int)) or price <= 0:
                            raise ValueError(f"Invalid price {price} for {symbol} at {action_time}")
                        return float(price)
            except Exception:
                continue

        raise ValueError(f"No valid price found for {symbol} at {action_time}")

    # [新增] 2026-06-03 重置账户状态，支持连续多次回测（walk-forward 等场景）
    def reset(self, init_cash: float = None):
        """
        重置账户到初始状态
        
        Args:
            init_cash: 可选，重置后的初始资金。不传则保持当前现金不变。
        """
        if init_cash is not None:
            self.cash = round(init_cash, 2)
        self.positions.clear()
        self.trade_records.clear()
        self.snapshots.clear()


# ============================================================================
# FastAccount — 轻量快速账户 (fast 模式专用)
# ============================================================================

class FastAccount(_OrderMixin):
    """轻量账户：不走快照/TradeRecord，通过 context.data() 从缓存获取价格。

    在 run_fast() 时替换 Engine.account，策略统一用 ctx.account 下单，
    接口完全兼容 AccountManager (order_percent / order_volume / get_position)。

    fee_config 从 AccountManager 继承，与 full 模式共享同一费源。
    [新增] 2026-08-04 期货支持：核心逻辑复用 _OrderMixin，
      持仓 FuturePosition 对象，账务与 AccountManager 完全一致（NAV=cash+浮盈）。
    """

    __slots__ = ('cash', 'positions', 'fee_config', 'daily_assets', '_latest_prices',
                 '_contracts')

    FREQ_ORDER = ['1m', '60s', '5m', '300s', '15m', '900s',
                  '30m', '1800s', '60m', '3600s', '1d']

    def __init__(self, cash: float = 1e6, fee_config: Dict = None):
        self.cash = float(cash)
        self.positions: Dict[str, float] = {}  # {symbol: shares}
        self.fee_config = fee_config or {
            'commission_rate': 0.0,
            'stamp_tax_rate': 0.0,
            'min_commission': 0.0,
        }
        self.daily_assets: Dict = {}  # {datetime.date: nav}
        self._latest_prices: Dict[str, float] = {}  # [优化] 2026-06-21 缓存 bar 价格，避免 _get_price
        self._contracts: Dict[str, ContractSpec] = {}  # [新增] 2026-08-04 合约注册表

    # ── 价格查询 (读 context.data 缓存) ──

    def _get_price(self, symbol: str) -> float:
        """从缓存获取当前价格。优先读 _latest_prices，兜底走 context.data。"""
        # [优化] 2026-06-21 优先读引擎注入的 bar 价格缓存，跳过 DataFrame 构造
        cached = self._latest_prices.get(symbol)
        if cached is not None and cached > 0:
            return cached

        action_time = context.now
        subscribed_freqs = {freq for (s, freq) in context._subscribed if s == symbol}
        if not subscribed_freqs:
            raise ValueError(f"品种 {symbol} 未订阅任何频率数据")

        frequencies = [f for f in self.FREQ_ORDER if f in subscribed_freqs]
        frequencies += [f for f in subscribed_freqs if f not in self.FREQ_ORDER]

        for freq in frequencies:
            try:
                raw_data = context.data(symbol=symbol, frequency=freq,
                                        count=3, fields='close,eob')
                if isinstance(raw_data, pd.DataFrame):
                    data = raw_data.to_dict('records')
                else:
                    data = raw_data
                for d in reversed(data):
                    if d['eob'] <= action_time:
                        price = d['close']
                        if isinstance(price, (float, int, np.integer)) and price > 0:
                            return float(price)
            except Exception:
                continue
        return 0.0

    # ── 价格缓存 ([优化] 2026-06-21 消除 mark/get_account 中的 _get_price 开销) ──

    def update_prices(self, bars: List[Dict]):
        """引擎注入当前 bar 价格，mark()/get_account() 优先读缓存。

        由 _drive_timeline 在每个 bar 前调用，避免 mark() 和 get_account()
        反复通过 context.data() → DataFrame 查价（约 1.2ms/次/品种）。
        """
        for b in bars:
            close = b.get('close')
            if close is not None and close > 0:
                self._latest_prices[b['symbol']] = float(close)

    # ── 交易单位 ──

    def _get_lot_size(self, symbol: str) -> float:
        """获取交易单位，对齐 AccountManager._get_lot_size"""
        if self.fee_config.get('lot_size') is not None:
            return self.fee_config['lot_size']
        sec_type = classify_symbol(symbol)
        if sec_type in ('stock', 'etf'):
            return 100
        if sec_type == 'index':
            return 1
        if sec_type == 'future':    # [新增] 2026-08-04 期货 1 手 = 1 张
            return 1
        return 0.1

    def init_snapshot(self, date):
        """[修复] 2026-06-21 初始化净值记录，对齐 AccountManager.init_snapshot"""
        self.mark(date=date)

    # ── 净值记录 ──

    def mark(self, date=None):
        """记录当日净值到 daily_assets。优先读 _latest_prices 缓存，兜底 _get_price。

        [新增] 2026-08-04 期货持仓按浮盈计入 NAV（对齐 AccountManager：NAV = cash + 浮盈）。
        """
        if date is None:
            date = context.now.date()
        nav = self.cash
        float_pnl = 0.0
        for sym, shares in self.positions.items():
            # [优化] 2026-06-21 优先读引擎注入的 bar 价格缓存
            price = self._latest_prices.get(sym)
            if price is None:
                try:
                    price = self._get_price(sym)
                except (ValueError, KeyError):
                    pass
            if price:
                if isinstance(shares, FuturePosition):
                    spec = self._contracts.get(sym)
                    if spec is None:
                        continue
                    float_pnl += shares.float_pnl(price, spec.multiplier)
                else:
                    nav += shares * price
        nav += float_pnl
        self.daily_assets[date] = round(nav, 2)

    # ── 下单 (逻辑由 _OrderMixin 统一提供，此处仅覆写股票执行层 hook) ──
    #   [重构] 2026-08-04 order_percent/order_volume/order_value 及期货分叉
    #   移入 _OrderMixin，签名/验证链单份维护；差异仅在执行层：
    #     AccountManager → _process_order (TradeRecord + 快照)
    #     FastAccount    → _process_order (现金 + 持仓, 无 TradeRecord/快照)

    def _process_stock_order(self, symbol: str, volume: int, side: int,
                             position_effect: int, order_type: int,
                             price: float, note: str = '') -> str:
        """[覆写] 股票订单执行：轻量路径（现金+持仓，无 TradeRecord/快照）"""
        self._process_order(symbol, volume, side, price)
        return ''

    def _get_stock_position_volume(self, symbol: str) -> float:
        """[覆写] 股票持仓数量（FastAccount 持仓为 float 结构）"""
        sh = self.positions.get(symbol, 0)
        return sh if not isinstance(sh, FuturePosition) else 0

    def _process_order(self, symbol: str, volume: int, side: int,
                       price: float) -> int:
        """执行订单 — 现金+持仓更新，对齐 AccountManager._process_order 现金计算。

        与 AccountManager._process_order 的区别：不生成 TradeRecord，不触发快照。
        """
        fee = self.fee_config

        commission = max(
            round(price * volume * fee['commission_rate'], 2),
            fee['min_commission']
        )
        stamp_tax = round(price * volume * fee['stamp_tax_rate'], 2) if side == OrderSide.Sell else 0
        total_fee = round(commission + stamp_tax, 2)

        if side == OrderSide.Buy:
            total_cost = round(volume * price + total_fee, 2)
            if self.cash < total_cost:
                print(f"FastAccount 买入 {symbol} 失败，资金不足。需要 {total_cost}，可用资金 {self.cash}")
                return 0
            self.cash = round(self.cash - total_cost, 2)
            self.positions[symbol] = self.positions.get(symbol, 0) + volume
        else:
            current_shares = self.positions.get(symbol, 0)
            if current_shares < volume:
                print(f"FastAccount 卖出 {symbol} 失败，持仓不足。需要 {volume}，当前持仓 {current_shares}")
                return 0
            self.cash = round(self.cash + volume * price - total_fee, 2)
            self.positions[symbol] -= volume
            if abs(self.positions[symbol]) < 1e-9:
                del self.positions[symbol]

        return volume

    # ── 查询 (兼容 AccountManager 接口) ──

    def get_position(self, symbol: str = None):
        """返回持仓信息。

        [新增] 2026-08-04 期货返回多空分列（FuturePosition.to_dict），多空可共存。
        """
        if symbol:
            if self._is_future(symbol):
                pos = self.positions.get(symbol)
                if isinstance(pos, FuturePosition):
                    return pos.to_dict()
                return {'long_volume': 0, 'long_volume_today': 0, 'long_cost': 0.0,
                        'short_volume': 0, 'short_volume_today': 0, 'short_cost': 0.0,
                        'sec_type': 'future'}
            shares = self.positions.get(symbol, 0)
            return {'volume': shares, 'cost_price': 0}
        result = {}
        for sym, sh in self.positions.items():
            if isinstance(sh, FuturePosition):
                result[sym] = sh.to_dict()
            else:
                result[sym] = {'volume': sh, 'cost_price': 0}
        return result

    def get_account(self, query_time=None):
        """返回账户概览。nav = cash + 股票市值 + 期货浮盈，优先读 _latest_prices 缓存。"""
        nav = self.cash
        float_pnl = 0.0
        for sym, shares in self.positions.items():
            price = self._latest_prices.get(sym)
            if price is None:
                try:
                    price = self._get_price(sym)
                except (ValueError, KeyError):
                    pass
            if price:
                if isinstance(shares, FuturePosition):
                    spec = self._contracts.get(sym)
                    if spec is None:
                        continue
                    float_pnl += shares.float_pnl(price, spec.multiplier)
                else:
                    nav += shares * price
        return {'cash': self.cash, 'nav': round(nav + float_pnl, 2)}


# ============================================================================
# 内置基准策略
# ============================================================================

class BenchHolder:
    """
    买入持有基准策略 — 首 bar 全仓买入第一只标的，后续持有不动

    设计说明（与 GM 的差异）：
        GM 的基准对比是通过终端 GUI 选一个指数（如沪深300），后台 RPC 拉该指数的
        收益率序列来画线。Python SDK 不暴露 get_benchmark_return() API。
        
        本框架的基准是一个真实的策略（BenchHolder），走和主策略完全相同的引擎、
        数据和账户通道。好处：
        1. 基准和策略数据源一致，不存在因来源不同导致的偏差
        2. 基准可任意定制（不限于预设指数，可以是任何自定义策略）
        3. 对比链路完全可编程，不依赖 GUI

    [重构] 2026-06-09 改用 context.account 访问活跃 Engine 的账户（不再依赖全局 account）

    用法:
        bench_engine.run(BenchHolder, start_time, end_time)
        bench_analyzer = AccountAnalyzer(bench_engine.account)
        strategy_analyzer.set_benchmark(bench_analyzer.daily_assets, '国证A指')
    """
    
    def on_bar(self, context, bars):
        if context.account.get_position():
            return
        context.account.order_percent(bars[0]['symbol'], 1.0, OrderSide.Buy, note='基准买入持有')


# [重构] 2026-06-09 移除全局 account 实例
#   旧架构：全局 account 被 Engine.run() 期间使用，需手动 account.reset()
#   新架构：每 Engine 实例内置独立 AccountManager，通过 context.account 委托访问
#   全局实例已无使用场景，移除以避免误用
