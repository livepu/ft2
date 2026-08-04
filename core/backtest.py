"""
core/backtest.py — 简化回测入口 (Engine 二次封装)
============================================================

定位：core.Engine 之上的薄封装，消除重复的使用模板代码。
      不替代 Engine，内部委托 Engine.run / Engine.run_fast。

封装的模板:
  1. 创建 Engine + context.mode 配置
  2. 数据注入 (add_data 逐个传入 + eob 列 + DatetimeIndex + subscribe)
  3. 基准注入 (BenchHolder + set_benchmark, full 模式自动)

不封装的:
  - Strategy 的 on_bar 决策逻辑 (用户自己写, 保留完整事件驱动能力)
  - start_time/end_time (用户传入, 因场景而异)

用法 — 自定义 Strategy (完整事件驱动能力):
  >>> from core import Backtester
  >>> bt = Backtester()
  >>> bt.set_init_cash(1_000_000).set_benchmark('399317.SZ', df_399317, '国证A指')
  >>> bt.add_data('600000.SH', df_600000, symbol_name='浦发银行')
  >>> analyzer = bt.run(MyStrategy(), start_time, end_time, mode='full')

逃生舱: bt.engine 可直接拿原始 Engine 做高级操作。

[新增] 2026-06-30 Engine 二次封装, 简化调用不丢灵活性
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Any

from .engine import Engine
from .account import BenchHolder
from .storage import context
from .analyzer import AccountAnalyzer




# ============================================================
# Backtester — Engine 二次封装
# ============================================================

class Backtester:
    """简化回测入口 — 封装 Engine 使用模板, 不封装 Strategy 决策

    封装:
      - Engine 创建 (init_cash / fee_config)
      - context.mode = 'backtest'
      - 数据注入 (add_data 逐个传入 + eob 列 + DatetimeIndex + subscribe)
      - 基准注入 (BenchHolder + set_benchmark, full 模式自动)

    不封装:
      - Strategy 的 on_bar (用户自定义, 保留完整事件驱动能力)
      - start_time/end_time (用户传入, 因场景而异)

    Attributes:
        engine: 原始 Engine 实例 (add_data 后可用, run 前可配置, run 后可查询)
    """

    def __init__(self):
        """构造空 Backtester, 数据在 add_data() 时传入"""
        self._symbol_data: Dict[str, pd.DataFrame] = {}
        self._symbol_names: Dict[str, str] = {}  # 品种名称（可选，仅用于显示）
        self._init_cash: float = 1e6
        self._fee_config: Optional[dict] = None
        self._future_config: Optional[dict] = None  # [新增] 2026-08-04 期货统一默认规格（方案A）
        self._bench_label: Optional[str] = None
        self._freq: str = '1d'

        # engine 在 add_data 时创建
        self.engine: Optional[Engine] = None

    # ── 配置 (链式) ──

    def set_init_cash(self, init_cash: float) -> 'Backtester':
        """设置初始资金 (对齐 Engine.__init__ 的 init_cash 参数)"""
        self._init_cash = init_cash
        return self

    def set_fee_config(self, fee_config: dict) -> 'Backtester':
        """设置费率配置 (对齐 Engine.__init__ 的 fee_config 参数)"""
        self._fee_config = fee_config
        return self

    def set_future_config(self, future_config: dict) -> 'Backtester':
        """设置期货统一默认规格 (对齐 Engine.__init__ 的 future_config 参数)

        [新增] 2026-08-04 方案A：无品种数据时统一兜底，三级解析
        (register_contract > contracts[symbol] > 默认值)。

        Example:
            >>> bt.set_future_config({'default_multiplier': 10, 'default_margin_ratio': 0.10})
        """
        self._future_config = future_config
        return self

    def set_benchmark(self, bench_label: str, bench_data: pd.DataFrame,
                      symbol_name: str = None) -> 'Backtester':
        """设置基准品种 (标签+数据一起传, full 模式自动跑 BenchHolder)

        对齐 FacEngine 的 bench_label 参数，基准数据只存不加入主引擎。

        Args:
            bench_label: 基准品种代码 (如 '399317.SZ')
            bench_data: OHLCV DataFrame
            symbol_name: 品种名称 (可选, 仅用于显示)
        """
        self._bench_label = bench_label

        # 标准化数据
        df = bench_data.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if 'eob' not in df.columns:
            df['eob'] = df.index

        # 基准数据只存 _symbol_data, 不加入主引擎
        self._symbol_data[bench_label] = df
        if symbol_name:
            self._symbol_names[bench_label] = symbol_name
        elif 'name' in df.columns:
            self._symbol_names[bench_label] = df['name'].iloc[-1]

        return self

    def set_freq(self, freq: str) -> 'Backtester':
        """设置数据频率 (默认 '1d', 支持 '1w' 等多频率)"""
        self._freq = freq
        return self

    # ── 数据注入 ──

    def add_data(self, symbol: str, data: pd.DataFrame, symbol_name: str = None) -> 'Backtester':
        """添加策略品种数据，对齐 Engine.add_data 风格

        注意: 基准数据请通过 set_benchmark(label, data) 传入，不走 add_data。

        封装:
          - Engine 创建 (首次 add_data 时)
          - context.mode = 'backtest'
          - DatetimeIndex + eob 列 + subscribe + add_data
          - symbol_name 透传给 Engine (Engine 自动提取 df 列作为后备)

        Args:
            symbol: 品种代码（如 '600000.SH', '399317.SZ'）
            data: OHLCV DataFrame，需满足:
                * index: 日期（DatetimeIndex / 可转换的日期字符串）
                * columns: 应含 OHLCV 字段（open/high/low/close/amount/volume 等）
                  可额外带 symbol_name/name 列（Engine 自动识别为品种名称）
                * eob 列（可选）：若不传，Backtester 自动设 eob = index
            symbol_name: 品种名称（可选，显式传入时优先于 df 列）

        Returns:
            Backtester (链式)

        Example:
            >>> from core import Backtester
            >>> bt = Backtester().set_init_cash(1e6).set_benchmark('399317.SZ', df_399317, '国证A指')
            >>> bt.add_data('600000.SH', df_600000, symbol_name='浦发银行')
            >>> analyzer = bt.run(MyStrategy(), start, end)
        """
        # 首次 add_data 时创建 Engine
        if self.engine is None:
            self.engine = Engine(init_cash=self._init_cash, fee_config=self._fee_config,
                                 future_config=self._future_config)
            context.mode = 'backtest'

        # 标准化数据
        df = data.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if 'eob' not in df.columns:
            df['eob'] = df.index

        # subscribe + add_data
        context.unsubscribe(symbol, self._freq)
        context.subscribe(symbol, self._freq, count=300)
        self.engine.add_data(symbol, self._freq, df, symbol_name=symbol_name)

        return self

    # ── 执行 (接受任意 Strategy) ──

    def run(self, strategy: Any, start_time, end_time,
            mode: str = 'full') -> AccountAnalyzer:
        """执行回测 — 用户传 Strategy, 保留完整事件驱动能力

        Args:
            strategy: 带 on_bar 的对象或类 (同 Engine.run)
            start_time: 回测起始时间
            end_time: 回测结束时间
            mode: 'full' (快照+交易记录+基准) / 'fast' (仅净值, 无交易记录)

        Returns:
            AccountAnalyzer

        Example:
            >>> bt = Backtester().set_init_cash(1e6).set_benchmark('399317.SZ', df_399317)
            >>> bt.add_data('600000.SH', df_600000)
            >>> analyzer = bt.run(MyStrategy(), start, end, mode='full')
        """
        if self.engine is None:
            raise RuntimeError("未注入数据, 请先调 add_data()")

        if mode == 'fast':
            return self.engine.run_fast(strategy, start_time, end_time)

        # full
        self.engine.run(strategy, start_time, end_time)
        analyzer = AccountAnalyzer(self.engine.account)

        # 基准注入
        if self._bench_label and self._bench_label in self._symbol_data:
            analyzer = self._inject_benchmark(analyzer, start_time, end_time)

        return analyzer

    # ── 内部: 基准注入 (封装 BenchHolder 模板) ──

    def _inject_benchmark(self, analyzer: AccountAnalyzer,
                          start_time, end_time) -> AccountAnalyzer:
        """跑基准 Engine + BenchHolder, 注入对比"""
        bench_label = self._bench_label

        # 直接使用已标准化的数据
        if bench_label not in self._symbol_data:
            raise ValueError(f"基准品种 {bench_label} 未通过 set_benchmark() 注入")

        bench_df = self._symbol_data[bench_label].copy()

        # 创建基准 Engine
        bench_eng = Engine(init_cash=self._init_cash, fee_config=self._fee_config)

        # 基准数据需要单独 subscribe + add_data（因为没加入主引擎）
        context.unsubscribe(bench_label, self._freq)
        context.subscribe(bench_label, self._freq, count=3000)

        # 获取品种名称（用于显示，没有则回退到代码）
        bench_name = self._symbol_names.get(bench_label)

        # 传入 symbol_name（如果有的话）
        bench_eng.add_data(bench_label, self._freq, bench_df, symbol_name=bench_name)

        bench_eng.run(BenchHolder, start_time, end_time)
        bench_an = AccountAnalyzer(bench_eng.account)

        analyzer.set_benchmark(bench_an.daily_assets, bench_name or bench_label)
        return analyzer


# ============================================================
# VectorBacktester — 向量化回测流程封装（与 Backtester 平级但独立）
# ============================================================
# [新增] 2026-08-04 补全 vector 高层流程：导入数据 → weight_fn → 执行 → AccountAnalyzer。
#   与 Backtester 的关系：Backtester 封装 Engine（事件驱动 full/fast）；
#   本类封装矩阵路径（run_vectorized），两者互不依赖、使用体验对齐（add_data → run）。

class VectorBacktester:
    """向量化回测流程封装（矩阵近似，无 lot_size）

    对齐 Backtester 使用体验：
        vbt = VectorBacktester().set_init_cash(1e6).set_fee_config({...})
        vbt.add_data('600000.SH', df_600000).add_data('000001.SZ', df_000001)
        analyzer = vbt.run(weight_fn, rebalance='W')
        print(analyzer.sharpe_ratio())

    策略表达为 weight_fn(date) → {symbol: weight}（调仓日目标权重），
    决策逻辑由调用方提供，引擎只做矩阵/时序/费率/净值。

    Attributes:
        assets: 导入的数据 {symbol: DataFrame}
    """

    def __init__(self):
        self.assets: Dict[str, pd.DataFrame] = {}
        self._symbol_names: Dict[str, str] = {}
        self._init_cash: float = 1e6
        self._fee_config: Optional[dict] = None

    # ── 配置 (链式) ──

    def set_init_cash(self, init_cash: float) -> 'VectorBacktester':
        """设置初始资金"""
        self._init_cash = init_cash
        return self

    def set_fee_config(self, fee_config: dict) -> 'VectorBacktester':
        """设置费率配置"""
        self._fee_config = fee_config
        return self

    # ── 数据注入 ──

    def add_data(self, symbol: str, data: pd.DataFrame,
                 symbol_name: str = None) -> 'VectorBacktester':
        """添加品种数据（只需 close 列 + DatetimeIndex）

        Args:
            symbol: 品种代码
            data: OHLCV DataFrame（index 为日期，含 close 列；index 可自动转换）
            symbol_name: 品种名称（可选，仅用于显示）
        """
        df = data.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        self.assets[symbol] = df
        if symbol_name:
            self._symbol_names[symbol] = symbol_name
        return self

    # ── panel 工具（融合 factor 的 Top-N 能力）──

    @staticmethod
    def make_top_n_weight_fn(panel: pd.DataFrame, top_n: int, buffer: int = 0):
        """从排名面板构造 Top-N 等权 weight_fn（含 buffer 保留，闭包维护 held 跨调仓日状态）

        [新增] 2026-08-04 融合 factor 的 panel 驱动能力：
        factor 的 FacEngine 与 VectorBacktester.run_panel 共用此工具，避免各版本复制 Top-N 逻辑。
        """
        panel = panel.copy()
        if not isinstance(panel.index, pd.DatetimeIndex):
            panel.index = pd.to_datetime(panel.index)
        dates = panel.index.sort_values()
        symbols = panel.columns.tolist()
        symbols_set = set(symbols)
        use_buffer = buffer > 0
        buffer_rank = top_n + buffer

        # 预计算每日 top 排名索引 (T × k)
        panel_arr = panel.values
        top_indices = np.argsort(-panel_arr, axis=1)[:, :max(top_n, buffer_rank if use_buffer else top_n)]
        date_to_i = {d: i for i, d in enumerate(dates)}
        held = set()

        def weight_fn(date):
            nonlocal held
            i = date_to_i.get(date)
            if i is None:                      # 调仓日不在 panel 中（数据不齐）→ 空仓
                return {}
            top_codes = {symbols[j] for j in top_indices[i, :top_n] if symbols[j] in symbols_set}
            if use_buffer:
                buffer_codes = {symbols[j] for j in top_indices[i, :buffer_rank] if symbols[j] in symbols_set}
                keep = held & buffer_codes
            else:
                keep = held & top_codes
            n_slots = top_n - len(keep)
            new_codes = [c for c in top_codes if c not in held][:n_slots]
            target = keep | set(new_codes)
            held = target
            if not target:
                return {}
            wt = 1.0 / len(target)
            return {c: wt for c in target}

        return weight_fn

    # ── 执行 ──

    def run_panel(self, panel: pd.DataFrame, top_n: int, buffer: int = 0,
                  rebalance='W', start_time=None, end_time=None) -> AccountAnalyzer:
        """panel 驱动的向量回测（factor Top-N 等权轮动）

        [新增] 2026-08-04 融合 factor 的 panel 能力：内部用 make_top_n_weight_fn
        构造 Top-N 权重，再委托 run()。factor 的 FacEngine(mode='vector') 与
        通用用户均可用此入口，无需复制 Top-N 逻辑。

        Args:
            panel: 因子排名面板, index=日期, columns=品种, 值越大越好
            top_n: 持仓品种数
            buffer: 排名缓冲数（0=严格 Top-N）
            rebalance / start_time / end_time: 同 run()
        """
        weight_fn = self.make_top_n_weight_fn(panel, top_n, buffer)
        return self.run(weight_fn, rebalance, start_time, end_time)

    def run(self, weight_fn, rebalance='W', start_time=None, end_time=None) -> AccountAnalyzer:
        """执行向量化回测

        Args:
            weight_fn: 策略权重回调 weight_fn(date) → {symbol: weight}（仅调仓日调用）
            rebalance: 调仓频率（'5D'/'D'/'W'/'M'/'ME' 或 Scheduler 对象）
            start_time / end_time: 可选时间范围（None=全数据）

        Returns:
            AccountAnalyzer(daily_assets)
        """
        if not self.assets:
            raise RuntimeError("未注入数据，请先调 add_data()")

        # 对齐交易日（所有品种 index 并集）
        dates = pd.DatetimeIndex(sorted(set().union(*[set(df.index) for df in self.assets.values()])))
        if start_time is not None:
            dates = dates[dates >= pd.Timestamp(start_time)]
        if end_time is not None:
            dates = dates[dates <= pd.Timestamp(end_time)]
        if len(dates) < 2:
            raise ValueError("回测区间不足 2 个交易日")

        return run_vectorized(self.assets, dates, list(self.assets.keys()),
                              weight_fn, rebalance, self._init_cash,
                              start_time, self._fee_config)


# ============================================================
# 向量化回测核心 — [新增] 2026-08-04 从 factor/v4/v5、pms/v1 的 _run_vectorized 上移
# ============================================================

def _make_rebalance_set(dates: pd.DatetimeIndex, rebalance) -> set:
    """生成调仓日集合（兼容字符串和 v3 RebalanceScheduler 对象）

    字符串: 支持 '5D' 固定间隔 / 'D' / 'W' / 'M' / 'ME'
    Scheduler: 调用 generate() 保持 v3 兼容
    """
    if hasattr(rebalance, 'generate'):
        rb_dates = rebalance.generate(dates)
        return {pd.Timestamp(d.date()) for d in rb_dates}

    rebalance = str(rebalance)
    if rebalance.endswith('D') and rebalance[:-1].isdigit():
        interval = int(rebalance[:-1])
        return {pd.Timestamp(dates[i].date())
                for i in range(interval - 1, len(dates), interval)}

    freq_map = {'M': 'MS', 'ME': 'ME'}
    freq = freq_map.get(rebalance, rebalance)
    rebalance_series = dates.to_series().resample(freq).last().dropna()
    return {pd.Timestamp(d.date()) for d in rebalance_series}


def run_vectorized(assets: Dict[str, pd.DataFrame], dates: pd.DatetimeIndex,
                   symbols: list, weight_fn, rebalance='W',
                   initial_capital: float = 1e6, start_date=None,
                   fee_config: Optional[dict] = None) -> AccountAnalyzer:
    """通用向量化回测核心（矩阵近似，无 lot_size）。

    将"每日调仓权重"抽象为回调 weight_fn，统一实现：
    价格/收益率矩阵、调仓时序、费率模拟、NAV 迭代 → AccountAnalyzer。
    因子轮动（Top-N）与风格配置（预计算权重）都只需提供 weight_fn，无需复制矩阵引擎。

    调仓时序: 当日收盘后用旧权重计收益 → 调仓 → 记录净值（与事件驱动 _drive_timeline 一致）

    Args:
        assets: Dict[symbol, DataFrame(OHLCV)] — 只需 close 列
        dates: pd.DatetimeIndex — 回测交易日序列（升序）
        symbols: List[str] — 候选品种
        weight_fn: Callable[[pd.Timestamp], Dict[str, float]] — 调仓日目标权重回调
            （仅调仓日调用；返回 {symbol: weight}，权重和=1；空 dict 表示空仓）
        rebalance: 调仓频率（'5D'/'D'/'W'/'M'/'ME' 或 RebalanceScheduler 对象）
        initial_capital: 初始资金
        start_date: 可选起始日期
        fee_config: 费率 {'commission_rate', 'stamp_tax_rate', 'min_commission'}

    Returns:
        AccountAnalyzer(daily_assets)
    """
    if start_date is not None:
        dates = dates[dates >= pd.Timestamp(start_date)]
    if len(dates) < 2:
        raise ValueError("vector 回测至少需要 2 个交易日")
    sym_to_idx = {c: i for i, c in enumerate(symbols)}
    n = len(dates)

    # 价格 + 收益率矩阵 (T × N)
    price_arr = np.full((n, len(symbols)), np.nan)
    for code in symbols:
        if code in assets:
            price_arr[:, sym_to_idx[code]] = assets[code]['close'].reindex(dates).values
    returns_arr = np.nan_to_num(np.diff(price_arr, axis=0) / (price_arr[:-1] + 1e-12), nan=0.0)

    # 调仓日
    rebalance_set = _make_rebalance_set(dates, rebalance)
    fee = fee_config or {'commission_rate': 0.0, 'stamp_tax_rate': 0.0, 'min_commission': 0.0}

    nav = float(initial_capital)
    daily_nav = {dates[0].date(): round(nav, 2)}
    current_weights: Dict[str, float] = {}

    for i in range(n):
        date = dates[i]

        # 1. 当日收益: 旧权重 × 当日收益率 (i-1 → i)
        if i > 0 and current_weights:
            ret = 0.0
            for c, w in current_weights.items():
                j = sym_to_idx.get(c)
                if j is not None:
                    ret += w * returns_arr[i - 1, j]
            nav *= (1.0 + ret)

        # 2. 调仓 (收盘后)
        if date in rebalance_set:
            new_weights = weight_fn(date) or {}

            # 手续费（卖出/买入分量）
            if current_weights:
                sell_val = sum((w - new_weights.get(c, 0.0)) * nav
                               for c, w in current_weights.items() if w > new_weights.get(c, 0.0))
                buy_val = sum((w - current_weights.get(c, 0.0)) * nav
                              for c, w in new_weights.items() if w > current_weights.get(c, 0.0))
                if sell_val > 0:
                    nav -= max(sell_val * fee['commission_rate'], fee['min_commission'])
                    nav -= sell_val * fee['stamp_tax_rate']
                if buy_val > 0:
                    nav -= max(buy_val * fee['commission_rate'], fee['min_commission'])

            current_weights = new_weights

        daily_nav[date.date()] = round(nav, 2)

    return AccountAnalyzer(daily_assets=daily_nav)
