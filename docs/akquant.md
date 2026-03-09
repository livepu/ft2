# AKQuant 框架源码分析

> 分析版本：基于 `d:\programdata\micromamba\envs\py313\lib\site-packages\akquant` 安装包源码
> 分析日期：2026-02-12

---

## 一、架构概览

### 1.1 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Python Layer                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Strategy │  │   Data   │  │    ML    │  │  Risk    │    │
│  │  策略层   │  │  数据层   │  │ 机器学习 │  │  风控    │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │             │             │           │
│  ┌────▼─────────────▼─────────────▼─────────────▼─────┐    │
│  │              Backtest (backtest.py)                │    │
│  │         回测引擎封装 (Rust核心接口)                  │    │
│  └─────────────────────┬───────────────────────────────┘    │
│                        │                                     │
└────────────────────────┼─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                      Rust Core (akquant.pyd)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │    Engine    │  │  DataFeed    │  │   Account    │       │
│  │    撮合引擎   │  │   数据喂送    │  │   账户管理    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 目录结构

```
akquant/
├── __init__.py           # 包入口，导出核心类
├── akquant.pyd           # Rust核心编译的二进制模块
├── akquant.pyi           # Type hints文件
├── backtest.py           # 回测引擎封装
├── strategy.py           # 策略基类
├── data.py               # 数据加载和Catalog
├── indicator.py          # 指标系统
├── ml/                   # 机器学习模块
│   ├── __init__.py
│   └── model.py          # QuantModel适配器
├── gateway/              # 交易网关
│   ├── __init__.py
│   └── ctp.py            # CTP期货接口
├── utils/                # 工具函数
│   ├── __init__.py
│   └── inspector.py      # 代码检查工具
├── config.py             # 配置管理
├── risk.py               # 风控模块
├── sizer.py              # 仓位管理
├── plot.py               # 绘图功能
├── optimize.py           # 参数优化
├── log.py                # 日志系统
└── live.py               # 实盘接口
```

---

## 二、回测引擎流程详解

### 2.1 整体流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           run_backtest() 入口                                │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. 策略实例化                                                                │
│    - isinstance(strategy, type) → strategy()                                │
│    - isinstance(strategy, Strategy) → 直接使用                               │
│    - callable(strategy) → FunctionalStrategy 包装                            │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. 数据准备                                                                  │
│    - DataFrame → prepare_dataframe() → df_to_arrays() → DataFeed           │
│    - Dict[str, DataFrame] → 多标的处理                                       │
│    - List[Bar] → 直接添加                                                    │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. 引擎配置 (Engine - Rust核心)                                              │
│    - set_timezone(offset)                                                   │
│    - set_cash(initial_cash)                                                 │
│    - set_execution_mode(NextOpen/CurrentClose)                              │
│    - set_stock_fee_rules(commission, stamp_tax, transfer_fee, min_commission)│
│    - add_instrument(Instrument)                                             │
│    - add_data(DataFeed)                                                     │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. 指标预计算 (可选)                                                          │
│    - strategy._prepare_indicators(data_map)                                 │
│    - 向量化计算所有指标，存入 Indicator._data                                 │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. 运行回测 engine.run(strategy, show_progress)                              │
│    ┌─────────────────────────────────────────────────────────────────────┐  │
│    │ Rust核心循环:                                                        │  │
│    │ for bar in sorted_bars:                                             │  │
│    │     1. 更新Portfolio价格                                             │  │
│    │     2. 检查止损/止盈订单                                              │  │
│    │     3. 创建StrategyContext                                           │  │
│    │     4. 调用 strategy._on_bar_event(bar, ctx)                        │  │
│    │     5. 处理新订单 (撮合)                                              │  │
│    │     6. 记录快照                                                       │  │
│    └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 6. 返回结果 BacktestResult                                                   │
│    - metrics: PerformanceMetrics                                            │
│    - trades: List[ClosedTrade]                                              │
│    - equity_curve: List[Tuple[timestamp, equity]]                           │
│    - positions_df, trades_df, metrics_df (DataFrame视图)                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心类交互流程

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Strategy   │────▶│StrategyContext│────▶│   Engine     │
│  (Python)    │     │   (Rust)      │     │   (Rust)     │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ on_bar()     │     │ cash         │     │ portfolio    │
│ buy()        │◀────│ positions    │◀────│ orders       │
│ sell()       │     │ history()    │     │ risk_manager │
│ get_history()│     │ buy()        │     │ data_feed    │
└──────────────┘     │ sell()       │     └──────────────┘
                     └──────────────┘
