"""
utils/mcts/v1/config.py — MCTS 变异配置（独立，不依赖 v5 TreeGenConfig）
"""

import random
from dataclasses import dataclass, field
from typing import Optional, Dict, Set


# ── 默认变量池 ──
MCTS_VARIABLES = ['CLOSE', 'OPEN', 'HIGH', 'LOW', 'VOLUME', 'AMOUNT']

# ── 默认常数池 ──
MCTS_CONSTANTS = [0.0, 0.5, 1.0, -1.0, 2.0, 0.01, 0.02, 0.05, 1.5, 3.0]

# ── 默认结构组权重 ──
MCTS_GROUP_WEIGHTS = {
    'ts_function':  30,
    'math_function': 15,
    'comparison':    15,
    'logic':         13,
    'binary_op':     13,
    'unary_op':       9,
    'ternary':        5,
}

# ── 默认时序函数权重（常用子集） ──
MCTS_TS_WEIGHTS = {
    'ts_rank': 3, 'ts_mean': 2, 'ts_std': 2,
    'ts_roc': 3, 'ts_delta': 2, 'ts_sum': 1,
    'ts_max': 1, 'ts_min': 1, 'ts_cov': 1,
    'ts_corr': 1, 'ts_skew': 1, 'ts_kurt': 1,
    'ts_ema': 1, 'ts_wma': 1, 'ts_mad': 1,
    'ts_delay': 1,
}

# ── 默认数学函数权重 ──
MCTS_MATH_WEIGHTS = {
    'abs': 2, 'log': 2, 'sign': 2,
    'sqrt': 1, 'square': 1, 'cube': 1,
}

# ── 默认变量权重 ──
MCTS_VAR_WEIGHTS = {
    'CLOSE': 5, 'OPEN': 3, 'HIGH': 3, 'LOW': 3,
    'VOLUME': 4, 'AMOUNT': 3,
}


@dataclass
class MutationConfig:
    """MCTS 变异配置（TreeGenConfig 的独立替代）

    控制变异算子的搜索空间和方向偏置。
    不依赖 v5 的 TreeGenConfig / FUNC_REGISTRY / FunctionSpec。
    """

    # ── 随机数 ──
    rng: random.Random = field(default_factory=random.Random)

    # ── 结构组权重 ──
    group_weights: Dict[str, float] = field(default_factory=lambda: dict(MCTS_GROUP_WEIGHTS))

    # ── 时序函数权重 ──
    ts_weights: Dict[str, float] = field(default_factory=lambda: dict(MCTS_TS_WEIGHTS))

    # ── 数学函数权重 ──
    math_weights: Dict[str, float] = field(default_factory=lambda: dict(MCTS_MATH_WEIGHTS))

    # ── 变量权重 ──
    var_weights: Dict[str, float] = field(default_factory=lambda: dict(MCTS_VAR_WEIGHTS))

    # ── 白名单（限制搜索空间） ──
    var_allowlist: Optional[Set[str]] = None      # 仅从这些变量中采样
    func_allowlist: Optional[Set[str]] = None      # 仅从这些函数中采样

    # ── 模式 ──
    mode: Optional[str] = None                     # None=hybrid | 'continuous' | 'predicate'

    def with_seed(self, seed: int) -> 'MutationConfig':
        """创建使用指定种子的配置副本"""
        import copy
        new_cfg = copy.deepcopy(self)
        new_cfg.rng = random.Random(seed)
        return new_cfg
