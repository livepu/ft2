"""
utils/mcts/v2/ — MCTS 搜索引擎 v2（扁平模块，对齐 GP v5 风格）
=============================================================================

设计:
  - 引擎只做编排（select→expand→evaluate→backprop），0 业务判断
  - 通过构造参数显式注入 evaluator + fitness + selection，适配因子/择时/任意场景

与 v1 的关系:
  - v2 完全独立（不 import v1），复用代码通过"复制独立文件"实现
  - v1 保留供现有成果复现

[重构] 2026-08-06 基于 v1 事故教训：BestTracker 收敛全局最优、UCB 选择策略独立、
  场景策略（fitness/validation）归属于应用层。
"""
from .engine import MCTSEngine
from .config import EngineConfig
from .node import MCTSNode
from .tree import MCTSTree
from .best_tracker import BestTracker

__all__ = [
    'MCTSEngine', 'EngineConfig', 'MCTSNode', 'MCTSTree', 'BestTracker',
]