```

### 2.3 订单撮合流程

```
策略调用 buy/sell
        │
        ▼
┌───────────────────┐
│ StrategyContext   │
│ 创建 Order 对象    │
│ 加入 orders 列表   │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ RiskManager       │
│ 检查风控规则       │
│ - 资金是否充足     │
│ - 持仓是否超限     │
│ - 是否在限制列表   │
└─────────┬─────────┘
          │ 通过
          ▼
┌───────────────────┐
│ Engine 撮合        │
│ 根据ExecutionMode │
│ - NextOpen: 下一根Bar开盘价 │
│ - CurrentClose: 当前Bar收盘价 │
│ 计算滑点、手续费    │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Portfolio 更新     │
│ - 更新 cash        │
│ - 更新 positions   │
│ - 创建 Trade 记录  │
└───────────────────┘
```

### 2.4 Rust核心类详解 (akquant.pyi)

#### 2.4.1 Engine 类

```python
class Engine:
    """主回测引擎 (Rust实现)"""
    
    portfolio: Portfolio          # 投资组合
    orders: list[Order]           # 订单列表
    trades: list[Trade]           # 成交列表
    risk_manager: RiskManager     # 风控管理器
    
    # 配置方法
    def set_timezone(self, offset: int) -> None: ...
    def set_cash(self, cash: float) -> None: ...
    def set_execution_mode(self, mode: ExecutionMode) -> None: ...
    def set_t_plus_one(self, enabled: bool) -> None: ...
    def set_stock_fee_rules(self, commission, stamp_tax, transfer_fee, min_commission): ...
    def set_slippage(self, type_: str, value: float) -> None: ...
    
    # 数据和标的
    def add_instrument(self, instrument: Instrument) -> None: ...
    def add_data(self, feed: DataFeed) -> None: ...
    def add_bars(self, bars: Sequence[Bar]) -> None: ...
    
    # 运行
    def run(self, strategy: Any, show_progress: bool) -> str: ...
    def get_results(self) -> BacktestResult: ...
    def create_context(self, active_orders: Sequence[Order]) -> StrategyContext: ...
```

#### 2.4.2 StrategyContext 类

```python
class StrategyContext:
    """策略上下文 (Rust实现，每次on_bar创建)"""
    
    cash: float                           # 当前现金
    positions: dict[str, float]           # 当前持仓
    available_positions: dict[str, float] # 可用持仓
    session: TradingSession               # 当前交易时段
    orders: list[Order]                   # 订单列表
    active_orders: list[Order]            # 活跃订单
    recent_trades: list[Trade]            # 最近成交
    
    # 交易方法
    def buy(self, symbol, quantity, price=None, time_in_force=None, trigger_price=None) -> str: ...
    def sell(self, symbol, quantity, price=None, time_in_force=None, trigger_price=None) -> str: ...
    def cancel_order(self, order_id: str) -> None: ...
    
    # 数据方法
    def history(self, symbol: str, field: str, count: int) -> Optional[ndarray]: ...
    def schedule(self, timestamp: int, payload: str) -> None: ...
```

#### 2.4.3 Portfolio 类

```python
class Portfolio:
    """投资组合管理 (Rust实现)"""
    
    cash: float                      # 现金余额
    positions: dict[str, float]      # 持仓 {symbol: quantity}
    available_positions: dict[str, float]  # 可用持仓
    
    def get_position(self, symbol: str) -> float: ...
    def get_available_position(self, symbol: str) -> float: ...
```

#### 2.4.4 Bar 数据结构

```python
class Bar:
    """K线数据结构"""
    
    timestamp: int           # Unix时间戳 (纳秒)
    symbol: str              # 标的代码
    open: float              # 开盘价
    high: float              # 最高价
    low: float               # 最低价
    close: float             # 收盘价
    volume: float            # 成交量
    extra: dict[str, float]  # 自定义字段 (用于ML特征)
    timestamp_str: str       # 时间字符串 (只读属性)
