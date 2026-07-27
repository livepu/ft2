"""
utils/mcts/v1/config.py — MCTS 动作空间配置（极简）

MCTS 不需要 GP 的"树生成权重"，只需要定义:
  1. 允许哪些变量/函数（搜索空间边界）
  2. 允许哪些动作（动作空间）
  3. 参数的可选值（窗口/阈值）
"""

import random
from dataclasses import dataclass, field
from typing import Set, List, FrozenSet


# ── 默认变量池 ──
DEFAULT_VARIABLES: FrozenSet[str] = frozenset({
    'CLOSE', 'OPEN', 'HIGH', 'LOW', 'VOLUME', 'AMOUNT',
})

# ── 默认函数池 ──
DEFAULT_FUNCTIONS: FrozenSet[str] = frozenset({
    # 时序（1 数据参数 + 1 窗口）
    'ts_rank', 'ts_mean', 'ts_std', 'ts_roc', 'ts_delta',
    'ts_sum', 'ts_max', 'ts_min', 'ts_skew', 'ts_kurt',
    'ts_mad', 'ts_ema', 'ts_wma', 'ts_delay',
    # 时序成对（2 数据参数 + 1 窗口）
    'ts_cov', 'ts_corr',
    # 截面（1 数据参数）
    'cs_rank', 'cs_zscore', 'cs_scale',
    # 数学（1 数据参数）
    'abs', 'log', 'sign', 'sqrt', 'square', 'cube',
})

# ── 默认动作池 ──
DEFAULT_ACTIONS: FrozenSet[str] = frozenset({
    'change_param',
    'change_variable',
    'change_function',
    'wrap_function',
    'unwrap_function',
    'add_condition',
    # graft 需要最优池，由 engine 单独控制
})

# ── 默认窗口参数可选值 ──
DEFAULT_PARAM_WINDOWS: List[int] = [5, 10, 20, 40, 60]

# ── 默认阈值参数可选值 ──
DEFAULT_PARAM_THRESHOLDS: List[float] = [0.0, 0.01, 0.02, 0.05, 0.1]


@dataclass
class ActionConfig:
    """MCTS 动作空间配置

    只定义"能做什么"，不定义"怎么做"的权重。
    MCTS 的方向选择由 UCB 负责，不由配置权重决定。
    """

    # ── 随机数 ──
    rng: random.Random = field(default_factory=random.Random)

    # ── 搜索空间边界 ──
    allowed_variables: Set[str] = field(default_factory=lambda: set(DEFAULT_VARIABLES))
    allowed_functions: Set[str] = field(default_factory=lambda: set(DEFAULT_FUNCTIONS))

    # ── 动作空间 ──
    allowed_actions: Set[str] = field(default_factory=lambda: set(DEFAULT_ACTIONS))

    # ── 参数可选值 ──
    param_windows: List[int] = field(default_factory=lambda: list(DEFAULT_PARAM_WINDOWS))
    param_thresholds: List[float] = field(default_factory=lambda: list(DEFAULT_PARAM_THRESHOLDS))

    def with_seed(self, seed: int) -> 'ActionConfig':
        """创建使用指定种子的配置副本"""
        import copy
        new_cfg = copy.deepcopy(self)
        new_cfg.rng = random.Random(seed)
        return new_cfg
