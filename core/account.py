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


# [对齐掘金 2026-08-04] 模块级常量别名（gm 风格：OrderSide_Buy / PositionEffect_CloseToday）
#   与上述类属性数值完全等价，供掘金风格策略代码直接引用，同时保留 OrderSide.Buy 类属性用法。
OrderSide_Buy = OrderSide.Buy
OrderSide_Sell = OrderSide.Sell
OrderType_Limit = OrderType.Limit
OrderType_Market = OrderType.Market
PositionEffect_Open = PositionEffect.Open
PositionEffect_Close = PositionEffect.Close
PositionEffect_CloseToday = PositionEffect.CloseToday
PositionEffect_CloseYesterday = PositionEffect.CloseYesterday
PositionSide_Long = PositionSide.Long
PositionSide_Short = PositionSide.Short


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
        margin_ratio_near: [参考掘金 marginfloat_ratio2] 临近交割(距最后交易日≤2交易日)保证金上浮率，
                           None 表示不分级（恒用 margin_ratio）
        price_tick: 最小变动价位，如螺纹钢=1.0
        exchange: 交易所：SHFE/DCE/CZCE/CFFEX/INE
        delisted_date: 最后交易日（对齐掘金 get_symbol_infos.delisted_date）
    """
    symbol: str
    multiplier: int
    margin_ratio: float
    margin_ratio_near: float = None   # [参考掘金] 临近交割保证金上浮率（分级保证金）
    price_tick: float = 1.0
    exchange: str = ''
    delisted_date: str = ''

    def effective_margin_ratio(self, remaining_days: int = None) -> float:
        """按剩余交易日动态选择保证金率（对齐掘金 marginfloat_ratio1/2 分级思想）。

        remaining_days ≤ 2 且配置了 margin_ratio_near → 上浮费率；否则基准费率。
        remaining_days=None（未配置交割日）时恒用基准费率。
        """
        if self.margin_ratio_near and remaining_days is not None and remaining_days <= 2:
            return self.margin_ratio_near
        return self.margin_ratio


@dataclass
class Position:
    """统一持仓对象 — 对齐掘金 gm Position（股票/期货通用）

    [新增] 2026-08-04 深度B重构：股票/期货统一持仓表 (symbol, side) → Position。
    字段与 gm Position 回报一致：symbol/side/volume/volume_today/vwap/fpnl
      - 股票：side=PositionSide.Long（恒多头），multiplier=1
      - 期货：side=Long/Short，multiplier=合约乘数
    vwap = 加权开仓均价（对齐 Position.vwap，不含手续费）
    """

    symbol: str
    side: int
    volume: int = 0
    volume_today: int = 0     # 今仓（期货平今依据；股票=当日买入）
    vwap: float = 0.0         # 加权开仓均价（不含手续费）

    def is_empty(self) -> bool:
        """持仓为零"""
        return self.volume == 0

    def open(self, volume: int, price: float):
        """开仓：加权 vwap，今仓同步增加"""
        new_vol = self.volume + volume
        self.vwap = ((self.vwap * self.volume + price * volume) / new_vol
                     if new_vol > 0 else 0.0)
        self.volume = new_vol
        self.volume_today += volume

    def close(self, volume: int, today_volume: int = None):
        """平仓。today_volume=None → FIFO 先平今仓（对齐掘金"期货默认平今"）；
        CloseToday 传 today_volume=volume；CloseYesterday 传 today_volume=0。"""
        if today_volume is None:
            today_volume = min(self.volume_today, volume)
        self.volume_today -= today_volume
        self.volume -= volume

    def fpnl(self, price: float, multiplier: int = 1) -> float:
        """浮动盈亏：多头 (price-vwap)、空头 (vwap-price) × 乘数 × 手数（对齐 Position.fpnl）"""
        if self.side == PositionSide.Long:
            return (price - self.vwap) * multiplier * self.volume
        return (self.vwap - price) * multiplier * self.volume

    def used_bail(self, price: float, multiplier: int, margin_ratio: float) -> float:
        """已用保证金 = 持仓市值 × 保证金率（股票调用方传 margin_ratio=0 即无保证金）"""
        return self.volume * price * multiplier * margin_ratio

    def to_dict(self) -> Dict:
        """转 dict（get_position 对外输出，键名对齐 gm Position 回报）"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'volume': self.volume,
            'volume_today': self.volume_today,
            'vwap': round(self.vwap, 3),
        }


@dataclass
class PositionSnapshot:
    """持仓快照数据类（字段对齐掘金 Position：symbol/side/volume/volume_today/vwap）"""
    symbol: str
    side: int = PositionSide.Long
    volume: float = 0.0
    volume_today: float = 0.0
    vwap: float = 0.0
    price: float = 0.0
    created_at: datetime = None