```

### 2.5 执行模式详解

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `NextOpen` | 信号产生后，下一根Bar开盘价成交 | 日线策略，避免未来函数 |
| `CurrentClose` | 信号产生时，当前Bar收盘价成交 | 分钟线策略，日内交易 |

```python
# NextOpen 示例
# T时刻收盘产生信号，T+1时刻开盘成交
result = run_backtest(
    strategy=MyStrategy,
    data=df,
    execution_mode=ExecutionMode.NextOpen  # 默认
)

# CurrentClose 示例
# T时刻收盘产生信号，T时刻收盘价成交（日内）
result = run_backtest(
    strategy=MyStrategy,
    data=df,
    execution_mode=ExecutionMode.CurrentClose
)
```

---

## 三、核心模块分析

### 3.1 回测引擎 (backtest.py)

#### 2.1.1 BacktestResult 类

回测结果包装器，将Rust返回的原始数据转换为Python友好的DataFrame格式。

**核心属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `metrics` | PerformanceMetrics | 绩效指标原始对象 |
| `metrics_df` | pd.DataFrame | 绩效指标DataFrame |
| `trades` | List[ClosedTrade] | 成交记录列表 |
| `trades_df` | pd.DataFrame | 成交记录DataFrame |
| `orders` | List[Order] | 订单列表 |
| `orders_df` | pd.DataFrame | 订单DataFrame |
| `positions` | pd.DataFrame | 持仓历史 |
| `positions_df` | pd.DataFrame | 详细持仓历史 |

**关键方法：**

```python
# 绘制回测结果
result.plot(symbol='600000', show=True, title='回测结果')

# 获取权益曲线
result.equity_curve  # List[Tuple[timestamp, equity]]

# 获取交易统计
trade_metrics = result.trade_metrics
```

#### 2.1.2 run_backtest 函数

主要回测入口函数，支持多种策略定义方式。

**参数说明：**

```python
def run_backtest(
    data: Optional[Union[pd.DataFrame, Dict[str, pd.DataFrame], List[Bar]]] = None,
    strategy: Union[Type[Strategy], Strategy, Callable[[Any, Bar], None], None] = None,
    symbol: Union[str, List[str]] = "BENCHMARK",
    cash: float = 1_000_000.0,
    commission: float = 0.0003,      # 佣金率
    stamp_tax: float = 0.0005,       # 印花税
    transfer_fee: float = 0.00001,   # 过户费
    min_commission: float = 5.0,     # 最低佣金
    execution_mode: Union[ExecutionMode, str] = ExecutionMode.NextOpen,  # 执行模式
    timezone: str = "Asia/Shanghai",
    initialize: Optional[Callable[[Any], None]] = None,  # 初始化函数
    context: Optional[Dict[str, Any]] = None,            # 上下文数据
    history_depth: int = 0,          # 历史数据深度
    warmup_period: int = 0,          # 预热期
    lot_size: Union[int, Dict[str, int], None] = None,   # 最小交易单位
    show_progress: bool = True,
    config: Optional[BacktestConfig] = None,              # 高级配置
    instruments_config: Optional[Union[List[InstrumentConfig], Dict[str, InstrumentConfig]]] = None,
    **kwargs: Any,
) -> BacktestResult
```

**执行模式 (ExecutionMode)：**

| 模式 | 说明 |
|------|------|
| `NextOpen` | 下一根Bar开盘价成交（默认） |
| `CurrentClose` | 当前Bar收盘价成交 |

---

### 2.2 策略基类 (strategy.py)

#### 2.2.1 Strategy 类架构

```python
class Strategy:
    """策略基类 - 事件驱动设计"""
    
    # 核心属性
    ctx: StrategyContext          # 策略上下文（Rust引擎提供）
    current_bar: Optional[Bar]    # 当前Bar
    current_tick: Optional[Tick]  # 当前Tick
    sizer: Sizer                  # 仓位管理器
    model: Optional[QuantModel]   # ML模型
    
    # 历史数据配置
    _history_depth: int           # 历史数据保留长度
    _bars_history: defaultdict    # Bar历史缓存
    
    # 滚动训练配置
    _rolling_train_window: int    # 训练窗口
    _rolling_step: int            # 滚动步长
    _bar_count: int               # Bar计数器
