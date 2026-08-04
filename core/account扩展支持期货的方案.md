# AccountManager 扩展支持期货 — 实施方案

> **原则：直接改造 AccountManager，不新建子类。股票路径零改动，期货路径增量添加。**

---

## 实施状态（2026-08-04 已落地）

- ✅ `AccountManager` 期货下单已实现（`order_volume/order_percent/order_value` 签名对齐掘金 GM，`order_target_volume/value/percent` 用 `position_side`）
- ✅ 下单共用逻辑提取为 `_OrderMixin`（`AccountManager` 与 `FastAccount` 共享，股票+期货）：订单三件套签名/验证链/期货分叉单份维护，持仓统一 `FuturePosition` 对象；股票执行层差异走 `_process_stock_order` hook
- ✅ `FastAccount` 期货支持已完成（复用 mixin，NAV = cash + 浮盈）
- ✅ 字段命名对齐掘金官网：`multiplier/margin_ratio`（get_symbols）、`price_tick/delisted_date`（get_symbol_infos）
- ✅ `FUTURE_ORDER_MATRIX` 标注 gm `OrderBusiness_FUTURE_*`（10-17）
- ⚠️ 与本文档差异：账务模型采用"做法B"（保证金不进出 cash，NAV = cash + 浮盈），非本文"开仓扣保证金"（做法A）——做法B 持仓期权益正确
- ⚠️ 未实现：第八节"fee_config['contracts'] 懒加载"、`order_batch`（用户明确无需求）
- 冒烟测试：`tmp/test_futures_smoke.py`（15 组，含 FastAccount 链路）

---

## 一、整体策略：品种分叉，股票路径零改动

```
order_percent / order_volume
        │
        ▼ _is_future(symbol)?
       / \
    否  是
    │    │
    │    └── _validate_future_order()  ← 校验 side+position_effect 合法性
    │    │
    ▼    ▼
_process_order()           _process_future_order()
(股票原逻辑零改动)           (保证金+多空+平今平昨)

        │                    │
        └─────┬──────────────┘
              ▼
        take_snapshot()  ← 期货多空双向分别估值
```

核心思想：在 `order_volume()` 入口处做一次 `if` 分叉，之后的两条路径互不干扰。

---

## 二、新增数据结构

### 2.1 ContractSpec（合约规格数据类）

```python
@dataclass
class ContractSpec:
    symbol: str            # 合约代码，如 'RB2510.SHF'
    product_code: str      # 品种代码，如 'RB'
    multiplier: int        # 合约乘数，如螺纹钢=10，沪深300=300
    price_tick: float      # 最小变动价位，如 1.0
    margin_ratio: float     # 保证金比例，如 0.08
    exchange: str = ''     # 交易所：SHFE/DCE/CZCE/CFFEX/INE
    delisted_date: str = ''  # 最后交易日
```

存储在 `AccountManager.__init__` 中：

```python
self._contracts: Dict[str, ContractSpec] = {}
```

提供注册方法：

```python
def register_contract(self, symbol: str, multiplier: int, 
                      margin_ratio: float, price_tick: float = 1.0):
    """策略初始化时注册合约规格"""
```

### 2.2 期货持仓数据结构

股票持仓（不变）：
```python
self.positions = {
    '600000.SH': {'volume': 500, 'cost_price': 10.5},
}
```

期货持仓（新增字段）：
```python
self.positions = {
    'RB2510.SHF': {
        # 多头
        'long_volume': 5,           # 多头总持仓（手）
        'long_volume_today': 3,     # 今日开的多头（区分平今/平昨）
        'long_cost': 3850.0,        # 多头均价
        # 空头
        'short_volume': 0,
        'short_volume_today': 0,
        'short_cost': 0.0,
        # 品种元标记
        'sec_type': 'future',
    }
}
```

> **设计决策：同一品种的多空共存。** 期货可以同时持有多头和空头（锁仓），这与股票完全不同。

### 2.3 账户状态扩展

新增实例变量（AccountManager.__init__）：

```python
self.frozen = 0.0           # 冻结资金（市价单暂未用，为条件单预留）
self.float_pnl = 0.0        # 总浮动盈亏（每次 snapshot 时重新计算）
```

### 2.4 fee_config 合约级覆盖

期货费率和股票不同——按手收费、无印花税。扩展 fee_config 增加 `per_symbol` 子表：

