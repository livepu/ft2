"""
utils/mcts/v1 — MCTS 因子搜索引擎 v1（零外部依赖，MCTS 原生架构）

架构 (9 个文件):
  1. node.py        → MCTSNode 数据结构
  2. tree.py        → MCTSTree（select / expand / backpropagate）
  3. engine.py      → MCTSEngine 主循环 + MCTSConfig
  4. actions.py     → 7 种因子动作（局部变换，非 GP 变异）
  5. config.py      → ActionConfig（5 字段极简配置）
  6. constraints.py → CFG 语法约束 + 语义检查
  7. dedup.py       → 子树同构检测 + FrequentSubtreeMonitor
  8. ast_utils.py   → AST 纯函数工具
  9. cache.py       → SimpleFitnessCache

完全独立于 gp/v5，无任何外部模块依赖（除 stdlib）。
"""

from .engine import MCTSEngine, MCTSConfig
from .node import MCTSNode
from .tree import MCTSTree
from .constraints import CFGGrammar, SemanticValidator
from .dedup import SubtreeHasher, FrequentSubtreeMonitor
from .config import ActionConfig
from .cache import SimpleFitnessCache

__all__ = [
    'MCTSEngine', 'MCTSConfig',
    'MCTSNode', 'MCTSTree',
    'CFGGrammar', 'SemanticValidator',
    'SubtreeHasher', 'FrequentSubtreeMonitor',
    'ActionConfig', 'SimpleFitnessCache',
]