```

#### 2.2.2 生命周期方法

```python
def on_start(self) -> None:
    """策略启动时调用 - 用于订阅数据、注册指标"""
    pass

def on_bar(self, bar: Bar) -> None:
    """Bar数据回调 - 主策略逻辑入口"""
    pass

def on_tick(self, tick: Tick) -> None:
    """Tick数据回调"""
    pass

def on_timer(self, payload: str) -> None:
    """定时器回调"""
    pass

def on_order(self, order: Any) -> None:
    """订单状态更新回调"""
    pass

def on_trade(self, trade: Any) -> None:
    """成交回调"""
    pass

def on_stop(self) -> None:
    """策略停止时调用"""
    pass
```

#### 2.2.3 交易接口

```python
# 基础下单
def buy(self, symbol=None, quantity=None, price=None, 
        time_in_force=None, trigger_price=None) -> str:
    """买入下单"""
    
def sell(self, symbol=None, quantity=None, price=None,
         time_in_force=None, trigger_price=None) -> str:
    """卖出下单"""

# 目标仓位管理
def order_target(self, target: float, symbol=None, price=None) -> None:
    """调整仓位到目标数量"""
    
def order_target_value(self, target_value: float, symbol=None, price=None) -> None:
    """调整仓位到目标市值"""
    
def order_target_percent(self, target_percent: float, symbol=None, price=None) -> None:
    """调整仓位到目标百分比"""

# 快捷操作
def buy_all(self, symbol=None) -> None:
    """全仓买入"""
    
def close_position(self, symbol=None) -> None:
    """平仓"""
    
def short(self, symbol=None, quantity=None, price=None) -> None:
    """卖出开空（期货）"""
    
def cover(self, symbol=None, quantity=None, price=None) -> None:
    """买入平空（期货）"""

# 订单管理
def cancel_order(self, order_or_id) -> None:
    """取消订单"""
    
def cancel_all_orders(self, symbol=None) -> None:
    """取消所有未完成订单"""
```

#### 2.2.4 数据获取接口

```python
def get_history(self, count: int, symbol=None, field: str = "close") -> np.ndarray:
    """
    获取历史数据 (类似Zipline)
    
    :param count: 数据长度
    :param symbol: 标的代码
    :param field: 字段名 (open, high, low, close, volume)
    :return: Numpy数组
    """

def get_history_df(self, count: int, symbol=None) -> pd.DataFrame:
    """
    获取历史数据DataFrame
    
    :return: DataFrame with columns [open, high, low, close, volume]
    """

def get_rolling_data(self, length=None, symbol=None) -> tuple[pd.DataFrame, Optional[pd.Series]]:
    """
    获取滚动训练数据 (X, y)
    
    用于机器学习策略
    """
```

#### 2.2.5 持仓查询

```python
@property
def position(self) -> Position:
    """获取当前标的持仓对象"""
    # 使用: if self.position.size == 0: ...

def get_position(self, symbol=None) -> float:
    """获取指定标的持仓数量"""

def get_positions(self) -> Dict[str, float]:
    """获取所有持仓"""

def get_portfolio_value(self) -> float:
    """获取投资组合总价值"""

def get_cash(self) -> float:
    """获取现金"""

def get_open_orders(self, symbol=None) -> list:
    """获取未完成订单"""
```

---

### 2.3 机器学习模块 (ml/model.py)

#### 2.3.1 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    QuantModel (ABC)                     │
│                   抽象基类 - 统一接口                      │
├─────────────────────────────────────────────────────────┤
│  + fit(X, y)                                            │
│  + predict(X) -> np.ndarray                             │
│  + save(path)                                           │
│  + load(path)                                           │
│  + set_validation(...)                                  │
└─────────────────────────────────────────────────────────┘
                           △
           ┌───────────────┴───────────────┐
           │                               │
┌──────────┴──────────┐         ┌──────────┴──────────┐
│   SklearnAdapter    │         │   PyTorchAdapter    │
│   sklearn模型适配器  │         │   PyTorch模型适配器  │
├─────────────────────┤         ├─────────────────────┤
│ 支持: XGBoost,      │         │ 支持: LSTM,         │
│       LightGBM,     │         │       Transformer,  │
│       RandomForest, │         │       MLP           │
│       LogisticReg   │         │                     │
└─────────────────────┘         └─────────────────────┘
```

