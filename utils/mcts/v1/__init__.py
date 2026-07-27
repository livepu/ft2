"""
utils/mcts/v1 — MCTS 因子搜索引擎 v1（零外部依赖）

架构 (9 个文件):
  1. node.py        → MCTSNode 数据结构
  2. tree.py        → MCTSTree 管理类（select / expand / backpropagate）
  3. engine.py      → MCTSEngine 主循环
  4. constraints.py → CFG 语法约束 + 语义检查
  5. dedup.py       → 子树同构检测 + FrequentSubtreeMonitor
  6. mutations.py   → 自包含树生成 + 4 种变异算子
  7. ast_utils.py   → AST 纯函数工具
  8. config.py      → MutationConfig
  9. cache.py       → 简单内存缓存

完全独立于 gp/v5，无任何外部模块依赖（除 stdlib）。
与 gp 同级目录（utils/mcts/ vs utils/gp/）。
"""

from .engine import MCTSEngine, MCTSConfig
from .node import MCTSNode
from .tree import MCTSTree
from .constraints import CFGGrammar, SemanticValidator
from .dedup import SubtreeHasher, FrequentSubtreeMonitor
from .config import MutationConfig
from .cache import SimpleFitnessCache

__all__ = [
    'MCTSEngine', 'MCTSConfig',
    'MCTSNode', 'MCTSTree',
    'CFGGrammar', 'SemanticValidator',
    'SubtreeHasher', 'FrequentSubtreeMonitor',
    'MutationConfig', 'SimpleFitnessCache',
]