```python
self.fee_config = {
    'commission_rate': 0.0003,   # 股票默认佣金率
    'stamp_tax_rate': 0.001,     # 印花税（仅股票）
    'min_commission': 5.0,       # 最低佣金

    # 期货合约级费率覆盖
    'per_symbol': {
        'RB2510.SHF': {
            'commission_mode': 'per_lot',    # per_lot(按手) | per_value(按成交额)
            'commission_per_lot': 3.0,       # 元/手
            'open_commission_rate': 0.0001,  # 开仓手续费率
            'close_commission_rate': 0.0001, # 平仓手续费率
            'close_today_rate': 0.0001,      # 平今仓手续费率（部分品种平今贵）
        }
    }
}
```

---

## 三、改造点清单（AccountManager 主体）

### 3.1 品种识别

`symbol_classifier.py` 新增：

```python
SEC_TYPE_FUTURE = 'future'

# 后缀规则新增
SYMBOL_TYPE_RULES.append(
    {'suffix': ('.SHF', '.DCE', '.ZCE', '.CFE', '.INE'), 'type': 'future'},
)
```

`AccountManager` 新增内部方法：

```python
def _is_future(self, symbol: str) -> bool:
    return classify_symbol(symbol) == 'future'

def _get_product_code(self, symbol: str) -> str:
    """从合约代码提取品种代码，如 'RB2510.SHF' → 'RB'"""
    import re
    m = re.match(r'^([A-Za-z]+)', symbol)
    return m.group(1).upper() if m else symbol
```

### 3.2 交易单位

`_get_lot_size()` 扩展一行：

```python
def _get_lot_size(self, symbol: str) -> float:
    if self.fee_config.get('lot_size') is not None:
        return self.fee_config['lot_size']
    sec_type = classify_symbol(symbol)
    if sec_type in ('stock', 'etf'):
        return 100
    if sec_type == 'index':
        return 1
    if sec_type == 'future':    # ← 新增
        return 1                # 期货 1 手 = 1 张
    return 0.1
```

### 3.3 保证金计算

新增私有方法：

```python
def _calc_margin(self, symbol: str, price: float, volume: int) -> float:
    """计算开仓所需保证金"""
    spec = self._contracts.get(symbol)
    if spec is None:
        raise ValueError(f"合约 {symbol} 未注册规格，请先调用 register_contract()")
    return price * spec.multiplier * spec.margin_ratio * volume

def _get_used_margin(self) -> float:
    """计算当前所有期货持仓的已用保证金"""
    total = 0.0
    for symbol, pos in self.positions.items():
        if pos.get('sec_type') != 'future':
            continue
        spec = self._contracts.get(symbol)
        if spec is None:
            continue
        price = self._get_price(symbol)
        long_val = pos.get('long_volume', 0) * price * spec.multiplier
        short_val = pos.get('short_volume', 0) * price * spec.multiplier
        total += (long_val + short_val) * spec.margin_ratio
    return round(total, 2)

def _get_available_cash(self) -> float:
    """可用资金 = 现金 - 已用保证金 - 冻结"""
    return round(self.cash - self._get_used_margin() - self.frozen, 2)
```

### 3.4 费率计算（期货路径）

新增私有方法：

```python
def _calc_future_commission(self, symbol: str, price: float, volume: int,
                             side: int, position_effect: int) -> float:
    """计算期货手续费"""
    ps = self.fee_config.get('per_symbol', {}).get(symbol)
    if ps is None:
        # 无合约配置，走默认
        return max(
            round(price * volume * self.fee_config['commission_rate'], 2),
            self.fee_config['min_commission']
        )

    mode = ps.get('commission_mode', 'per_value')
    
    if mode == 'per_lot':
        # 按手收费：每手固定金额
        rate = ps.get('commission_per_lot', 3.0)
        # 部分品种平今仓费率不同
        if position_effect in (PositionEffect.Close, PositionEffect.CloseToday):
            rate = ps.get('close_today_rate', rate)
        return round(rate * volume, 2)
    else:
        # 按成交额收费
        contract_value = price * self._contracts[symbol].multiplier * volume
        if position_effect == PositionEffect.Open:
            rate = ps.get('open_commission_rate', 0.0001)
        else:
            rate = ps.get('close_commission_rate', 0.0001)
        return max(round(contract_value * rate, 2), ps.get('min_commission', 0))
```