#### 2.3.2 ValidationConfig 配置

```python
@dataclass
class ValidationConfig:
    method: Literal["walk_forward"] = "walk_forward"  # 验证方法
    train_window: Union[str, int] = "1y"              # 训练窗口
    test_window: Union[str, int] = "3m"               # 测试窗口
    rolling_step: Union[str, int] = "3m"              # 滚动步长
    frequency: str = "1d"                             # 数据频率
    incremental: bool = False                         # 是否增量学习
    verbose: bool = False                             # 是否打印日志
```

#### 2.3.3 SklearnAdapter 使用示例

```python
from akquant import Strategy
from akquant.ml import SklearnAdapter
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

class MLStrategy(Strategy):
    def __init__(self):
        super().__init__()
        
        # 1. 创建Pipeline（防止数据泄露）
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('model', RandomForestClassifier(n_estimators=100))
        ])
        
        # 2. 包装为QuantModel
        self.model = SklearnAdapter(pipeline)
        
        # 3. 配置Walk-forward验证
        self.model.set_validation(
            method='walk_forward',
            train_window=50,      # 50根Bar训练
            rolling_step=10,      # 每10根Bar重训
            frequency='1d',
            verbose=True
        )
        
        # 4. 设置历史数据深度
        self.set_history_depth(60)
    
    def prepare_features(self, df: pd.DataFrame, mode='training'):
        """
        特征工程 - 必须实现
        
        :param mode: 'training' 返回 (X, y)
                     'inference' 返回 X (最后一行)
        """
        X = pd.DataFrame()
        X['ret1'] = df['close'].pct_change(1)
        X['ret5'] = df['close'].pct_change(5)
        X['volatility'] = df['close'].rolling(5).std()
        X = X.fillna(0)
        
        if mode == 'inference':
            return X.iloc[-1:]
        
        # 构造标签 - 预测下一期涨跌
        future_ret = df['close'].pct_change().shift(-1)
        y = (future_ret > 0).astype(int)
        
        return X.iloc[:-1], y.iloc[:-1]
    
    def on_bar(self, bar):
        # 模型自动训练（由框架触发）
        
        # 获取预测
        hist_df = self.get_history_df(10)
        X_curr = self.prepare_features(hist_df, mode='inference')
        
        prob_up = self.model.predict(X_curr)[0]
        
        # 交易决策
        if prob_up > 0.55:
            self.buy(bar.symbol, 100)
        elif prob_up < 0.45:
            self.sell(bar.symbol, 100)
```

#### 2.3.4 PyTorchAdapter 使用示例

```python
from akquant.ml import PyTorchAdapter
import torch.nn as nn
import torch.optim as optim

class SimpleNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(10, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x):
        return self.fc(x)

# 在策略中使用
self.model = PyTorchAdapter(
    network=SimpleNet(),
    criterion=nn.BCELoss(),
    optimizer_cls=optim.Adam,
    lr=0.001,
    epochs=20,
    batch_size=64,
    device='cuda'  # 或 'cpu'
)
```

#### 2.3.5 自动训练机制

```python
# Strategy基类中的自动训练逻辑
def _on_bar_event(self, bar: Bar, ctx: StrategyContext) -> None:
    # ... 其他处理 ...
    
    # 检查滚动训练信号
    if self._rolling_step > 0:
        self._bar_count += 1
        if self._bar_count % self._rolling_step == 0:
            self.on_train_signal(self)

def on_train_signal(self, context) -> None:
    """滚动训练信号回调"""
    if self.model:
        X_df, _ = self.get_rolling_data()
        X, y = self.prepare_features(X_df, mode='training')
        self.model.fit(X, y)
```

---

### 2.4 数据模块 (data.py)

#### 2.4.1 ParquetDataCatalog

高性能数据存储，使用Parquet格式。

