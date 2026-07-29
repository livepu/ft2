"""
utils/mcts/v1 — MCTS 树搜索引擎 v1

定位:
  纯搜索引擎，不绑定任何评估逻辑。评估通过外部注入的
  evaluator + fitness_calculator 完成，与 gp/v5 架构一致。

函数元数据: 从 AST v2 FUNC_REGISTRY 动态读取（单一致信源）。
自定义函数只需 register_function() 注册一次，MCTS 自动识别。

架构 (9 个文件):
  1. node.py        → MCTSNode 数据结构
  2. tree.py        → MCTSTree（select / expand / backpropagate）
  3. engine.py      → MCTSEngine 主循环 + MCTSConfig
  4. actions.py     → 7 种搜索动作（AST 局部变换，参数从 registry 推导）
  5. config.py      → ActionConfig + 探索级函数组合 API
  6. constraints.py → CFG 语法约束 + 语义检查
  7. dedup.py       → 子树同构检测 + FrequentSubtreeMonitor
  8. ast_utils.py   → AST 纯函数工具
  9. cache.py       → SimpleFitnessCache
"""

from .engine import MCTSEngine, MCTSConfig
from .node import MCTSNode
from .tree import MCTSTree
from .constraints import CFGGrammar, SemanticValidator
from .dedup import SubtreeHasher, FrequentSubtreeMonitor
from .config import (
    ActionConfig,
    get_functions_by_category,
    get_functions_except,
)
from .cache import SimpleFitnessCache

__all__ = [
    'MCTSEngine', 'MCTSConfig',
    'MCTSNode', 'MCTSTree',
    'CFGGrammar', 'SemanticValidator',
    'SubtreeHasher', 'FrequentSubtreeMonitor',
    'ActionConfig', 'get_functions_by_category', 'get_functions_except',
    'SimpleFitnessCache',
]