### 3.5 开平仓合法性校验（核心）

```python
# 类常量：期货下单合法性矩阵
FUTURE_ORDER_MATRIX = {
    # (side, position_effect) → (操作语义, 需要持仓条件, 扣减方向)
    (OrderSide.Buy,  PositionEffect.Open):           ("开多", None, 'long'),
    (OrderSide.Sell, PositionEffect.Close):          ("平多", 'long', 'long'),
    (OrderSide.Sell, PositionEffect.CloseToday):     ("平今多", 'long_today', 'long'),
    (OrderSide.Sell, PositionEffect.CloseYesterday): ("平昨多", 'long_yesterday', 'long'),
    (OrderSide.Sell, PositionEffect.Open):           ("开空", None, 'short'),
    (OrderSide.Buy,  PositionEffect.Close):          ("平空", 'short', 'short'),
    (OrderSide.Buy,  PositionEffect.CloseToday):     ("平今空", 'short_today', 'short'),
    (OrderSide.Buy,  PositionEffect.CloseYesterday): ("平昨空", 'short_yesterday', 'short'),
}

def _validate_future_order(self, symbol: str, volume: int, side: int,
                            position_effect: int) -> str:
    """
    校验期货下单合法性，返回 None 表示通过，否则返回错误描述

    校验项：
    1. side + position_effect 是否为有效组合
    2. 平仓时持仓是否充足
    3. 合约是否已注册规格
    """
    key = (side, position_effect)
    rule = self.FUTURE_ORDER_MATRIX.get(key)
    if rule is None:
        return f"无效的期货下单组合: side={side}, position_effect={position_effect}"

    semantic, required, direction = rule

    # 检查合约注册
    if symbol not in self._contracts:
        return f"合约 {symbol} 未注册规格"

    # 开仓 → 无需检查持仓
    if required is None:
        return None

    # 平仓 → 检查持仓
    pos = self.positions.get(symbol, {})
    
    if required == 'long':
        total = pos.get('long_volume', 0)
    elif required == 'long_today':
        total = pos.get('long_volume_today', 0)
    elif required == 'long_yesterday':
        today = pos.get('long_volume_today', 0)
        total = pos.get('long_volume', 0) - today
    elif required == 'short':
        total = pos.get('short_volume', 0)
    elif required == 'short_today':
        total = pos.get('short_volume_today', 0)
    elif required == 'short_yesterday':
        today = pos.get('short_volume_today', 0)
        total = pos.get('short_volume', 0) - today
    else:
        total = 0

    if total < volume:
        return f"平仓不足: 需要 {volume} 手, 可平 {total} 手 ({semantic})"

    return None
```

### 3.6 order_volume() 改造

在现有方法中加入品种分叉：

```python
def order_volume(self, symbol, volume, side, position_effect=PositionEffect.Open,
                 order_type=OrderType.Limit, price=None, note=''):
    # ... 现有验证代码不变 ...
    
    if self._is_future(symbol):
        # ── 期货路径 ──
        error = self._validate_future_order(symbol, volume, side, position_effect)
        if error:
            print(f"订单失败: {error}")
            return ''
        return self._process_future_order(symbol, volume, side, position_effect,
                                          order_type, price, note)
    else:
        # ── 股票路径（原逻辑零改动）──
        return self._process_order(symbol, volume, side, position_effect,
                                   order_type, price, order_id, note)
```

### 3.7 _process_future_order() — 期货订单执行（核心新方法）