```python
from akquant.data import ParquetDataCatalog

# 创建Catalog
catalog = ParquetDataCatalog()
# 默认路径: ~/.akquant/catalog

# 写入数据
catalog.write('600000', df)

# 读取数据
df = catalog.read(
    symbol='600000',
    start_date='2023-01-01',
    end_date='2023-12-31',
    columns=['open', 'high', 'low', 'close', 'volume']
)

# 列出所有标的
symbols = catalog.list_symbols()
```

#### 2.4.2 DataLoader

```python
from akquant.data import DataLoader

loader = DataLoader()

# DataFrame转Bar列表
bars = loader.df_to_bars(df, symbol='600000')
```

---

### 2.5 风控模块 (risk.py)

```python
from akquant.config import StrategyConfig, RiskConfig
from akquant.risk import apply_risk_config

# 配置风控
risk_config = RiskConfig(
    max_position_pct=0.95,      # 最大仓位95%
    max_drawdown_pct=0.20,      # 最大回撤20%
    daily_loss_limit=10000,     # 日亏损限额
)

config = StrategyConfig(
    initial_cash=1_000_000,
    risk=risk_config
)

# 应用到引擎
result = run_backtest(
    strategy=MyStrategy,
    data=df,
    config=config
)
```

---

### 2.6 仓位管理 (sizer.py)

```python
from akquant.sizer import FixedSize, PercentSizer, AllInSizer

class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        
        # 固定数量
        self.set_sizer(FixedSize(100))
        
        # 按资金百分比
        self.set_sizer(PercentSizer(0.95))
        
        # 全仓
        self.set_sizer(AllInSizer())
```

---

## 三、多周期支持分析

### 3.1 现状评估

**结论：AKQuant 原生不支持多周期数据同时订阅**

| 功能 | 支持情况 | 说明 |
|------|---------|------|
| 单周期回测 | ✅ 完整支持 | 日线、小时线、分钟线 |
| 多周期同时订阅 | ❌ 不支持 | 无 `resampledata` 类方法 |
| 数据重采样 | ❌ 不支持 | 需外部预处理 |
| 多资产回测 | ✅ 支持 | 可同时交易多个标的 |

### 3.2 与Backtrader对比

```python
# Backtrader - 原生支持多周期
cerebro.adddata(daily_data)
cerebro.resampledata(daily_data, timeframe=bt.TimeFrame.Weeks)

# AKQuant - 单数据传入
result = run_backtest(
    data=df,  # 单一DataFrame
    strategy=MyStrategy,
    symbol='600000'
)
```

### 3.3 多周期 workaround

```python
class MultiTimeframeStrategy(Strategy):
    """AKQuant多周期策略示例 - 预处理方案"""
    
    def __init__(self, prepared_data):
        # 传入预处理好的多周期数据
        self.data = prepared_data
        self.cursor = 0
    
    def on_bar(self, bar):
        # 从预计算数据中获取当前多周期特征
        current = self.data.iloc[self.cursor]
        
        daily_ma = current['daily_ma20']
        weekly_ma = current['weekly_ma4']  # 周线MA4 ≈ 日线MA20
        
        # 多周期共振逻辑
        if daily_ma > weekly_ma:
            self.buy(bar.symbol, 100)
        
        self.cursor += 1

# 数据预处理
def prepare_multi_timeframe_data(df_daily):
    """在策略外预处理多周期数据"""
    df = df_daily.copy()
    
    # 计算日线指标
    df['daily_ma5'] = df['close'].rolling(5).mean()
    df['daily_ma20'] = df['close'].rolling(20).mean()
    
    # 计算周线指标（从日线重采样）
    weekly = df.resample('W').last()
    weekly['weekly_ma4'] = weekly['close'].rolling(4).mean()
    
    # 将周线指标对齐到日线
    df['weekly_ma4'] = weekly['weekly_ma4'].reindex(df.index, method='ffill')
    
    return df
```

---

## 四、AKQuant vs ft2 详细对比

### 4.1 架构设计对比

| 维度 | AKQuant | ft2 |
|------|---------|-----|
| **核心语言** | Rust + Python混合 | 纯Python |
| **性能特点** | 极高（Rust零拷贝） | 标准Python性能 |
| **设计模式** | 事件驱动 + 向量化混合 | 纯事件驱动 |
| **代码复杂度** | 较高（Rust+Python） | 较低（纯Python） |
| **可扩展性** | 需Rust开发 | Python直接修改 |

