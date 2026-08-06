"""
core/node.py — MCTS 树节点数据结构（v1 搬运，精简未使用字段）
=============================================================================

[搬运] 2026-08-06 从 utils/mcts/v1/node.py 搬运，保留核心字段。
  v2 引擎不再使用 subtree_hash/frequent_subtree_count（best_tracker 统一管理）。
"""

import ast
import hashlib
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class MCTSNode:
    """MCTS 树节点 = 一个表达式

    生命周期:
      创建 → expand 产生子节点 → evaluate 计算 fitness → backpropagate 更新统计
    """

    # ── 表达式核心 ──
    expression: str                          # 表达式字符串
    tree: ast.Expression                     # AST 树
    fitness: float = -999.0                  # 评估后的 fitness（-999 表示未评估）

    # ── MCTS 统计 ──
    visit_count: int = 0                     # 被访问次数（反向传播累计）
    total_value: float = 0.0                 # 累计价值总和
    reward_history: List[float] = field(default_factory=list)

    # ── 树结构 ──
    parent: Optional['MCTSNode'] = None
    children: List['MCTSNode'] = field(default_factory=list)
    edge: Optional[str] = None               # 从父到本节点的变异操作描述

    # ── 元信息 ──
    depth: int = 0                           # 树深度（根=0）
    is_seed: bool = False                    # 是否是种子节点
    generation: int = 0                      # 创建时的代数
    expression_str: str = ''                 # _expr_str 缓存

    # ── 去重签名 ──
    signature: str = ''                      # 规范化缓存 key

    # ── 贝叶斯先验 ──
    prior_quality: float = 1.0               # 归一化质量（0~1）
    outdegree: int = 0                       # 当前出度

    # ── 评估/训练分离 ──
    train_fitness: float = -999.0
    valid_fitness: float = -999.0

    @property
    def q_value(self) -> float:
        if self.visit_count == 0:
            return self.fitness if self.fitness > -999 else 0.0
        return self.total_value / self.visit_count

    @property
    def is_evaluated(self) -> bool:
        return self.fitness > -999.0

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    @property
    def is_root(self) -> bool:
        return self.parent is None

    def path_to_root(self) -> List['MCTSNode']:
        path = []
        node = self
        while node is not None:
            path.append(node)
            node = node.parent
        return path

    def sibling_count(self) -> int:
        if self.parent is None:
            return 0
        return len(self.parent.children)

    def __repr__(self) -> str:
        fit_str = f"{self.fitness:.4f}" if self.is_evaluated else "NA"
        return (f"MCTSNode(expr={self.expression[:40]}..., "
                f"fit={fit_str}, Q={self.q_value:.4f}, "
                f"visits={self.visit_count}, depth={self.depth}, "
                f"outdeg={self.outdegree})")
