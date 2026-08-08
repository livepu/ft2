"""
core/config.py — 引擎参数 + 动作配置（v2 独立模块）
=============================================================================

EngineConfig  : v2 新增，引擎主循环参数（v1 散落在 MCTSConfig 中的字段）
ActionConfig  : v1 搬运，7 种 AST 动作的空间边界

[重构] 2026-08-06 EngineConfig 与 ActionConfig 分离：引擎参数与动作空间边界不再耦合。
"""

import random
from dataclasses import dataclass, field
from typing import List, Set, Optional


# ============================================================
# 引擎参数
# ============================================================

@dataclass
class EngineConfig:
    """MCTS 搜索引擎参数（v2 新增，无默认值 = 调用方必须显式指定）

    所有参数均为领域无关的搜索控制参数，不含动作/变量/函数等业务配置。
    """

    # ── 迭代控制 ──
    n_iterations: int = 500          # 总迭代次数
    n_trees: int = 1                 # 并行树数（多树=多线程评估，默认单树串行）
    early_stop_rounds: int = 0       # 早停轮数（0=不停）
    max_depth: int = 6               # 最大 AST 深度

    # ── 选择策略参数 ──
    selection_mode: str = 'bayesian_ucb'  # standard_ucb | bayesian_ucb | puct
    ucb_constant: float = 1.414     # UCB 探索常数
    gamma: float = 0.05             # 贝叶斯深度折扣
    beta: float = 0.01              # 贝叶斯出度折扣

    # ── 扩展参数 ──
    n_branches: int = 3             # 每次扩展生成的子节点数
    enable_graft: bool = False      # 允许嫁接动作

    # ── 最优池参数 ──
    best_pool_size: int = 20        # 全局最优池容量（v1 默认 20）
    enable_diverse_pool: bool = True # 结构签名去重

    # ── 相似度折扣 ──
    enable_similarity_discount: bool = False  # AlphaCFG 相似度折扣（默认关）
    similarity_threshold: float = 0.3
    top_k_similar: int = 1

    # ── 日志 ──
    verbose: bool = True            # 打印进度
    log_every: int = 50             # 每 N 轮打印

    # ── 随机种子 ──
    seed: Optional[int] = None

    def __post_init__(self):
        if self.n_iterations < 1:
            raise ValueError("n_iterations 必须 >= 1")
        if self.max_depth < 1:
            raise ValueError("max_depth 必须 >= 1")
        if self.n_trees < 1:
            raise ValueError("n_trees 必须 >= 1")


# ============================================================
# 动作空间配置（v1 搬运）
# ============================================================

@dataclass
class ActionConfig:
    """7 种 AST 局部变换的动作空间边界

    定义哪些变量/函数/参数可用，以及哪些动作允许。
    这个配置在各场景（因子/择时）中通常不同。
    """

    # 变量列表
    allowed_variables: List[str] = field(default_factory=list)
    # 函数允许集
    allowed_functions: Set[str] = field(default_factory=set)
    # 可用动作
    allowed_actions: List[str] = field(default_factory=lambda: [
        'change_param', 'change_variable', 'change_function',
        'wrap_function', 'unwrap_function', 'add_condition', 'graft',
    ])
    # 窗口参数候选
    param_windows: List[int] = field(default_factory=lambda: [5, 10, 20, 60, 120])
    # 阈值候选
    param_thresholds: List[float] = field(default_factory=lambda: [0.05, 0.1, 0.2])
    # 随机种子
    seed: Optional[int] = None

    def __post_init__(self):
        if not self.allowed_variables:
            raise ValueError("allowed_variables 不能为空")
        if not self.allowed_functions:
            raise ValueError("allowed_functions 不能为空")