```python
def _process_future_order(self, symbol: str, volume: int, side: int,
                           position_effect: int, order_type: int,
                           price: float, note: str = '') -> int:
    """
    执行期货订单：
    1. 计算保证金（开仓）/ 释放保证金（平仓）
    2. 验资
    3. 计算手续费
    4. 资金变动：开仓=冻结保证金+扣手续费，平仓=释放保证金+盈亏结算
    5. 更新双向持仓
    6. 记录 TradeRecord
    """
    spec = self._contracts[symbol]
    contract_value = price * spec.multiplier   # 每手合约价值
    
    # ── 手续费 ──
    commission = self._calc_future_commission(symbol, price, volume, side, position_effect)
    
    # ── 开仓 ──
    if position_effect == PositionEffect.Open:
        margin_required = self._calc_margin(symbol, price, volume)
        available = self._get_available_cash()
        
        if available < margin_required + commission:
            print(f"期货开仓失败: 需要保证金 {margin_required:.0f}+手续费 {commission}, "
                  f"可用 {available:.0f}")
            return 0
        
        # 扣减：开仓只冻结保证金，不扣全额（期货是杠杆）
        # 简化处理：现金 - 保证金 - 手续费
        self.cash = round(self.cash - margin_required - commission, 2)
        
        # 更新持仓
        self._update_future_position(symbol, volume, price, side, position_effect)
    
    # ── 平仓 ──
    else:
        # 计算释放的保证金
        margin_released = self._calc_margin(symbol, price, volume)
        
        # 计算平仓盈亏（以持仓均价为准）
        pos = self.positions.get(symbol, {})
        if side == OrderSide.Sell:
            # 平多：盈亏 = (现价 - 成本) × 乘数 × 手数
            cost = pos.get('long_cost', price)
            pnl = (price - cost) * spec.multiplier * volume
        else:
            # 平空：盈亏 = (成本 - 现价) × 乘数 × 手数
            cost = pos.get('short_cost', price)
            pnl = (cost - price) * spec.multiplier * volume
        
        # 现金变动：释放保证金 + 平仓盈亏 - 手续费
        self.cash = round(self.cash + margin_released + pnl - commission, 2)
        
        # 更新持仓
        self._update_future_position(symbol, volume, price, side, position_effect)
    
    # ── 记录 TradeRecord ──
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
        amount=contract_value * volume,
        note=note,
    ))
    return volume
```

### 3.8 _update_future_position() — 期货持仓更新

```python
def _update_future_position(self, symbol: str, volume: int, price: float,
                             side: int, position_effect: int):
    """
    更新期货双向持仓

    逻辑：
    - Buy + Open  → long_volume ↑, long_volume_today ↑
    - Sell + Close → long_volume ↓ (FIFO: 先减今仓再减昨仓)
    - Sell + Open  → short_volume ↑, short_volume_today ↑
    - Buy + Close  → short_volume ↓
    """
    pos = self.positions.get(symbol, {
        'long_volume': 0, 'long_volume_today': 0, 'long_cost': 0.0,
        'short_volume': 0, 'short_volume_today': 0, 'short_cost': 0.0,
        'sec_type': 'future',
    })

    key = (side, position_effect)
    
    if key == (OrderSide.Buy, PositionEffect.Open):
        # 开多：均价法更新
        old_vol = pos['long_volume']
        old_cost = pos['long_cost']
        new_vol = old_vol + volume
        pos['long_cost'] = ((old_cost * old_vol + price * volume) / new_vol
                            if new_vol > 0 else 0.0)
        pos['long_volume'] = new_vol
        pos['long_volume_today'] += volume

    elif key == (OrderSide.Sell, PositionEffect.Close):
        # 平多：FIFO 先平今仓
        today = min(pos['long_volume_today'], volume)
        remaining = volume - today
        pos['long_volume_today'] -= today
        pos['long_volume'] -= volume

    elif key == (OrderSide.Sell, PositionEffect.CloseToday):
        pos['long_volume_today'] -= volume
        pos['long_volume'] -= volume

    elif key == (OrderSide.Sell, PositionEffect.CloseYesterday):
        pos['long_volume'] -= volume
        # long_volume_today 不变

    elif key == (OrderSide.Sell, PositionEffect.Open):
        # 开空：均价法
        old_vol = pos['short_volume']
        old_cost = pos['short_cost']
        new_vol = old_vol + volume
        pos['short_cost'] = ((old_cost * old_vol + price * volume) / new_vol
                             if new_vol > 0 else 0.0)
        pos['short_volume'] = new_vol
        pos['short_volume_today'] += volume

    elif key == (OrderSide.Buy, PositionEffect.Close):
        # 平空
        today = min(pos['short_volume_today'], volume)
        remaining = volume - today
        pos['short_volume_today'] -= today
        pos['short_volume'] -= volume

    elif key == (OrderSide.Buy, PositionEffect.CloseToday):
        pos['short_volume_today'] -= volume
        pos['short_volume'] -= volume

    elif key == (OrderSide.Buy, PositionEffect.CloseYesterday):
        pos['short_volume'] -= volume

    # 清理零持仓
    if pos['long_volume'] == 0 and pos['short_volume'] == 0:
        self.positions.pop(symbol, None)
    else:
        self.positions[symbol] = pos
```

