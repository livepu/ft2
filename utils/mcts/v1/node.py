"""
MCTSNode — MCTS 树节点数据结构

每个节点 = 一个因子表达式 + MCTS 统计 + 树结构关系。
节点本身是轻量 dataclass，不包含评估逻辑。

贝叶斯先验字段（AlphaPROBE 方案）:
  prior_quality : 归一化后的因子质量 (ICIR/SR)
  outdegree     : 被选作父因子的次数（出度惩罚用）
"""

import ast
import hashlib
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class MCTSNode:
    """MCTS 树节点 = 一个因子表达式

    生命周期:
      创建 → expand 产生子节点 → evaluate 计算 fitness → backpropagate 更新统计
    """

    # ── 因子核心 ──
    expression: str                          # 因子表达式字符串
    tree: ast.Expression                     # AST 树
    fitness: float = -999.0                  # 评估后的 fitness（-999 表示未评估）

    # ── MCTS 统计 ──
    visit_count: int = 0                     # 被访问次数（反向传播累计）
    total_value: float = 0.0                 # 累计价值总和（反向传播累计）
    reward_history: List[float] = field(default_factory=list)  # 历史 reward 序列（一致性惩罚用）

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
    signature: str = ''                      # 规范化缓存 key（v5 _canonicalize_key）

    # ── 贝叶斯先验（AlphaPROBE 方案） ──
    prior_quality: float = 1.0               # 归一化质量（0~1，评估后更新）
    outdegree: int = 0                       # 当前出度（被选作父因子的次数）

    # ── 子树同构检测（AlphaAgent 方案） ──
    subtree_hash: str = ''                   # 规范化 AST 子树哈希
    frequent_subtree_count: int = 0          # 该子树模式在历史中出现次数

    # ── 评估/训练分离 ──
    train_fitness: float = -999.0            # 训练集 fitness
    valid_fitness: float = -999.0            # 验证集 fitness（OOS）

    @property
    def q_value(self) -> float:
        """平均价值 Q = total_value / visit_count"""
        if self.visit_count == 0:
            return self.fitness if self.fitness > -999 else 0.0
        return self.total_value / self.visit_count

    @property
    def is_evaluated(self) -> bool:
        """是否已经过评估"""
        return self.fitness > -999.0

    @property
    def is_leaf(self) -> bool:
        """是否是叶节点（无子节点）"""
        return len(self.children) == 0

    @property
    def is_root(self) -> bool:
        """是否是根节点"""
        return self.parent is None

    def path_to_root(self) -> List['MCTSNode']:
        """从本节点到根的路径（含本节点和根）"""
        path = []
        node = self
        while node is not None:
            path.append(node)
            node = node.parent
        return path

    def sibling_count(self) -> int:
        """同级兄弟节点数量"""
        if self.parent is None:
            return 0
        return len(self.parent.children)

    def __repr__(self) -> str:
        fit_str = f"{self.fitness:.4f}" if self.is_evaluated else "NA"
        return (f"MCTSNode(expr={self.expression[:40]}..., "
                f"fit={fit_str}, Q={self.q_value:.4f}, "
                f"visits={self.visit_count}, depth={self.depth}, "
                f"outdeg={self.outdegree})")
