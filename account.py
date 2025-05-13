#这个类是带东八时区的，逐一其他数据要时区一致
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable, Union, TypeVar, Any
import pandas as pd
import pytz
from .storage import context
# 添加插件类型定义
T = TypeVar('T')
class Plugin:
    def update(self, account: 'AccountManager', timestamp: datetime) -> None:
        pass
    
    def get_results(self) -> Any:
        pass
# ---------- 基础数据结构 ----------
@dataclass
class PositionSnapshot:
    """持仓快照（支持任意时间粒度）"""
    symbol: str
    volume: float            # 持仓数量
    cost_price: float        # 持仓成本价
    market_price: float      # 快照时标的价格
    created_at: datetime     # 快照时间（严格使用datetime）

@dataclass
class AccountSnapshot:
    """账户快照（与掘金account()返回值兼容）"""
    cash: float              # 可用资金
    total_assets: float       # 总资产价值
    created_at: datetime     # 快照时间（严格使用datetime）
    positions: Dict[str, PositionSnapshot] = field(default_factory=dict)
    
@dataclass
class TradeRecord:
    """成交记录（兼容掘金接口）"""
    created_at: datetime     # 成交时间（严格使用datetime）
    symbol: str
    price: float
    volume: float
    side: str                # 'buy'/'sell'
    fee: float               # 总手续费
    order_id: str            # 模拟订单ID

