# AccountManager 统一持仓模型（对齐掘金 myquant.cn）— 重构方案

> **目标：深度 B —— 彻底统一持仓模型为 `(symbol, side) → Position`，股票/期货共用一张持仓表，逐字段对齐掘金 `Position` 回报模型。**
>
> 现状（已落地 V2）：`_OrderMixin` + `FuturePosition`（一对象双向），字段命名已对齐（`balance/vwap/fpnl/used_bail/filled_commission`），但持仓仍是"一 symbol 一对象含多空"，产生 `long_vwap` 这类自创名。

---

## 一、演进脉络

| 版本 | 持仓模型 | 状态 |
|---|---|---|
| V1 设计稿 | 裸 dict 双向（`{'long_volume','long_cost',...}`） | 已废弃（本文档重写前的旧稿） |
| V2 已实现 | `FuturePosition` 一对象双向（`long_vwap/short_vwap`） | ✅ 当前代码 |
| **V3 目标（深度 B）** | **`Position` 单方向对象，`(symbol, side)` 统一表** | 本文档方案 |

**V3 要解决的问题**：
1. `long_vwap/short_vwap` 是自创命名——掘金只有 `vwap`（方向靠 `side` 字段）；
2. 持仓方向逻辑散在字段前缀里，而非对象内聚；
3. 股票/期货两套持仓结构（dict vs FuturePosition），查询/快照都要 `isinstance` 分支。

---

## 二、掘金持仓架构参考（本地 gm 源码实证）

### 2.1 统一持仓表（核心架构）

```python
# gm/model/account.py（本地 gm 3.0.186 源码）
class Account:
    # 这里的 inside_positions 是个字典, 用 symbol.side 作为key, value为Position的属性展开的字典
    self.inside_positions = positions  # Dict[Tuple[Text, int, int], Dict[Text, Any]]
    #                                                       ↑ (symbol, side, covered_flag)
    def position(self, symbol, side, covered_flag=0):        # 单查，side 必传
        return self.inside_positions.get((symbol, side, covered_flag))
```

**关键设计**：股票/期货/期权**共用一张持仓表**，维度 `(symbol, side, covered_flag)`：

| 品种 | side | covered_flag |
|---|---|---|
| 股票 | `Long(1)`（恒多头） | 0 |
| 期货 | `Long(1)` / `Short(2)` | 0 |
| 期权 | Long/Short + 备兑 | 0/1 |

### 2.2 Position 对象（gm protobuf 回报字段）

```
symbol / side / volume / volume_today / vwap / fpnl / market_value /
available / order_frozen / last_price / cost / amount / created_at ...
```

- `vwap`：加权开仓均价 `Σ(价×量)/Σ量`，**不含手续费**，加仓加权更新、平仓不变；
- `volume_today`：今仓（期货平今/平昨依据；股票=当日买入）；
- `fpnl`：浮动盈亏，按 `side` 方向计算（多头 `(price-vwap)`，空头 `(vwap-price)`）。

### 2.3 回测引擎架构（run() 集中配置）

```python
# gm/api/basic.py run(mode=MODE_BACKTEST, ...)
py_gmi_set_backtest_config(
    start_time, end_time, initial_cash,
    transaction_ratio,          # 成交比例（流动性模拟）
    commission_ratio, commission_unit, slippage_ratio,
    option_float_margin_ratio1, # ← 期货保证金分级①：距到期日 >2 天
    option_float_margin_ratio2, # ← 期货保证金分级②：距到期日 ≤2 天
    adjust,                     # 复权：NONE/POST/PREV
    match_mode,                 # 撮合模式
)
py_gmi_run()                    # gmsdk.dll C 引擎：数据回放+撮合+账务+持仓
```

**值得参考**：#2 **期货保证金按到期日分级**（`marginfloat_ratio1/2`）——临近交割保证金上调，直接落在 `ContractSpec` 上（见 §4.4）。

---

## 三、V3 统一持仓设计（深度 B）

### 3.1 统一持仓对象 `Position`（单方向）