### 4.2 回测引擎对比

| 功能 | AKQuant | ft2 |
|------|---------|-----|
| **引擎实现** | Rust核心 (akquant.pyd) | Python (engine.py) |
| **撮合方式** | Engine.run() 内部循环 | Engine.run() 外部循环 |
| **执行模式** | NextOpen / CurrentClose | 当前Bar收盘价 |
| **滑点支持** | ✅ set_slippage() | ❌ 需自行实现 |
| **手续费配置** | ✅ 多品种独立配置 | ✅ 统一配置 |
| **T+1规则** | ✅ set_t_plus_one() | ❌ 需自行实现 |
| **交易时段** | ✅ set_market_sessions() | ❌ 无 |
| **进度条** | ✅ show_progress | ❌ 无 |

### 4.3 数据管理对比

| 功能 | AKQuant | ft2 |
|------|---------|-----|
| **多周期支持** | ❌ 不支持 | ✅ 原生支持 |
| **数据订阅** | subscribe(symbol) 单一 | subscribe(symbol, freq, count) 多周期 |
| **历史数据获取** | get_history(count, field) | data(symbol, freq, count, fields) |
| **数据缓存** | Rust内部管理 | _Cache类 (行/列两种格式) |
| **数据源** | AKShare / Parquet | 掘金API |
| **自定义字段** | bar.extra dict | DataFrame列 |

### 4.4 策略接口对比

| 功能 | AKQuant | ft2 |
|------|---------|-----|
| **策略基类** | Strategy | 用户自定义类 |
| **初始化** | __init__() | __init__() |
| **启动回调** | on_start() | 无 |
| **Bar回调** | on_bar(bar) | on_bar(context, bars) |
| **Tick回调** | on_tick(tick) | 无 |
| **停止回调** | on_stop() | 无 |
| **订单回调** | on_order(order) | 无 |
| **成交回调** | on_trade(trade) | 无 |

### 4.5 交易接口对比

| 功能 | AKQuant | ft2 |
|------|---------|-----|
| **买入** | buy(symbol, quantity, price) | order_volume(symbol, volume, price) |
| **卖出** | sell(symbol, quantity, price) | order_volume(symbol, -volume, price) |
| **按比例下单** | order_target_percent() | order_percent(symbol, percent) |
| **平仓** | close_position(symbol) | order_percent(symbol, -1.0) |
| **全仓买入** | buy_all(symbol) | order_percent(symbol, 0.95) |
| **仓位管理器** | Sizer (FixedSize/PercentSizer/AllInSizer) | 无 |
| **止损单** | stop_buy() / stop_sell() | 无 |
| **取消订单** | cancel_order(order_id) | 无 |

### 4.6 持仓与账户对比

| 功能 | AKQuant | ft2 |
|------|---------|-----|
| **持仓查询** | position.size / get_position() | get_position(symbol) |
| **现金查询** | get_cash() | get_account()['cash'] |
| **总资产** | get_portfolio_value() | get_account()['nav'] |
| **持仓对象** | Position类 | Dict |
| **账户快照** | 自动记录 | take_snapshot() 手动调用 |

### 4.7 机器学习对比

| 功能 | AKQuant | ft2 |
|------|---------|-----|
| **ML集成** | ✅ 内置完整方案 | ❌ 需自行开发 |
| **模型适配器** | SklearnAdapter, PyTorchAdapter | 无 |
| **Walk-forward** | ✅ ValidationConfig配置 | ❌ 需自行实现 |
| **自动训练** | ✅ on_train_signal() 触发 | ❌ 需手动调用 |
| **特征工程** | prepare_features() 回调 | 无 |
| **防数据泄露** | ✅ Pipeline集成 | ❌ 需自行处理 |

### 4.8 分析与报告对比

| 功能 | AKQuant | ft2 |
|------|---------|-----|
| **绩效指标** | 40+ 指标 (PerformanceMetrics) | AccountAnalyzer |
| **交易分析** | TradePnL (FIFO) | _calculate_profit() |
| **结果格式** | DataFrame + 原始对象 | DataFrame |
| **绘图** | result.plot() | 无 |
| **HTML报告** | ❌ 无 | ✅ to_html_report() |
| **权益曲线** | equity_curve | snapshots |