---

## 四、新增上层下单接口

对标 GM 的 `order_target_*` 系列，期货策略应使用 `position_side` (Long/Short) 而非 `side` (Buy/Sell)：

### 4.1 order_target_long / order_target_short

```python
def order_target_long(self, symbol: str, target_lots: int,
                      order_type: int = OrderType.Market,
                      price: float = None, note: str = '') -> str:
    """
    目标多头持仓 N 手。自动计算差量 → 开多 or 平多 or 平空后开多。

    Args:
        symbol: 合约代码
        target_lots: 目标多头手数 (>= 0)
    """
    pos = self.positions.get(symbol, {'long_volume': 0, 'short_volume': 0})
    current = pos.get('long_volume', 0)
    delta = target_lots - current
    
    if delta > 0:
        # 加多仓
        # 先检查是否有空仓：有空仓则先平空再开多
        short_vol = pos.get('short_volume', 0)
        if short_vol > 0:
            self.order_volume(symbol, short_vol, OrderSide.Buy,
                            PositionEffect.Close, order_type, price,
                            note + ' (平空)')
        if delta > 0:
            return self.order_volume(symbol, delta, OrderSide.Buy,
                                     PositionEffect.Open, order_type, price, note)
    elif delta < 0:
        # 减多仓
        return self.order_volume(symbol, -delta, OrderSide.Sell,
                                 PositionEffect.Close, order_type, price, note)
    return ''


def order_target_short(self, symbol: str, target_lots: int,
                       order_type: int = OrderType.Market,
                       price: float = None, note: str = '') -> str:
    """目标空头持仓 N 手，同 order_target_long 的镜像"""
    pos = self.positions.get(symbol, {'long_volume': 0, 'short_volume': 0})
    current = pos.get('short_volume', 0)
    delta = target_lots - current
    
    if delta > 0:
        # 先平多再开空
        long_vol = pos.get('long_volume', 0)
        if long_vol > 0:
            self.order_volume(symbol, long_vol, OrderSide.Sell,
                            PositionEffect.Close, order_type, price,
                            note + ' (平多)')
        if delta > 0:
            return self.order_volume(symbol, delta, OrderSide.Sell,
                                     PositionEffect.Open, order_type, price, note)
    elif delta < 0:
        return self.order_volume(symbol, -delta, OrderSide.Buy,
                                 PositionEffect.Close, order_type, price, note)
    return ''


def order_target(self, symbol: str, long_lots: int, short_lots: int,
                 order_type: int = OrderType.Market,
                 price: float = None, note: str = '') -> str:
    """同时设定多空目标，先调空再调多（避免锁仓）"""
    self.order_target_short(symbol, short_lots, order_type, price, note)
    return self.order_target_long(symbol, long_lots, order_type, price, note)
```

### 4.2 order_percent 的期货适配

期货的 `order_percent` 应基于**可用资金**而非总权益计算：

```python
# 在 order_percent 开头加入期货判断
def order_percent(self, symbol, percent, side, position_effect=PositionEffect.Open,
                  order_type=OrderType.Limit, price=None, note=''):
    if not 0 < abs(percent) <= 1:
        raise ValueError("Percent must be between -1 and 1 (non-zero)")

    account_info = self.get_account()
    nav = account_info['nav']

    if self._is_future(symbol):
        # 期货：基于可用资金 × percent 计算手数
        available = self._get_available_cash()
        order_amount = available * abs(percent)
        price = price or self._get_price(symbol)
        spec = self._contracts[symbol]
        margin_per_lot = price * spec.multiplier * spec.margin_ratio
        volume = int(order_amount / margin_per_lot)
        if volume == 0:
            raise ValueError("Calculated order volume is zero")
        return self.order_volume(symbol, volume, side, position_effect,
                                 order_type, price, note)

    # ── 股票原逻辑不变 ──
    ...
```

---

## 五、快照扩展

### 5.1 AccountSnapshot 扩展

```python
@dataclass
class AccountSnapshot:
    cash: float
    nav: float
    created_at: datetime
    positions: Dict[str, PositionSnapshot] = field(default_factory=dict)
    # [新增] 期货专用字段
    margin_used: float = 0.0       # 已用保证金
    float_pnl: float = 0.0         # 浮动盈亏
```

### 5.2 take_snapshot() 改造