# ---------- 核心账户类 ----------
##这个账户管理类，还得改动一下。初始化参数减少。让它作为全局变量放到引擎里面。这样时间轴才能真实有效。
class AccountManager:
    def __init__(
        self,
        init_cash: float = 1e6,
        fee_config: Dict = None,
        price_provider: Callable[[str, datetime], float] = None,
    ):
        """
        :param init_cash: 初始资金
        :param fee_config: 手续费配置（默认股票费率）
        :param price_provider: 价格获取函数 (symbol, datetime) -> price
        """
        # 账户状态
        self.cash = round(init_cash, 2)
        self.positions: Dict[str, Dict] = {}  # {symbol: {'volume': x, 'cost_price': y}}
        
        # 历史记录
        self.trade_log: List[TradeRecord] = []
        self.snapshots: List[AccountSnapshot] = []
        
        # 配置
        self.fee_config = fee_config or {
            'commission_rate': 0.0003,  # 佣金率
            'stamp_tax_rate': 0.001,    # 印花税（仅卖出）
            'min_commission': 5.0       # 最低佣金
        }
        self.price_provider = price_provider
        
        # 插件列表（初始化为None）
        self._plugins: Optional[Dict[str, Plugin]] = None


    # ---------- 核心方法 ----------
    def take_snapshot(self) -> AccountSnapshot:
        """记录账户快照"""
        created_at = context.now
        
        pos_snapshots = {}
        total_assets = self.cash
        
        for symbol, pos in self.positions.items():
            price = self._get_market_price(symbol)
            pos_snap = PositionSnapshot(
                symbol=symbol,
                volume=pos['volume'],
                cost_price=round(pos['cost_price'], 3),
                market_price=price,
                created_at=created_at
            )
            pos_snapshots[symbol] = pos_snap
            total_assets += pos['volume'] * price

        total_assets = round(total_assets, 2)
        snapshot = AccountSnapshot(
            cash=self.cash,
            total_assets=total_assets,
            created_at=created_at,
            positions=pos_snapshots
        )
        self.snapshots.append(snapshot)

        # 更新插件（仅在插件启用时）
        if self._plugins is not None:
            for plugin in self._plugins.values():
                plugin.update(self, created_at)
        
        return snapshot

    def _get_market_price(self, symbol: str) -> float:
        """获取指定时间的市场价格"""
        if self.price_provider is None:
            raise ValueError("Price provider must be set before getting market price")
        
        action_time = context.now
        price = self.price_provider(symbol, action_time) #这里保留时间参数，对外部数据的处理相对通用
        
        if not isinstance(price, (float, int)) or price <= 0:
            raise ValueError(f"Invalid price {price} for {symbol} at {action_time}")
        return float(price)

    def order_percent(
        self, 
        symbol: str, 
        percent: float, 
        price: float = None, 
    ) -> str:
        """
        按总资产指定比例下单
        :param symbol: 标的代码
        :param percent: 下单比例，0-1 之间，正数买入，负数卖出
        :param price: 指定价格（可选）
        :return: 模拟订单ID
        """
       
        if not -1 <= percent <= 1:
            raise ValueError("Percent must be between -1 and 1")
            
        if percent == 0:
            raise ValueError("Order percent cannot be zero")

        # 获取当前总资产，使用 get_account 方法避免额外记录快照
        account_info = self.get_account()
        total_assets = account_info['total_assets']

        # 计算下单金额
        order_amount = total_assets * abs(percent)

        if percent > 0:  # 买入
            # 考虑手续费，计算可购买的最大金额
            available_amount = self.cash
            if order_amount > available_amount:
                # 若下单金额超过可用金额，使用全部可用金额下单
                order_amount = available_amount

        # 获取当前价格
        price = price or self._get_market_price(symbol)
        if price <= 0:
            raise ValueError(f"Invalid price {price} for {symbol}")

        # 计算下单数量
        if percent > 0:  # 买入
            # 考虑手续费，计算可购买的最大数量
            commission = max(
                round(order_amount * self.fee_config['commission_rate'], 2),
                self.fee_config['min_commission']
            )
            available_amount = order_amount - commission
            volume = int(available_amount / price)
        else:  # 卖出
            current_pos = self.positions.get(symbol, {'volume': 0})
            volume = -int(current_pos['volume'] * abs(percent))

        if volume == 0:
            raise ValueError("Calculated order volume is zero")

        # 调用按数量下单方法
        return self.order_volume(symbol, volume, price)

    def order_volume(
        self, 
        symbol: str, 
        volume: int, 
        price: float = None, 
    ) -> str:
        """
        按数量下单
        :param volume: >0买入，<0卖出
        :param price: 指定价格（可选）
        :return: 模拟订单ID
        """
        if volume == 0:
            raise ValueError("Order volume cannot be zero")
            
        price = price or self._get_market_price(symbol)
        if price <= 0:
            raise ValueError(f"Invalid price {price} for {symbol}")

        # 生成订单ID
        order_id = f"order_{len(self.trade_log)+1}"
        
        # 计算实际成交量（考虑持仓限制）
        executed_volume = self._process_order(symbol, volume, price, order_id)
        
        # 记录成交
        if executed_volume != 0:
            self.take_snapshot()
        return order_id

    def _process_order(
        self, 
        symbol: str, 
        volume: int, 
        price: float, 
        order_id: str,
    ) -> int:
        """处理订单成交（返回实际成交量）"""
        # 计算手续费
        commission = max(
            round(price * abs(volume) * self.fee_config['commission_rate'], 2),
            self.fee_config['min_commission']
        )
        stamp_tax = round(price * abs(volume) * self.fee_config['stamp_tax_rate'], 2) if volume < 0 else 0
        total_fee = round(commission + stamp_tax, 2)
        
        # 买入逻辑
        if volume > 0:
            total_cost = round(volume * price + total_fee, 2)
            if self.cash < total_cost:
                error_msg = f"订单 {order_id} 买入 {symbol} 失败，资金不足。需要 {total_cost}，可用资金 {self.cash}"
                print(error_msg)
                return 0  # 资金不足
            self.cash = round(self.cash - total_cost, 2)
        # 卖出逻辑
        else:
            current_pos = self.positions.get(symbol, {'volume': 0})
            if current_pos['volume'] < abs(volume):
                error_msg = f"订单 {order_id} 卖出 {symbol} 失败，持仓不足。需要 {abs(volume)}，当前持仓 {current_pos['volume']}"
                print(error_msg)
                return 0  # 持仓不足
            self.cash = round(self.cash + abs(volume) * price - total_fee, 2)
        
        # 更新持仓
        self._update_position(symbol, volume, price, total_fee)  # 传递手续费参数
        
        # 记录交易
        self.trade_log.append(TradeRecord(
            symbol=symbol,
            volume=volume,
            price=price,
            side='buy' if volume>0 else 'sell',
            created_at=context.now, #使用context.now
            order_id=order_id,
            fee=total_fee
        ))
        return volume

    def _update_position(self, symbol: str, volume: int, price: float, total_fee: float):
        """更新持仓成本（移动平均法，包含手续费）"""
        pos = self.positions.get(symbol, {'volume': 0, 'cost_price': 0})
        if volume > 0:  # 买入
            new_volume = pos['volume'] + volume
            # 把手续费分摊到每一股上
            total_purchase_cost = pos['volume'] * pos['cost_price'] + volume * price + total_fee
            new_cost = total_purchase_cost / new_volume
            pos.update(volume=new_volume, cost_price=round(new_cost, 3))
        else:  # 卖出
            pos['volume'] += volume  # volume为负数
            if pos['volume'] == 0:
                del self.positions[symbol]
                return
        self.positions[symbol] = pos

    # ---------- 查询接口 ----------
    def get_account(self, query_time: datetime = None) -> Dict:
        """获取当前账户信息"""
        query_time = context.now if query_time is None else query_time

        if not self.snapshots:
            return {
                'cash': self.cash,
                'total_assets': self.cash,
                'created_at': query_time
            }
            
        # 找到指定时间的最新快照
        snapshot = next(
            (s for s in reversed(self.snapshots) if s.created_at <= query_time),
            None
        )
        
        if snapshot is None:
            return {
                'cash': self.cash,
                'total_assets': self.cash,
                'created_at': query_time
            }
            
        return {
            'cash': snapshot.cash,
            'total_assets': snapshot.total_assets,
            'created_at': snapshot.created_at
        }

    def get_positions(self, symbol: str = None) -> Dict:
        """获取持仓"""
        if not self.snapshots:
            # 若没有快照，返回当前持仓
            positions = self.positions.copy()
        else:
            # 获取最后一次快照
            last_snapshot = self.snapshots[-1]
            # 从最后一次快照中提取持仓信息
            positions = {
                sym: {'volume': pos.volume, 'cost_price': pos.cost_price}
                for sym, pos in last_snapshot.positions.items()
            }

        if symbol:
            pos = positions.get(symbol, {'volume': 0, 'cost_price': 0})
            pos['cost_price'] = round(pos['cost_price'], 3)
            return pos
        for pos in positions.values():
            pos['cost_price'] = round(pos['cost_price'], 3)
        return positions

    def get_orders(
        self, 
        start_query_time: datetime = None, 
        end_query_time: datetime = None
    ) -> List[TradeRecord]:
        """获取历史订单"""
            
        if start_query_time and end_query_time:
            return [t for t in self.trade_log if start_query_time <= t.created_at <= end_query_time]
        elif start_query_time:
            return [t for t in self.trade_log if t.created_at >= start_query_time]
        elif end_query_time:
            return [t for t in self.trade_log if t.created_at <= end_query_time]
        return self.trade_log.copy()


    # ---------- 仿真专用方法 ----------
    def load_snapshot(self, snapshot: AccountSnapshot):
        """加载账户快照（用于仿真初始化）"""
        self.cash = round(snapshot.cash, 2)
        self.positions = {
            sym: {'volume': pos.volume, 'cost_price': round(pos.cost_price, 3)}
            for sym, pos in snapshot.positions.items()
        }
        self.current_time = self._validate_time(snapshot.created_at)

    def add_plugin(self, plugin: Plugin, plugin_name: str):
        """添加插件"""
        if self._plugins is None:
            self._plugins = {}
        self._plugins[plugin_name] = plugin


    def get_plugin_results(self, plugin_name: Optional[str] = None):
        """获取所有插件的结果或特定插件的结果"""
        # 检查插件系统是否初始化
        if self._plugins is None:
            if plugin_name is None:
                return {}
            else:
                raise KeyError(f"No plugin found with name: {plugin_name}")
        
        if plugin_name is None:
            results = {}
            for name, plugin in self._plugins.items():
                results[name] = plugin.get_results()
            return results
        else:
            if plugin_name in self._plugins:
                return self._plugins[plugin_name].get_results()
            else:
                raise KeyError(f"No plugin found with name: {plugin_name}")

##这个类有外部回调函数，不能在这里设置统一实例。应该配合外部函数，再初始化实例

#设置一个按日度获取价格的回调函数
def day_price_provider(symbol: str, timestamp: datetime) -> float:
    # 按时间查找最接近的 bar 数据
    data = context.data(symbol=symbol, frequency='1d', count=3, fields=['close', 'eob'])
    for d in reversed(data):  # 倒序查找第一个 eob <= timestamp 的价格
        if d['eob'] <= timestamp:
            return d['close']
    raise ValueError(f"未找到 {symbol} 在 {timestamp} 的有效价格")

account = AccountManager(init_cash=1e6, price_provider=day_price_provider)#把账户管理类，独立出来。不再context里面。