### 4.9 代码示例对比

#### 数据订阅

```python
# AKQuant - 单周期订阅
class MyStrategy(Strategy):
    def __init__(self):
        self.subscribe('600000')
    
    def on_bar(self, bar):
        hist = self.get_history_df(20)

# ft2 - 多周期订阅
class MyStrategy:
    def __init__(self):
        context.subscribe(symbols='600000', freq='1d', count=200)
        context.subscribe(symbols='600000', freq='1w', count=50)  # 多周期
    
    def on_bar(self, context, bars):
        daily = context.data('600000', '1d', count=20)
        weekly = context.data('600000', '1w', count=10)
```

#### 下单交易

```python
# AKQuant
def on_bar(self, bar):
    if self.position.size == 0:
        self.buy(bar.symbol, 100)  # 固定数量
    else:
        self.close_position(bar.symbol)

# ft2
def on_bar(self, context, bars):
    pos = account.get_position('600000')
    if pos['volume'] == 0:
        account.order_percent('600000', 0.95)  # 按比例
    else:
        account.order_percent('600000', -1.0)  # 平仓
```

#### 运行回测

```python
# AKQuant
result = run_backtest(
    strategy=MyStrategy,
    data=df,
    symbol='600000',
    cash=1_000_000,
    commission=0.0003,
    execution_mode=ExecutionMode.NextOpen
)
print(result.metrics_df)

# ft2
engine.run(MyStrategy, start_time=start_time, end_time=end_time)
analyzer = AccountAnalyzer(account)
print(f"收益率: {analyzer.calculate_return_rate()*100:.2f}%")
analyzer.to_html_report("回测报告")
```

---

## 五、可借鉴的设计

### 5.1 值得ft2学习的地方

1. **ML集成框架**
   - `QuantModel` 抽象基类统一接口
   - `ValidationConfig` 配置Walk-forward
   - 自动训练触发机制

2. **Rust核心性能**
   - 撮合引擎用Rust实现
   - Python仅作为胶水层

3. **指标预计算**
   - `IndicatorSet` 向量化预计算
   - 避免on_bar中重复计算

4. **结果封装**
   - `BacktestResult` 提供多种格式视图
   - DataFrame和原始对象并存

### 5.2 ft2的优势

1. **多周期原生支持** - AKQuant缺失的功能
2. **掘金API兼容** - 实盘迁移成本低
3. **代码简洁** - 易于理解和修改
4. **数据缓存** - 灵活的Cache机制

---

## 六、API速查表

### 6.1 快速开始

```python
import akquant as aq
from akquant import Strategy, run_backtest
import pandas as pd

# 准备数据
df = pd.DataFrame({
    'date': pd.date_range('2023-01-01', periods=100),
    'open': [...],
    'high': [...],
    'low': [...],
    'close': [...],
    'volume': [...],
    'symbol': 'TEST'
})

# 定义策略
class MyStrategy(Strategy):
    def on_bar(self, bar):
        if self.position.size == 0:
            self.buy(bar.symbol, 100)
        else:
            self.sell(bar.symbol, 100)

# 运行回测
result = run_backtest(
    strategy=MyStrategy,
    data=df,
    symbol='TEST',
    cash=1_000_000
)

# 查看结果
print(result.metrics_df)
```

### 6.2 核心类继承关系

```
QuantModel (ABC)
├── SklearnAdapter
└── PyTorchAdapter

Strategy
├── 用户自定义策略
└── VectorizedStrategy (向量化策略)

Sizer
├── FixedSize
├── PercentSizer
└── AllInSizer
```

---

## 七、总结

AKQuant是一个设计精良的高性能回测框架，其核心优势在于：

1. **Rust核心** - 提供极致性能
2. **ML原生支持** - Walk-forward验证机制完善
3. **统一接口** - Adapter模式解耦模型与策略

但在多周期支持方面存在明显不足，这是ft2框架的优势所在。两个框架可以互补：
- **AKQuant** 适合大规模回测和ML策略
- **ft2** 适合多周期策略和掘金实盘对接