```python
def take_snapshot(self, created_at: datetime = None) -> AccountSnapshot:
    if created_at is None:
        created_at = context.now

    pos_snapshots = {}
    total_assets = self.cash
    total_float_pnl = 0.0
    
    for symbol, pos in self.positions.items():
        try:
            price = self._get_price(symbol)
        except (ValueError, KeyError):
            continue
        if price <= 0:
            continue
        
        # 期货多空分别估值
        if pos.get('sec_type') == 'future':
            spec = self._contracts.get(symbol)
            if spec is None:
                continue
            
            long_vol = pos.get('long_volume', 0)
            short_vol = pos.get('short_volume', 0)
            long_cost = pos.get('long_cost', 0)
            short_cost = pos.get('short_cost', 0)
            
            # 多头市值 + 空头市值 = 总持仓价值
            long_value = long_vol * price * spec.multiplier
            short_value = short_vol * price * spec.multiplier
            
            # 浮动盈亏
            if long_vol > 0:
                total_float_pnl += (price - long_cost) * spec.multiplier * long_vol
            if short_vol > 0:
                total_float_pnl += (short_cost - price) * spec.multiplier * short_vol
            
            pos_snap = PositionSnapshot(
                symbol=symbol,
                volume=long_vol + short_vol,   # 简化：多空总量
                cost_price=0,
                price=price,
                created_at=created_at,
            )
            total_assets += long_value + short_value
        else:
            # 股票原逻辑
            pos_snap = PositionSnapshot(
                symbol=symbol,
                volume=pos['volume'],
                cost_price=round(pos['cost_price'], 3),
                price=price,
                created_at=created_at,
            )
            total_assets += pos['volume'] * price
        
        pos_snapshots[symbol] = pos_snap

    total_assets = round(total_assets, 2)
    margin_used = self._get_used_margin()
    
    snapshot = AccountSnapshot(
        cash=self.cash,
        nav=total_assets,
        created_at=created_at,
        positions=pos_snapshots,
        margin_used=margin_used,
        float_pnl=round(total_float_pnl, 2),
    )
    self.snapshots.append(snapshot)
    return snapshot
```

---

## 六、查询接口扩展

### 6.1 get_account()

```python
def get_account(self, query_time=None):
    # ... 现有逻辑 ...
    base = {
        'cash': snapshot.cash,
        'nav': snapshot.nav,
        'created_at': snapshot.created_at,
    }
    # [新增] 期货专用字段
    base['available'] = self._get_available_cash()
    base['margin_used'] = getattr(snapshot, 'margin_used', 0)
    base['float_pnl'] = getattr(snapshot, 'float_pnl', 0)
    base['risk_ratio'] = (base['margin_used'] / base['nav']
                          if base['nav'] > 0 else 0)
    return base
```

### 6.2 get_position()

```python
def get_position(self, symbol=None):
    # 期货持仓：返回多空分列
    if symbol and self._is_future(symbol):
        pos = self.positions.get(symbol, {})
        if pos.get('sec_type') == 'future':
            return {
                'long_volume': pos.get('long_volume', 0),
                'long_volume_today': pos.get('long_volume_today', 0),
                'long_cost': pos.get('long_cost', 0),
                'short_volume': pos.get('short_volume', 0),
                'short_volume_today': pos.get('short_volume_today', 0),
                'short_cost': pos.get('short_cost', 0),
                'sec_type': 'future',
            }
    # 股票原逻辑
    ...
```

---

## 七、FastAccount 同步改造

FastAccount 同样需要支持期货，但保持轻量。改动点与 AccountManager 对齐，无 TradeRecord 路径：

```python
class FastAccount:
    # 现有 fields 不变
    # 新增:
    _contracts: dict           # symbol → (multiplier, margin_ratio)
    _pos_cost: dict            # symbol → {long_cost, short_cost}
    
    def _is_future(self, symbol): ...
    def register_contract(self, ...): ...
    def _calc_margin(self, ...): ...
    def _get_available_cash(self): ...
    
    def _process_order(self, ...):
        if self._is_future(symbol):
            return self._process_future_order(...)
        # 原逻辑
```

---

## 八、懒加载合约规格（兼容性最好）

不改动 `Engine.add_data()`，合约规格通过策略侧注册：