@dataclass
class AccountSnapshot:
    """账户快照数据类（字段对齐掘金 Cash：balance/nav/available/used_bail/fpnl）"""
    balance: float       # 账面资金（对齐 Cash.balance）
    nav: float
    created_at: datetime
    positions: Dict[str, PositionSnapshot] = field(default_factory=dict)
    # [新增] 2026-08-04 期货专用字段（仅期货持仓时非零）
    used_bail: float = 0.0   # 已用保证金（对齐 Cash.used_bail，当前所有期货持仓占用）
    fpnl: float = 0.0        # 浮动盈亏（对齐 Cash.fpnl，未平仓期货按现价重估）


@dataclass
class TradeRecord:
    """成交记录数据类 - 字段命名对齐掘金 Order 回报（filled_volume/filled_amount/filled_commission）"""
    created_at: datetime
    symbol: str
    price: float
    volume: float
    side: int                        # 买卖方向: 1=买入, 2=卖出
    position_effect: int             # 开平标志: 1=开仓, 2=平仓
    position_side: int = PositionSide.Long  # 持仓方向: 1=多, 2=空
    order_type: int = OrderType.Limit  # 委托类型: 1=限价, 2=市价
    filled_commission: float = 0.0   # 成交手续费（对齐 Order.filled_commission）
    order_id: str = ''
    filled_volume: float = 0.0        # 已成交数量（对齐 Order.filled_volume）
    filled_amount: float = 0.0        # 成交金额（对齐 Order.filled_amount）
    multiplier: int = 1               # [新增] 2026-08-04 合约乘数（股票=1，期货=合约乘数，analyzer 盈亏用）
    # [新增] 2026-08-04 实际保证金率：命名对齐 gm get_symbols 字段 margin_ratio；
    #   股票=1，期货=开仓时生效比率（含 margin_ratio_near 分级）。内部计算字段
    #   （analyzer 保证金口径收益率），gm Order 回报无此字段，不进 to_dict()
    margin_ratio: float = 1.0
    # [新增] 2026-05-30 信号备注，可追溯每笔交易触发原因（如 "温度计75度买入"）
    note: str = ''

    def to_dict(self) -> Dict:
        """转 dict — [重构] 2026-08-04 对齐 gm get_orders 返回 List[Dict]。

        字段命名对齐 gm Order（DictLikeOrder._fields）：
        volume=委托量, price=委托价, filled_vwap=已成均价（ft2 单笔全成=price），
        status 不输出（ft2 全成交，无委托状态机）。
        """
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side,
            'position_effect': self.position_effect,
            'position_side': self.position_side,
            'order_type': self.order_type,
            'volume': self.volume,
            'price': self.price,
            'filled_volume': self.filled_volume,
            'filled_vwap': self.price,
            'filled_amount': self.filled_amount,
            'filled_commission': self.filled_commission,
            'created_at': self.created_at,
            # ft2 扩展字段
            'multiplier': self.multiplier,
            'note': self.note,
        }


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

    [期货层] 纯计算/持仓操作集中于此，持仓统一用 Position 对象（(symbol, side) 表）：

      - 合约规格：register_contract / _get_contract
      - 保证金：_calc_margin / _get_used_bail / _get_available_cash（含按到期日分级）
      - 手续费：_calc_future_commission
      - 校验：FUTURE_ORDER_MATRIX / _validate_future_order
      - 执行：_process_future_order（成交记录差异走 _record_future_trade hook）
      - 持仓：_update_future_position（操作单方向 Position）
      - 目标持仓：order_target_volume/value/percent + long/short/target

    账务模型（对齐真实期货账户 + 掘金 Cash 字段命名，做法B）：
      balance   = 账面资金（对齐 Cash.balance；初始 + 已实现盈亏 - 手续费），保证金不从此扣减
      used_bail = 已用保证金（对齐 Cash.used_bail；遍历持仓动态计算）
      fpnl      = 未平仓浮动盈亏（对齐 Cash.fpnl；按现价重估）
      available = balance - used_bail - frozen
      nav       = balance + fpnl   ← 真实权益（保证金只是占用，仍在 balance 内）

    开仓：校验 available ≥ 保证金+手续费 → balance -= 手续费 → 持仓增加（used_bail 自动上升）
    平仓：balance += 平仓盈亏 - 手续费 → 持仓减少（used_bail 自动下降）
    与方案文档差异：文档"开仓扣保证金/平仓释放"会把持仓期 NAV 低估保证金，
    此处保证金不进出 balance，NAV 始终 = balance + 浮盈，持仓期权益正确。
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
            List[Dict]: 委托回报（[重构] 2026-08-04 对齐 gm 下单返回 List[Dict]），
                        校验/资金/持仓失败返回空列表 []
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
                return []
            filled = self._process_future_order(symbol, volume, side, position_effect,
                                                order_type, price, note)
        else:
            # 股票路径：执行层由子类提供
            filled = self._process_stock_order(symbol, volume, side, position_effect,
                                               order_type, price, note)

        if not filled:
            return []
        return self._order_receipt(symbol, volume, side, position_effect, order_type, price, note)

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
            available_amount = self.balance
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

        AccountManager：持仓 dict {'volume', 'vwap'} → ['volume']
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
        """获取合约规格（[重构] 2026-08-04 方案A 三级解析：注册 > 品种配置 > 统一默认）。

          - 一级：register_contract() 显式注册（有品种数据时最高优先）
          - 二级：future_config['contracts'][symbol] 按品种精确配置
          - 三级：future_config 默认值兜底（无品种数据时统一乘数/保证金率，
                  需配置 default_multiplier 或 default_margin_ratio 才启用；
                  构造后缓存进 _contracts）
        均未命中抛 ValueError（未注册拒单）。
        """
        spec = self._contracts.get(symbol)
        if spec is not None:
            return spec
        fc = self.future_config or {}
        cfg = fc.get('contracts', {}).get(symbol)
        if cfg:
            spec = ContractSpec(symbol=symbol, **cfg)
            self._contracts[symbol] = spec
            return spec
        if self._is_future(symbol) and (fc.get('default_multiplier') is not None
                                        or fc.get('default_margin_ratio') is not None):
            spec = ContractSpec(
                symbol=symbol,
                multiplier=fc.get('default_multiplier') or 1,
                margin_ratio=fc.get('default_margin_ratio', 0.10),
                margin_ratio_near=fc.get('default_margin_ratio_near'),
                price_tick=fc.get('default_price_tick', 1.0),
                exchange=fc.get('default_exchange', ''),
            )
            self._contracts[symbol] = spec
            return spec
        raise ValueError(f"合约 {symbol} 未注册规格且无 future_config 默认值，"
                         f"请调用 register_contract() 或配置 future_config")

    def _remaining_days(self, symbol: str) -> Optional[int]:
        """距最后交易日剩余自然日（未配置 delisted_date 返回 None → 恒用基准保证金率）"""
        spec = self._contracts.get(symbol)
        if spec is None or not spec.delisted_date:
            return None
        try:
            last = datetime.strptime(spec.delisted_date, '%Y-%m-%d').date()
            return (last - context.now.date()).days
        except (ValueError, TypeError):
            return None

    def _calc_margin(self, symbol: str, price: float, volume: int) -> float:
        """计算开仓所需保证金 = 价格 × 乘数 × 保证金率 × 手数（保证金率按到期日分级）"""
        spec = self._get_contract(symbol)
        ratio = spec.effective_margin_ratio(self._remaining_days(symbol))
        return round(price * spec.multiplier * ratio * volume, 2)

    def _get_used_bail(self) -> float:
        """计算当前所有期货持仓的已用保证金（对齐 Cash.used_bail，动态遍历）"""
        total = 0.0
        for (symbol, _side), pos in self.positions.items():
            if not self._is_future(symbol):
                continue
            # [重构] 2026-08-04 方案A：走三级解析，不依赖缓存顺序
            try:
                spec = self._get_contract(symbol)
            except ValueError:
                continue
            try:
                price = self._get_price(symbol)
            except (ValueError, KeyError):
                continue
            if price <= 0:
                continue
            total += pos.used_bail(price, spec.multiplier,
                                   spec.effective_margin_ratio(self._remaining_days(symbol)))
        return round(total, 2)

    def _get_available_cash(self) -> float:
        """可用资金 = 现金 - 已用保证金 - 冻结资金（getattr 兼容无 frozen 属性的 FastAccount）"""
        return round(self.balance - self._get_used_bail() - getattr(self, 'frozen', 0.0), 2)

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

    # 期货下单合法性矩阵： (side, position_effect) → (操作语义, 需持仓条件, order_business, pos_side)
    #   order_business 对齐掘金 gm OrderBusiness_FUTURE_* (10-17)：
    #   10=FUTURE_BUY_OPEN, 11=FUTURE_SELL_CLOSE, 12=FUTURE_SELL_CLOSE_TODAY,
    #   13=FUTURE_SELL_CLOSE_YESTERDAY, 14=FUTURE_SELL_OPEN, 15=FUTURE_BUY_CLOSE,
    #   16=FUTURE_BUY_CLOSE_TODAY, 17=FUTURE_BUY_CLOSE_YESTERDAY
    #   pos_side = 目标持仓方向（对齐掘金 Position.side 维度）
    FUTURE_ORDER_MATRIX = {
        (OrderSide.Buy,  PositionEffect.Open):           ("开多", None, 10, PositionSide.Long),
        (OrderSide.Sell, PositionEffect.Close):          ("平多", 'total', 11, PositionSide.Long),
        (OrderSide.Sell, PositionEffect.CloseToday):     ("平今多", 'today', 12, PositionSide.Long),
        (OrderSide.Sell, PositionEffect.CloseYesterday): ("平昨多", 'yesterday', 13, PositionSide.Long),
        (OrderSide.Sell, PositionEffect.Open):           ("开空", None, 14, PositionSide.Short),
        (OrderSide.Buy,  PositionEffect.Close):          ("平空", 'total', 15, PositionSide.Short),
        (OrderSide.Buy,  PositionEffect.CloseToday):     ("平今空", 'today', 16, PositionSide.Short),
        (OrderSide.Buy,  PositionEffect.CloseYesterday): ("平昨空", 'yesterday', 17, PositionSide.Short),
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

        semantic, required, _, pos_side = rule

        # [重构] 2026-08-04 方案A：走三级解析（注册 > 品种配置 > future_config 默认值），
        #   统一默认构造后缓存进 _contracts，此处不再直接读 _contracts
        try:
            self._get_contract(symbol)
        except ValueError:
            return f"合约 {symbol} 未注册规格且无 future_config 默认值，请 register_contract() 或配置 future_config"

        if required is None:  # 开仓无需检查持仓
            return None

        pos = self.positions.get((symbol, pos_side))
        if pos is None:
            return f"平仓失败: {symbol} 无{'多' if pos_side == PositionSide.Long else '空'}头持仓 ({semantic})"

        if required == 'total':
            total = pos.volume
        elif required == 'today':
            total = pos.volume_today
        elif required == 'yesterday':
            total = pos.volume - pos.volume_today
        else:
            total = 0

        if total < volume:
            return f"平仓不足: 需要 {volume} 手, 可平 {total} 手 ({semantic})"

        return None

    def _order_percent_future(self, symbol: str, percent: float, side: int,
                              position_effect: int, order_type: int,
                              price: float, note: str) -> str:
        """order_percent 的期货路径：基于账户净值 × percent 计算手数。

        对齐掘金 GM 官网手册：order_percent 按"总资产"指定比例委托，
        手数 = nav×percent / (价格×乘数×保证金率)。
        """
        nav = self.get_account()['nav']
        order_amount = nav * abs(percent)
        price = price or self._get_price(symbol)
        if price <= 0:
            raise ValueError(f"Invalid price {price} for {symbol}")
        spec = self._get_contract(symbol)
        ratio = spec.effective_margin_ratio(self._remaining_days(symbol))
        margin_per_lot = price * spec.multiplier * ratio
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
        保证金不进出 balance（见类注释账务模型），used_bail 由持仓动态计算。
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
            self.balance = round(self.balance - commission, 2)
            self._update_future_position(symbol, volume, price, side, position_effect)
        else:
            # ── 平仓（按 matrix 推导目标持仓方向 pos_side）──
            _, _, _, pos_side = self.FUTURE_ORDER_MATRIX[(side, position_effect)]
            pos = self.positions.get((symbol, pos_side))
            if pos is None:
                print(f"期货平仓失败: {symbol} 无持仓")
                return 0
            if pos_side == PositionSide.Long:
                # 平多：盈亏 = (现价 - vwap) × 乘数 × 手数
                pnl = (price - pos.vwap) * spec.multiplier * volume
            else:
                # 平空：盈亏 = (vwap - 现价) × 乘数 × 手数
                pnl = (pos.vwap - price) * spec.multiplier * volume
            self.balance = round(self.balance + pnl - commission, 2)
            self._update_future_position(symbol, volume, price, side, position_effect)

        # ── 成交记录 hook ──
        _, _, _, pos_side = self.FUTURE_ORDER_MATRIX[(side, position_effect)]
        self._record_future_trade(
            symbol=symbol, volume=volume, side=side, position_side=pos_side,
            position_effect=position_effect, order_type=order_type,
            price=price, commission=commission, multiplier=spec.multiplier,
            margin_ratio=spec.effective_margin_ratio(self._remaining_days(symbol)),
            note=note,
        )
        return volume

    def _record_future_trade(self, **kwargs):
        """成交记录 hook 默认空实现；AccountManager 覆写为 TradeRecord。"""
        pass

    def _order_receipt(self, symbol: str, volume: int, side: int, position_effect: int,
                       order_type: int, price: float, note: str = '') -> List[Dict]:
        """构造 gm 风格委托回报 List[Dict]（[重构] 2026-08-04 对齐 gm 下单返回）。

        统一由 TradeRecord.to_dict() 序列化（dataclass 单一字段源，不手写 key）：
        - AccountManager：复用 trade_records[-1]（完整成交记录，含手续费/成交额）
        - FastAccount：临时构造 TradeRecord 复用 to_dict()（不落库，保持零 TradeRecord 设计；
          乘数/保证金率/手续费按合约实际值，非写死）
        """
        records = getattr(self, 'trade_records', None)
        if records:
            return [records[-1].to_dict()]
        # FastAccount：临时构造 TradeRecord（不 append，保持轻量设计）
        pos_side = PositionSide.Long
        multiplier = 1
        commission = 0.0
        margin_ratio = 1.0
        if self._is_future(symbol):
            spec = self._get_contract(symbol)
            pos_side = self.FUTURE_ORDER_MATRIX[(side, position_effect)][3]
            multiplier = spec.multiplier
            margin_ratio = spec.effective_margin_ratio(self._remaining_days(symbol))
            commission = self._calc_future_commission(symbol, price, volume, position_effect)
        trade = TradeRecord(
            created_at=getattr(context, 'now', None) or datetime.now(),
            symbol=symbol, price=price, volume=volume, side=side,
            position_effect=position_effect, position_side=pos_side,
            order_type=order_type, filled_commission=commission,
            order_id='', filled_volume=volume,
            filled_amount=round(price * multiplier * volume, 2),
            multiplier=multiplier, margin_ratio=margin_ratio, note=note,
        )
        return [trade.to_dict()]

    def _update_future_position(self, symbol: str, volume: int, price: float,
                                side: int, position_effect: int):
        """更新期货持仓（统一 (symbol, side) 表，操作单方向 Position）。

        从 FUTURE_ORDER_MATRIX 取目标持仓方向 pos_side，
        8 种组合折叠为 Position.open/close 方法调用：
        Close(默认平仓) 按 FIFO 先平今仓（对齐掘金"期货默认平今"）；
        CloseToday / CloseYesterday 通过 today_volume 参数区分。
        """
        _, _, _, pos_side = self.FUTURE_ORDER_MATRIX[(side, position_effect)]
        pos = self.positions.get((symbol, pos_side))
        if pos is None:
            pos = Position(symbol=symbol, side=pos_side)

        if position_effect == PositionEffect.Open:
            pos.open(volume, price)                      # 开仓加权 vwap
        elif position_effect == PositionEffect.Close:
            pos.close(volume)                            # 平仓(FIFO先平今)
        elif position_effect == PositionEffect.CloseToday:
            pos.close(volume, today_volume=volume)       # 平今
        elif position_effect == PositionEffect.CloseYesterday:
            pos.close(volume, today_volume=0)            # 平昨

        # 清理零持仓
        if pos.is_empty():
            self.positions.pop((symbol, pos_side), None)
        else:
            self.positions[(symbol, pos_side)] = pos

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

        long_pos = self.positions.get((symbol, PositionSide.Long))
        short_pos = self.positions.get((symbol, PositionSide.Short))
        long_vol = long_pos.volume if long_pos else 0
        short_vol = short_pos.volume if short_pos else 0

        receipts = []
        if position_side == PositionSide.Long:
            # 目标多头：先平空（避免锁仓）再调整多头
            if short_vol > 0:
                receipts += self.order_volume(symbol, short_vol, OrderSide.Buy, order_type,
                                              PositionEffect.Close, price, note + ' (平空)')
            delta = volume - long_vol
            if delta > 0:
                receipts += self.order_volume(symbol, delta, OrderSide.Buy, order_type,
                                              PositionEffect.Open, price, note)
            elif delta < 0:
                receipts += self.order_volume(symbol, -delta, OrderSide.Sell, order_type,
                                              PositionEffect.Close, price, note)
        else:
            # 目标空头：先平多（避免锁仓）再调整空头
            if long_vol > 0:
                receipts += self.order_volume(symbol, long_vol, OrderSide.Sell, order_type,
                                              PositionEffect.Close, price, note + ' (平多)')
            delta = volume - short_vol
            if delta > 0:
                receipts += self.order_volume(symbol, delta, OrderSide.Sell, order_type,
                                              PositionEffect.Open, price, note)
            elif delta < 0:
                receipts += self.order_volume(symbol, -delta, OrderSide.Buy, order_type,
                                              PositionEffect.Close, price, note)
        return receipts

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
        future_config: Dict = None,
    ):
        """
        初始化账户管理器
        
        Args:
            init_cash: 初始资金，默认100万
            fee_config: 费用配置，包含佣金率、印花税率、最低佣金
            future_config: [新增] 2026-08-04 方案A 期货统一规格（无品种数据时兜底）：
                default_multiplier  统一乘数（必须显式给定，乘数因品种差异大无通用默认）
                default_margin_ratio 统一保证金率（默认 0.10，国内商品/股指常见中枢）
                default_margin_ratio_near 分级保证金上浮（不配=不分级）
                default_price_tick / default_exchange
                contracts: {symbol: {...}} 按品种精确覆盖（优先于默认值）
                解析优先级：register_contract > contracts[symbol] > 默认值
        """
        self.balance = round(init_cash, 2)
        # [重构] 2026-08-04 深度B：统一持仓表 (symbol, side) → Position（股票 side=Long，期货 Long/Short）
        self.positions: Dict[Tuple[str, int], Position] = {}
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
        # [新增] 2026-08-04 方案A：期货统一默认规格（与 fee_config 平级，run_fast 透传）
        self.future_config: Dict = future_config or {}

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
            balance=self.balance,
            nav=self.balance,
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
        total_assets = self.balance          # 股票部分累加市值
        total_fpnl = 0.0             # [新增] 2026-08-04 期货浮动盈亏

        # [重构] 2026-08-04 深度B：统一遍历 (symbol, side) → Position
        for (symbol, side), pos in self.positions.items():
            try:
                price = self._get_price(symbol)
            except (ValueError, KeyError):
                continue
            if price <= 0:
                continue

            if self._is_future(symbol):
                # 期货：NAV 只记浮动盈亏（保证金仍占用 balance 内）
                try:
                    spec = self._get_contract(symbol)
                except ValueError:
                    continue
                total_fpnl += pos.fpnl(price, spec.multiplier)
                pos_snap = PositionSnapshot(
                    symbol=symbol, side=side,
                    volume=pos.volume, volume_today=pos.volume_today,
                    vwap=pos.vwap, price=price, created_at=created_at,
                )
                pos_snapshots[(symbol, side)] = pos_snap
                continue

            # 股票：市值计入 NAV
            total_assets += pos.volume * price
            pos_snap = PositionSnapshot(
                symbol=symbol, side=side,
                volume=pos.volume, volume_today=pos.volume_today,
                vwap=round(pos.vwap, 3), price=price, created_at=created_at,
            )
            pos_snapshots[(symbol, side)] = pos_snap

        total_assets = round(total_assets + total_fpnl, 2)
        snapshot = AccountSnapshot(
            balance=self.balance,
            nav=total_assets,
            created_at=created_at,
            positions=pos_snapshots,
            used_bail=self._get_used_bail(),
            fpnl=round(total_fpnl, 2),
        )
        self.snapshots.append(snapshot)

        return snapshot

    def load_snapshot(self, snapshot: AccountSnapshot):
        """
        从快照恢复账户状态
        
        Args:
            snapshot: 账户快照对象
        """
        self.balance = round(snapshot.balance, 2)
        self.positions = {}
        for key, pos in snapshot.positions.items():
            # 兼容旧快照键格式（str）与新格式 ((symbol, side))
            symbol, side = key if isinstance(key, tuple) else (key, PositionSide.Long)
            self.positions[(symbol, side)] = Position(
                symbol=symbol, side=side,
                volume=int(pos.volume),
                volume_today=int(getattr(pos, 'volume_today', pos.volume)),
                vwap=pos.vwap,
            )
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
        """[覆写] 股票订单执行：生成 order_id → _process_order（TradeRecord+快照）。
        失败（资金不足/持仓不足）返回 ''，由 order_volume 出口转空列表。"""
        order_id = f"order_{len(self.trade_records)+1}"
        filled = self._process_order(symbol, volume, side, position_effect, order_type,
                                     price, order_id, note)
        return order_id if filled else ''

    def _get_stock_position_volume(self, symbol: str) -> float:
        """[覆写] 股票持仓数量（统一持仓表 (symbol, Long) → Position）"""
        pos = self.positions.get((symbol, PositionSide.Long))
        return pos.volume if pos else 0

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

        key = (symbol, PositionSide.Long)   # [重构] 2026-08-04 股票恒多头

        if side == OrderSide.Buy:
            total_cost = round(volume * price + total_fee, 2)
            if self.balance < total_cost:
                print(f"订单 {order_id} 买入 {symbol} 失败，资金不足。需要 {total_cost}，可用资金 {self.balance}")
                return 0
            self.balance = round(self.balance - total_cost, 2)
            pos = self.positions.get(key)
            if pos is None:
                pos = Position(symbol=symbol, side=PositionSide.Long)
            pos.open(volume, price)   # vwap 不含手续费（对齐掘金 Position.vwap）
            self.positions[key] = pos
        else:
            pos = self.positions.get(key)
            if pos is None or pos.volume < volume:
                cur = pos.volume if pos else 0
                print(f"订单 {order_id} 卖出 {symbol} 失败，持仓不足。需要 {volume}，当前持仓 {cur}")
                return 0
            self.balance = round(self.balance + volume * price - total_fee, 2)
            pos.close(volume)
            if pos.is_empty():
                self.positions.pop(key, None)

        self.trade_records.append(TradeRecord(
            created_at=context.now,
            symbol=symbol,
            price=price,
            volume=volume,
            side=side,
            position_effect=position_effect,
            position_side=PositionSide.Long,
            order_type=order_type,
            filled_commission=total_fee,
            order_id=order_id,
            filled_volume=volume,
            filled_amount=price * volume,
            note=note,
        ))
        return volume

    # [新增] 2026-08-04 期货支持：核心逻辑见 _OrderMixin（AccountManager/FastAccount 共享）
    #   账务模型：保证金不进出 cash，NAV = cash + 浮盈，详见 mixin 注释。
    # [重构] 2026-08-04 期货方法已移入 _OrderMixin，此处仅覆写成交记录 hook。

    def _record_future_trade(self, symbol: str, volume: int, side: int,
                             position_side: int, position_effect: int,
                             order_type: int, price: float, commission: float,
                             multiplier: int, note: str = '', margin_ratio: float = 1.0):
        """[覆写] 期货成交记录 → TradeRecord（FastAccount 走 mixin 默认空实现）
        position_side 由 FUTURE_ORDER_MATRIX 推导（对齐掘金 Position.side）；
        margin_ratio = 开仓时生效保证金率（含分级），供 analyzer 保证金口径收益率。"""
        order_id = f"order_{len(self.trade_records)+1}"
        self.trade_records.append(TradeRecord(
            created_at=context.now,
            symbol=symbol,
            price=price,
            volume=volume,
            side=side,
            position_effect=position_effect,
            position_side=position_side,
            order_type=order_type,
            filled_commission=commission,
            order_id=order_id,
            filled_volume=volume,
            filled_amount=round(price * multiplier * volume, 2),
            multiplier=multiplier,
            margin_ratio=margin_ratio,
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
            return self._account_dict(self.balance, self.balance, query_time,
                                      used_bail=self._get_used_bail())

        snapshot = next(
            (s for s in reversed(self.snapshots) if s.created_at <= query_time),
            None
        )

        if snapshot is None:
            return self._account_dict(self.balance, self.balance, query_time,
                                      used_bail=self._get_used_bail())

        used_bail = getattr(snapshot, 'used_bail', 0.0)
        fpnl = getattr(snapshot, 'fpnl', 0.0)
        return self._account_dict(snapshot.balance, snapshot.nav, snapshot.created_at,
                                  used_bail=used_bail, fpnl=fpnl)

    def _account_dict(self, balance: float, nav: float, created_at: datetime,
                      used_bail: float = 0.0, fpnl: float = 0.0) -> Dict:
        """构造 get_account 返回字典（三分支共用，消除重复）。

        字段对齐掘金 Cash：balance/nav/available + 期货扩展(used_bail/fpnl/risk_ratio)
        """
        return {
            'balance': balance,
            'nav': nav,
            'created_at': created_at,
            # [新增] 2026-08-04 期货字段：可用资金/已用保证金/浮动盈亏/风险度
            'available': round(balance - used_bail - self.frozen, 2),
            'used_bail': used_bail,
            'fpnl': fpnl,
            'risk_ratio': round(used_bail / nav, 4) if nav > 0 else 0.0,
        }

    def get_position(self, symbol: str = None, side: int = None) -> List[Dict]:
        """
        获取持仓信息（[重构] 2026-08-04 深度B：对齐掘金 gm get_position 返回 Position 列表）。

        Args:
            symbol: 合约/股票代码，过滤单品种
            side: 持仓方向（PositionSide.Long/Short），过滤单方向

        Returns:
            List[Dict]: [{symbol, side, volume, volume_today, vwap}, ...]，
                        空列表表示无持仓（falsy，兼容 `if get_position()` 判断）
        """
        result = []
        for (sym, s), pos in self.positions.items():
            if symbol and sym != symbol:
                continue
            if side is not None and s != side:
                continue
            result.append(pos.to_dict())
        return result

    def get_orders(
        self,
        start_query_time: datetime = None,
        end_query_time: datetime = None
    ) -> List[Dict]:
        """
        获取成交记录（[重构] 2026-08-04 返回 List[Dict]，对齐 gm get_orders 返回类型）
        
        Args:
            start_query_time: 查询起始时间
            end_query_time: 查询结束时间
            
        Returns:
            List[Dict]: 成交记录列表（字段对齐 gm Order），空列表表示无成交
        """
        trades = [t.to_dict() for t in self.trade_records]

        if start_query_time:
            trades = [t for t in trades if t['created_at'] >= start_query_time]
        if end_query_time:
            trades = [t for t in trades if t['created_at'] <= end_query_time]

        return trades

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
            self.balance = round(init_cash, 2)
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
      持仓 Position 对象（统一 (symbol, side) 表），账务与 AccountManager 完全一致（NAV=balance+浮盈）。
    """

    __slots__ = ('balance', 'positions', 'fee_config', 'future_config', 'daily_assets',
                 '_latest_prices', '_contracts')

    FREQ_ORDER = ['1m', '60s', '5m', '300s', '15m', '900s',
                  '30m', '1800s', '60m', '3600s', '1d']

    def __init__(self, cash: float = 1e6, fee_config: Dict = None, future_config: Dict = None):
        self.balance = float(cash)
        # [重构] 2026-08-04 深度B：统一持仓表 (symbol, side) → Position（与 AccountManager 一致）
        self.positions: Dict[Tuple[str, int], Position] = {}
        self.fee_config = fee_config or {
            'commission_rate': 0.0,
            'stamp_tax_rate': 0.0,
            'min_commission': 0.0,
        }
        self.future_config: Dict = future_config or {}  # [新增] 2026-08-04 方案A：期货统一默认规格
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
        nav = self.balance
        fpnl = 0.0
        # [重构] 2026-08-04 深度B：统一遍历 (symbol, side) → Position
        for (sym, _side), pos in self.positions.items():
            # [优化] 2026-06-21 优先读引擎注入的 bar 价格缓存
            price = self._latest_prices.get(sym)
            if price is None:
                try:
                    price = self._get_price(sym)
                except (ValueError, KeyError):
                    pass
            if price:
                if self._is_future(sym):
                    try:
                        spec = self._get_contract(sym)
                    except ValueError:
                        continue
                    fpnl += pos.fpnl(price, spec.multiplier)
                else:
                    nav += pos.volume * price
        nav += fpnl
        self.daily_assets[date] = round(nav, 2)

    # ── 下单 (逻辑由 _OrderMixin 统一提供，此处仅覆写股票执行层 hook) ──
    #   [重构] 2026-08-04 order_percent/order_volume/order_value 及期货分叉
    #   移入 _OrderMixin，签名/验证链单份维护；差异仅在执行层：
    #     AccountManager → _process_order (TradeRecord + 快照)
    #     FastAccount    → _process_order (现金 + 持仓, 无 TradeRecord/快照)

    def _process_stock_order(self, symbol: str, volume: int, side: int,
                             position_effect: int, order_type: int,
                             price: float, note: str = '') -> str:
        """[覆写] 股票订单执行：轻量路径（现金+持仓，无 TradeRecord/快照）。
        返回成交量，0=失败（由 order_volume 出口转空列表）。"""
        return self._process_order(symbol, volume, side, price)

    def _get_stock_position_volume(self, symbol: str) -> float:
        """[覆写] 股票持仓数量（统一持仓表 (symbol, Long) → Position）"""
        pos = self.positions.get((symbol, PositionSide.Long))
        return pos.volume if pos else 0

    def _process_order(self, symbol: str, volume: int, side: int,
                       price: float) -> int:
        """执行订单 — 现金+持仓更新，对齐 AccountManager._process_order 现金计算。

        与 AccountManager._process_order 的区别：不生成 TradeRecord，不触发快照。
        [重构] 2026-08-04 深度B：股票持仓用 Position 对象（(symbol, Long) 表）。
        """
        fee = self.fee_config

        commission = max(
            round(price * volume * fee['commission_rate'], 2),
            fee['min_commission']
        )
        stamp_tax = round(price * volume * fee['stamp_tax_rate'], 2) if side == OrderSide.Sell else 0
        total_fee = round(commission + stamp_tax, 2)

        key = (symbol, PositionSide.Long)

        if side == OrderSide.Buy:
            total_cost = round(volume * price + total_fee, 2)
            if self.balance < total_cost:
                print(f"FastAccount 买入 {symbol} 失败，资金不足。需要 {total_cost}，可用资金 {self.balance}")
                return 0
            self.balance = round(self.balance - total_cost, 2)
            pos = self.positions.get(key)
            if pos is None:
                pos = Position(symbol=symbol, side=PositionSide.Long)
            pos.open(volume, price)   # vwap 不含手续费（对齐掘金 Position.vwap）
            self.positions[key] = pos
        else:
            pos = self.positions.get(key)
            if pos is None or pos.volume < volume:
                cur = pos.volume if pos else 0
                print(f"FastAccount 卖出 {symbol} 失败，持仓不足。需要 {volume}，当前持仓 {cur}")
                return 0
            self.balance = round(self.balance + volume * price - total_fee, 2)
            pos.close(volume)
            if pos.is_empty():
                self.positions.pop(key, None)

        return volume

    # ── 查询 (兼容 AccountManager 接口) ──

    def get_position(self, symbol: str = None, side: int = None):
        """返回持仓信息（[重构] 2026-08-04 对齐掘金：Position dict 列表，可用 symbol/side 过滤）。

        Returns:
            List[Dict]: [{symbol, side, volume, volume_today, vwap}, ...]
        """
        result = []
        for (sym, s), pos in self.positions.items():
            if symbol and sym != symbol:
                continue
            if side is not None and s != side:
                continue
            result.append(pos.to_dict())
        return result

    def get_account(self, query_time=None):
        """返回账户概览。nav = balance + 股票市值 + 期货浮盈，优先读 _latest_prices 缓存。"""
        nav = self.balance
        fpnl = 0.0
        for (sym, _side), pos in self.positions.items():
            price = self._latest_prices.get(sym)
            if price is None:
                try:
                    price = self._get_price(sym)
                except (ValueError, KeyError):
                    pass
            if price:
                if self._is_future(sym):
                    try:
                        spec = self._get_contract(sym)
                    except ValueError:
                        continue
                    fpnl += pos.fpnl(price, spec.multiplier)
                else:
                    nav += pos.volume * price
        return {'balance': self.balance, 'nav': round(nav + fpnl, 2)}


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