```python
@dataclass
class Position:
    """统一持仓对象 — 对齐掘金 gm Position（股票/期货通用）

    字段与 gm Position 回报一致：symbol/side/volume/volume_today/vwap/fpnl
    """
    symbol: str
    side: int                        # PositionSide.Long / Short（股票恒 Long）
    volume: int = 0
    volume_today: int = 0            # 今仓（期货平今依据；股票=当日开仓）
    vwap: float = 0.0                # 加权开仓均价（对齐 Position.vwap，不含手续费）

    def is_empty(self) -> bool:
        return self.volume == 0

    def open(self, volume: int, price: float):
        """开仓：加权 vwap，今仓同步增加"""
        new_vol = self.volume + volume
        self.vwap = ((self.vwap * self.volume + price * volume) / new_vol
                     if new_vol > 0 else 0.0)
        self.volume = new_vol
        self.volume_today += volume

    def close(self, volume: int, today_volume: int = None):
        """平仓：today_volume=None → FIFO 先平今；CloseToday 传=volume；CloseYesterday 传=0"""
        if today_volume is None:
            today_volume = min(self.volume_today, volume)
        self.volume_today -= today_volume
        self.volume -= volume

    def fpnl(self, price: float, multiplier: int = 1) -> float:
        """浮动盈亏：多头 (price-vwap)，空头 (vwap-price) × 乘数 × 手数"""
        if self.side == PositionSide.Long:
            return (price - self.vwap) * multiplier * self.volume
        return (self.vwap - price) * multiplier * self.volume

    def used_bail(self, price: float, multiplier: int, margin_ratio: float) -> float:
        """已用保证金 = 持仓市值 × 保证金率（股票无保证金，调用方传 0 费率）"""
        return self.volume * price * multiplier * margin_ratio

    def to_dict(self) -> Dict:
        """get_position 对外输出（键名对齐 gm Position 回报）"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'volume': self.volume,
            'volume_today': self.volume_today,
            'vwap': round(self.vwap, 3),
        }
```

### 3.2 统一持仓表

```python
# AccountManager / FastAccount
self.positions: Dict[Tuple[str, int], Position] = {}
#     key = (symbol, side)
#     股票：('600000.SH', PositionSide.Long) → Position
#     期货多：('RB2510.SHF', PositionSide.Long)
#     期货空：('RB2510.SHF', PositionSide.Short)
```

> **与掘金差异**：掘金键是 `(symbol, side, covered_flag)` 三元组（期权备兑用），ft2 回测不涉及期权，用 `(symbol, side)` 二元组即可。

### 3.3 账务模型（沿用做法 B，已验证）

```
balance   = 账面资金（对齐 Cash.balance；初始 + 已实现盈亏 - 手续费），保证金不从此扣减
used_bail = 已用保证金（对齐 Cash.used_bail；遍历持仓动态计算）
fpnl      = 未平仓浮动盈亏（对齐 Cash.fpnl；按现价重估）
available = balance - used_bail - frozen
nav       = balance + fpnl   ← 真实权益（保证金只是占用，仍在 balance 内）

开仓：校验 available ≥ 保证金+手续费 → balance -= 手续费 → 持仓增加（used_bail 自动上升）
平仓：balance += 平仓盈亏 - 手续费 → 持仓减少（used_bail 自动下降）
```

### 3.4 保证金分级（参考掘金 marginfloat_ratio1/2）

```python
@dataclass
class ContractSpec:
    symbol: str
    multiplier: int
    margin_ratio: float               # 基准保证金率
    margin_ratio_near: float = None   # [参考掘金] 临近交割(距最后交易日≤2个交易日)保证金上浮率
    price_tick: float = 1.0
    exchange: str = ''
    delisted_date: str = ''           # 最后交易日（引擎据此计算剩余交易日）

    def effective_margin_ratio(self, remaining_days: int) -> float:
        """按剩余交易日动态选择保证金率（对齐掘金 marginfloat_ratio1/2 分级思想）
        remaining_days ≤ 2 → margin_ratio_near（上浮）；否则 → margin_ratio"""
        if self.margin_ratio_near and remaining_days <= 2:
            return self.margin_ratio_near
        return self.margin_ratio
```

---

## 四、改造点清单（V3 深度 B）

