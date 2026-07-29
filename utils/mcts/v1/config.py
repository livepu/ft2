"""
utils/mcts/v1/config.py — MCTS 动作空间配置

MCTS 不需要 GP 的"树生成权重"，只需要定义:
  1. 允许哪些变量/函数（搜索空间边界）
  2. 允许哪些动作（动作空间）
  3. 参数的可选值（窗口/阈值）

函数池从 AST v2 FUNC_REGISTRY 动态读取——注册新函数后 MCTS 自动可用。
探索级函数集可通过 get_functions_by_category() 按分类组合。
"""

import random
from dataclasses import dataclass, field
from typing import Set, List, FrozenSet, Optional


# ============================================================
# 函数池 — 从 AST v2 注册表动态读取
# ============================================================

def get_functions_by_category(*categories: str) -> Set[str]:
    """按 GP 分类获取函数集，用于探索级原语配比。

    例:
      get_functions_by_category('ts_function', 'math_function') → {ts_rank, ts_kurt, abs, log, ...}
      get_functions_by_category('cs_function')                  → {cs_rank, cs_zscore, ...}
    """
    try:
        from utils.ast.v2.registry import FUNC_CATEGORIES, FUNC_REGISTRY
        funcs = set()
        for cat in categories:
            funcs.update(FUNC_CATEGORIES.get(cat, []))
        return {f for f in funcs
                if f in FUNC_REGISTRY
                and FUNC_REGISTRY[f].data_args > 0
                and not FUNC_REGISTRY[f].macro_body}
    except ImportError:
        return set()


def get_functions_except(*exclude_categories: str) -> Set[str]:
    """获取排除指定分类后的函数集。

    例（单变量探索排除多变量 TA 指标）:
      get_functions_except('ta_function')  → 所有非 TA 的时序+截面+数学函数
    """
    try:
        from utils.ast.v2.registry import FUNC_CATEGORIES
        exclude = set()
        for cat in exclude_categories:
            exclude.update(FUNC_CATEGORIES.get(cat, []))
        return _get_default_functions() - exclude
    except ImportError:
        return set()


def _get_default_functions() -> Set[str]:
    """从 FUNC_REGISTRY 获取所有 data_args > 0 的非宏函数。"""
    try:
        from utils.ast.v2.registry import FUNC_REGISTRY
        return {name for name, spec in FUNC_REGISTRY.items()
                if spec.data_args > 0 and not spec.macro_body}
    except ImportError:
        return set(_DEFAULT_FUNCTIONS_FALLBACK)


def _filter_funcs_by_vars(allowed_functions: Set[str],
                          var_allowlist: Set[str]) -> Set[str]:
    """排除 data_vars 超限的函数（如单变量 HIGH 模式排除 atr）。

    例: var_allowlist={'HIGH'}, atr 的 data_vars=['HIGH','LOW','CLOSE']
    → atr 被排除（需要 LOW/CLOSE 但不在白名单）。
    """
    try:
        from utils.ast.v2.registry import FUNC_REGISTRY
        filtered = set()
        excluded = []
        for f in allowed_functions:
            spec = FUNC_REGISTRY.get(f.lower())
            if spec and spec.data_vars:
                if not all(v in var_allowlist for v in spec.data_vars):
                    excluded.append(f)
                    continue
            filtered.add(f)
        if excluded:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[MCTS] var_allowlist={var_allowlist} → 自动排除: {sorted(excluded)}"
            )
        return filtered
    except ImportError:
        return allowed_functions


# ============================================================
# 回退默认值（FUNC_REGISTRY 不可用时）
# ============================================================

_DEFAULT_FUNCTIONS_FALLBACK: FrozenSet[str] = frozenset({
    'ts_rank', 'ts_mean', 'ts_std', 'ts_roc', 'ts_delta',
    'ts_sum', 'ts_max', 'ts_min', 'ts_skew', 'ts_kurt',
    'ts_mad', 'ts_ema', 'ts_wma', 'ts_delay',
    'cs_rank', 'cs_zscore', 'cs_scale',
    'abs', 'log', 'sign', 'sqrt', 'square', 'cube', 'neg',
})

# ── 默认变量池 ──
DEFAULT_VARIABLES: FrozenSet[str] = frozenset({
    'CLOSE', 'OPEN', 'HIGH', 'LOW', 'VOLUME', 'AMOUNT',
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

# ── 默认窗口参数可选值（全局回退，按函数粒度的参数优先查 registry.param_pool）──
DEFAULT_PARAM_WINDOWS: List[int] = [5, 10, 20, 40, 60]

# ── 默认阈值参数可选值 ──
DEFAULT_PARAM_THRESHOLDS: List[float] = [0.0, 0.01, 0.02, 0.05, 0.1]


# ============================================================
# ActionConfig
# ============================================================

@dataclass
class ActionConfig:
    """MCTS 动作空间配置

    只定义"能做什么"，不定义"怎么做"的权重。
    MCTS 的方向选择由 UCB 负责，不由配置权重决定。

    参数:
      allowed_functions: None=从 FUNC_REGISTRY 自动获取全部; set=限定函数集
      var_allowlist: 变量白名单, 设为非空时 auto_filter_funcs 自动排除不兼容函数
      auto_filter_funcs: True=自动根据 var_allowlist 排除 data_vars 超限的函数
    """

    # ── 随机数 ──
    rng: random.Random = field(default_factory=random.Random)

    # ── 搜索空间边界 ──
    allowed_variables: Set[str] = field(default_factory=lambda: set(DEFAULT_VARIABLES))
    allowed_functions: Set[str] = field(default_factory=_get_default_functions)

    # ── 动作空间 ──
    allowed_actions: Set[str] = field(default_factory=lambda: set(DEFAULT_ACTIONS))

    # ── 参数可选值（全局回退）──
    param_windows: List[int] = field(default_factory=lambda: list(DEFAULT_PARAM_WINDOWS))
    param_thresholds: List[float] = field(default_factory=lambda: list(DEFAULT_PARAM_THRESHOLDS))

    # ── 变量作用域过滤 ──
    var_allowlist: Optional[Set[str]] = None
    auto_filter_funcs: bool = True

    def __post_init__(self):
        """自动根据 var_allowlist 过滤不兼容的函数。"""
        if self.var_allowlist and self.auto_filter_funcs:
            self.allowed_functions = _filter_funcs_by_vars(
                self.allowed_functions, self.var_allowlist)

    def with_seed(self, seed: int) -> 'ActionConfig':
        """创建使用指定种子的配置副本"""
        import copy
        new_cfg = copy.deepcopy(self)
        new_cfg.rng = random.Random(seed)
        return new_cfg