```python
# 策略 on_init / on_bar 首次执行时
def on_init(self, context):
    context.account.register_contract('RB2510.SHF', 
        multiplier=10, margin_ratio=0.08, price_tick=1.0)
    context.account.register_contract('I2509.DCE',
        multiplier=100, margin_ratio=0.12, price_tick=0.5)
```

也可以支持从 fee_config 导入：

```python
engine = Engine()
engine.account.fee_config['contracts'] = {
    'RB2510.SHF': {'multiplier': 10, 'margin_ratio': 0.08, 'price_tick': 1.0},
    'I2509.DCE':  {'multiplier': 100, 'margin_ratio': 0.12, 'price_tick': 0.5},
}
```

在 `order_volume()` 首次遇到时自动注册：

```python
if symbol not in self._contracts:
    cfg = self.fee_config.get('contracts', {}).get(symbol)
    if cfg:
        self.register_contract(symbol, **cfg)
```

---

## 九、AccountAnalyzer 新增指标

```python
# 新增 @metric（仅期货账户有数据时生效）

@metric('max_leverage', '最大杠杆倍数')
def _max_leverage(self):
    """nav / available 的最大值"""
    ...

@metric('avg_margin_usage', '平均保证金占用率')
def _avg_margin_usage(self):
    """margin_used / nav 的均值"""
    ...

@metric('float_pnl_ratio', '浮动盈亏/权益')
def _float_pnl_ratio(self):
    ...
```

---

## 十、改动汇总

| 文件 | 新增行数 | 修改行数 | 说明 |
|------|:--------:|:--------:|------|
| `symbol_classifier.py` | +5 | 0 | SEC_TYPE_FUTURE + 后缀规则 |
| `account.py` | +~350 | ~20 | 核心改造全集中于此 |
| ├ `ContractSpec` dataclass | +15 | 0 | 新增 |
| ├ `register_contract()` | +15 | 0 | 新增 |
| ├ `_is_future()` | +3 | 0 | 新增 |
| ├ `_calc_margin()` | +10 | 0 | 新增 |
| ├ `_get_used_margin()` | +20 | 0 | 新增 |
| ├ `_get_available_cash()` | +5 | 0 | 新增 |
| ├ `_calc_future_commission()` | +30 | 0 | 新增 |
| ├ `_validate_future_order()` | +45 | 0 | 新增 |
| ├ `_process_future_order()` | +70 | 0 | 新增 |
| ├ `_update_future_position()` | +60 | 0 | 新增 |
| ├ `order_target_long/short/target()` | +50 | 0 | 新增 |
| ├ `order_volume()` | +8 | 0 | 品种分叉 |
| ├ `order_percent()` | +15 | 0 | 期货路径 |
| ├ `take_snapshot()` | +15 | +5 | 期货估值 |
| ├ `get_account()` | +5 | 0 | 保证金字段 |
| ├ `get_position()` | +12 | 0 | 期货多空返回 |
| ├ `_get_lot_size()` | +2 | 0 | future→1 |
| `analyzer.py` | +30 | 0 | 期货专用指标 |
| `engine.py` | 0 | 0 | 无需改动 |

> 股票路径仅 `order_volume()` 加了一行 `if self._is_future()` 分叉，其余全部是对新方法的调用，**股票回测完全不受影响**。

---

## 十一、典型期货策略示例

```python
from ft2.core import Engine, EngineCore, AccountAnalyzer
from ft2.core.account import OrderSide, PositionEffect, OrderType

class EMATrendFutures:
    """双均线趋势跟踪 — 螺纹钢"""

    def on_init(self, context):
        # 注册合约规格
        context.account.register_contract('RB2510.SHF',
            multiplier=10, margin_ratio=0.08, price_tick=1.0)

    def on_bar(self, context, bars):
        bar = bars[0]
        symbol = bar['symbol']

        # 获取价格数据
        close = context.data(symbol=symbol, frequency='1d',
                            count=50, fields='close')
        ema20 = close['close'].ewm(span=20).mean().iloc[-1]
        ema50 = close['close'].ewm(span=50).mean().iloc[-1]

        # 期货用法：order_target_long/short
        if ema20 > ema50:
            context.account.order_target_long(symbol, 5, note='多头')
        elif ema20 < ema50:
            context.account.order_target_short(symbol, 3, note='空头')
        else:
            context.account.order_target(symbol, long_lots=0, short_lots=0, note='清仓')
```