| # | 方法/位置 | V2 现状 | V3 目标 |
|---|---|---|---|
| 1 | `_update_future_position` | `positions[symbol]` 一对象双向 | `positions[(symbol, side)]` 单方向 `open/close` |
| 2 | `_process_order`（股票） | `positions[symbol]` dict | `positions[(symbol, Long)]` Position |
| 3 | `_validate_future_order` | 读 `long_volume/long_volume_today` | 读 `positions[(symbol, side)].volume/volume_today` |
| 4 | `_process_future_order`（平仓盈亏） | `pos.long_vwap/short_vwap` | `pos.vwap`（side 内聚） |
| 5 | `_get_used_margin` | `isinstance(FuturePosition)` 分支 | 遍历全部 `Position`，期货 side 用 `used_bail()` |
| 6 | `take_snapshot` | 期货/股票 `isinstance` 分支 | 统一遍历 `Position.fpnl()`；股票 multiplier=1 |
| 7 | `get_position` | 期货返回多空分列 dict | **对齐掘金**：`(symbol=None, side=None)` 返回 Position dict **列表** |
| 8 | `order_target_volume/value/percent` | 读 `long_volume/short_volume` | 读 `positions[(symbol, Long/Short)]` |
| 9 | `FastAccount` | 同步 V2 | 同步 V3（同一张 `positions[(symbol, side)]` 表） |
| 10 | `analyzer._calculate_profit` | 纯股票 FIFO（期货缺口） | 按 `position_effect + side` 分支（**顺带补上遗留缺口**） |

### 4.1 get_position() 对齐掘金

```python
def get_position(self, symbol: str = None, side: int = None) -> List[Dict]:
    """对齐掘金 gm get_position()：返回 Position dict 列表（非 dict）
    调用方：iter_positions() 遍历全部；get_position(symbol) 过滤单合约；get_position(symbol, side) 过滤方向"""
```

**兼容策略**（signals/factor/pms 共 15 处调用方，当前只读 `pos['volume']`/取真值）：
- 内部改造为列表后，对外可保留一层兼容包装（按 `{symbol: {...}}` 汇总），或同步改造 15 处调用方（推荐，收益是彻底一致）。

### 4.2 股票统一进 `(symbol, side)` 表的影响

- `PositionSnapshot`（快照）字段 `vwap` 已对齐，只需把 `(symbol, side)` 合并展示；
- `analyzer` 主要消费 `trade_records` + `snapshots`，持仓表改造对其影响集中在 `_calculate_profit`（顺带修复期货盈亏）；
- 股票 `positions[symbol]['volume']` 的访问点：`order_percent` Sell、`get_position`、`take_snapshot`、`_process_order` 共 4 处，全部改为 `(symbol, Long)` 索引。

---

## 五、掘金回测架构参考（后续增强，非本次范围）

| 参考点 | 掘金 | ft2 落地建议 | 优先级 |
|---|---|---|---|
| 回测配置集中 | `run()` 全参数 | 提炼 `BacktestConfig`（时间/资金/佣金/滑点/保证金/撮合） | 中 |
| 保证金分级 | `marginfloat_ratio1/2` | `ContractSpec.margin_ratio_near`（§3.4） | **高（本次纳入）** |
| 撮合模式/成交比例 | `match_mode` / `transaction_ratio` | 滑点/成交比例可扩展进 `fee_config` | 低 |
| 参数校验前置 | `run()` 入口范围校验 | `Engine.backtest()` 入口统一校验 | 低 |

---

## 六、实施步骤（V3 深度 B）

1. **新增 `Position` 单方向对象**（§3.1），替换 `FuturePosition`（双向 → 单方向，字段 `volume/volume_today/vwap` 无前缀）；
2. **持仓表改 `(symbol, side)` 键**（§3.2），股票/期货统一；`FuturePosition` 删除；
3. **改造 10 个方法**（§4 表）——持仓读写全部走 `(symbol, side)` 索引；
4. **`ContractSpec` 增加 `margin_ratio_near` 分级**（§3.4），`_calc_margin`/`_get_used_margin` 按剩余交易日选费率；
5. **`get_position()` 对齐掘金返回列表** + 同步 15 处调用方；
6. **`analyzer._calculate_profit` 期货盈亏**（补遗留缺口，§4#10）；
7. 冒烟测试（`tmp/test_futures_smoke.py`）全量更新，新增：股票 `(symbol, Long)` 回归、保证金分级、get_position 列表格式断言；
8. 端到端 full/fast 双路径验证（SR 差异 = 0）。

---

## 七、验证矩阵

| 场景 | 断言 |
|---|---|
| 股票开/平仓 | `positions[('600000.SH', Long)].volume` 正确，`vwap` 加权 |
| 期货开多/开空 | 两方向独立 Position，`vwap` 各自加权 |
| 平今/平昨 | `volume_today` FIFO 扣减 |
| 保证金分级 | `remaining_days≤2` 用 `margin_ratio_near` |
| 快照估值 | `nav = balance + Σfpnl`（多空分别） |
| full/fast 一致 | 双路径 SR 差异 = 0 |
| 命名 | 无 `long_/short_` 前缀字段、无 `cost_price`、无 `float_pnl` |
