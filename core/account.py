#这个类是带东八时区的，逐一其他数据要时区一致
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
import pandas as pd
from .storage import context

@dataclass
class PositionSnapshot:
    symbol: str
    volume: float
    cost_price: float
    price: float
    created_at: datetime

@dataclass
class AccountSnapshot:
    cash: float
    nav: float
    created_at: datetime
    positions: Dict[str, PositionSnapshot] = field(default_factory=dict)
    
@dataclass
class TradeRecord:
    created_at: datetime
    symbol: str
    price: float
    volume: float
    side: str
    fee: float
    order_id: str

class AccountManager:
    FREQ_ORDER = ['1m', '60s', '5m', '300s', '15m', '900s', '30m', '1800s', '60m', '3600s', '1d']
    
    def __init__(
        self,
        init_cash: float = 1e6,
        fee_config: Dict = None,
    ):
        self.cash = round(init_cash, 2)
        self.positions: Dict[str, Dict] = {}
        self.trade_log: List[TradeRecord] = []
        self.snapshots: List[AccountSnapshot] = []
        self.fee_config = fee_config or {
            'commission_rate': 0.0003,
            'stamp_tax_rate': 0.001,
            'min_commission': 5.0
        }

    def take_snapshot(self,created_at: datetime=None) -> AccountSnapshot:
        if created_at is None:
            created_at = context.now
                
        pos_snapshots = {}
        total_assets = self.cash
        
        for symbol, pos in self.positions.items():
            price = self._get_price(symbol)
            pos_snap = PositionSnapshot(
                symbol=symbol,
                volume=pos['volume'],
                cost_price=round(pos['cost_price'], 3),
                price=price,
                created_at=created_at
            )
            pos_snapshots[symbol] = pos_snap
            total_assets += pos['volume'] * price

        total_assets = round(total_assets, 2)
        snapshot = AccountSnapshot(
            cash=self.cash,
            nav=total_assets,
            created_at=created_at,
            positions=pos_snapshots
        )
        self.snapshots.append(snapshot)
        
        return snapshot

    def _get_price(self, symbol: str) -> float:
        action_time = context.now
        subscribed_freqs = {freq for (s, freq) in context._subscribed if s == symbol}
        if not subscribed_freqs:
            raise ValueError(f"品种 {symbol} 未订阅任何频率数据")
            
        frequencies = [f for f in self.FREQ_ORDER if f in subscribed_freqs]
        
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

    def order_percent(
        self, 
        symbol: str, 
        percent: float, 
        price: float = None, 
    ) -> str:
        if not -1 <= percent <= 1:
            raise ValueError("Percent must be between -1 and 1")
            
        if percent == 0:
            raise ValueError("Order percent cannot be zero")

        account_info = self.get_account()
        nav = account_info['nav']

        order_amount = nav * abs(percent)

        if percent > 0:
            available_amount = self.cash
            if order_amount > available_amount:
                order_amount = available_amount

        price = price or self._get_price(symbol)
        if price <= 0:
            raise ValueError(f"Invalid price {price} for {symbol}")

        if percent > 0:
            commission = max(
                round(order_amount * self.fee_config['commission_rate'], 2),
                self.fee_config['min_commission']
            )
            available_amount = order_amount - commission
            volume = int(available_amount / price)
        else:
            current_pos = self.positions.get(symbol, {'volume': 0})
            volume = -int(current_pos['volume'] * abs(percent))

        if volume == 0:
            raise ValueError("Calculated order volume is zero")

        return self.order_volume(symbol, volume, price)

    def order_volume(
        self, 
        symbol: str, 
        volume: int, 
        price: float = None, 
    ) -> str:
        if volume == 0:
            raise ValueError("Order volume cannot be zero")
            
        price = price or self._get_price(symbol)
        if price <= 0:
            raise ValueError(f"Invalid price {price} for {symbol}")

        order_id = f"order_{len(self.trade_log)+1}"
        
        executed_volume = self._process_order(symbol, volume, price, order_id)
        
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
        commission = max(
            round(price * abs(volume) * self.fee_config['commission_rate'], 2),
            self.fee_config['min_commission']
        )
        stamp_tax = round(price * abs(volume) * self.fee_config['stamp_tax_rate'], 2) if volume < 0 else 0
        total_fee = round(commission + stamp_tax, 2)
        
        if volume > 0:
            total_cost = round(volume * price + total_fee, 2)
            if self.cash < total_cost:
                print(f"订单 {order_id} 买入 {symbol} 失败，资金不足。需要 {total_cost}，可用资金 {self.cash}")
                return 0
            self.cash = round(self.cash - total_cost, 2)
        else:
            current_pos = self.positions.get(symbol, {'volume': 0})
            if current_pos['volume'] < abs(volume):
                print(f"订单 {order_id} 卖出 {symbol} 失败，持仓不足。需要 {abs(volume)}，当前持仓 {current_pos['volume']}")
                return 0
            self.cash = round(self.cash + abs(volume) * price - total_fee, 2)
        
        self._update_position(symbol, volume, price, total_fee)
        
        self.trade_log.append(TradeRecord(
            symbol=symbol,
            volume=volume,
            price=price,
            side='buy' if volume>0 else 'sell',
            created_at=context.now,
            order_id=order_id,
            fee=total_fee
        ))
        return volume

    def _update_position(self, symbol: str, volume: int, price: float, total_fee: float):
        pos = self.positions.get(symbol, {'volume': 0, 'cost_price': 0})
        if volume > 0:
            new_volume = pos['volume'] + volume
            total_purchase_cost = pos['volume'] * pos['cost_price'] + volume * price + total_fee
            new_cost = total_purchase_cost / new_volume
            pos.update(volume=new_volume, cost_price=round(new_cost, 3))
        else:
            pos['volume'] += volume
            if pos['volume'] == 0:
                del self.positions[symbol]
                return
        self.positions[symbol] = pos

    def get_account(self, query_time: datetime = None) -> Dict:
        query_time = context.now if query_time is None else query_time

        if not self.snapshots:
            return {
                'cash': self.cash,
                'nav': self.cash,
                'created_at': query_time
            }
            
        snapshot = next(
            (s for s in reversed(self.snapshots) if s.created_at <= query_time),
            None
        )
        
        if snapshot is None:
            return {
                'cash': self.cash,
                'nav': self.cash,
                'created_at': query_time
            }
            
        return {
            'cash': snapshot.cash,
            'nav': snapshot.nav,
            'created_at': snapshot.created_at
        }

    def get_position(self, symbol: str = None) -> Dict:
        if not self.snapshots:
            positions = self.positions.copy()
        else:
            last_snapshot = self.snapshots[-1]
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
        trades = self.trade_log
        
        if start_query_time:
            trades = [t for t in trades if t.created_at >= start_query_time]
        if end_query_time:
            trades = [t for t in trades if t.created_at <= end_query_time]
            
        return trades.copy()

    def load_snapshot(self, snapshot: AccountSnapshot):
        self.cash = round(snapshot.cash, 2)
        self.positions = {
            sym: {'volume': pos.volume, 'cost_price': round(pos.cost_price, 3)}
            for sym, pos in snapshot.positions.items()
        }
        self.current_time = snapshot.created_at


account = AccountManager(init_cash=1e6)
