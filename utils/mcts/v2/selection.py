"""
strategies/selection.py — 选择策略（全部可替换）
=============================================================================

设计:
  - SelectionStrategy 协议定义 select_child 接口
  - BayesianUCB / StandardUCB / PUCT 三种默认实现
  - 调用方可通过协议实现任意选择策略（因子/择时统一接口）

[重构] 2026-08-06 从 v1 tree.py 的 _selection_score / _ucb_score 等抽取。
"""

import math
from typing import Protocol, List, Optional


class SelectionStrategy(Protocol):
    """选择策略协议：给定父访问次数 + 子节点列表，选最优子节点"""

    def select_child(self, children: List['MCTSNode'],
                     parent_visits: int) -> Optional['MCTSNode']:
        """从 children 中选最优（按得分），返回 None 表示无可用子节点"""
        ...

    def score(self, node: 'MCTSNode', parent_visits: int) -> float:
        """计算单个子节点的选择得分"""
        ...


# ============================================================
# 默认实现
# ============================================================

class StandardUCB:
    """标准 UCB1"""

    def __init__(self, C: float = 1.414):
        self.C = C

    def score(self, node: 'MCTSNode', parent_visits: int) -> float:
        if node.visit_count == 0:
            if node.parent and node.parent.visit_count > 0:
                return node.parent.q_value + self.C
            return self.C * 2
        Q = node.q_value
        explore = self.C * math.sqrt(math.log(max(parent_visits, 1)) / node.visit_count)
        return Q + explore

    def select_child(self, children, parent_visits: int):
        best, best_score = None, -float('inf')
        for child in children:
            s = self.score(child, parent_visits)
            if s > best_score:
                best_score, best = s, child
        return best


class BayesianUCB:
    """贝叶斯增强 UCB（AlphaPROBE，v2 默认推荐）"""

    def __init__(self, C: float = 1.414, gamma: float = 0.05, beta: float = 0.01):
        self.C = C
        self.gamma = gamma
        self.beta = beta

    def score(self, node: 'MCTSNode', parent_visits: int) -> float:
        if node.visit_count == 0:
            if node.parent and node.parent.visit_count > 0:
                return node.parent.q_value * node.prior_quality + self.C
            return self.C * 2
        Q = node.q_value
        explore = self.C * math.sqrt(math.log(max(parent_visits, 1)) / node.visit_count)
        depth_discount = (1 - self.gamma) ** node.depth
        outdeg_discount = (1 - self.beta) ** node.outdegree
        prior = node.prior_quality * depth_discount * outdeg_discount
        return Q * prior + explore

    def select_child(self, children, parent_visits: int):
        best, best_score = None, -float('inf')
        for child in children:
            s = self.score(child, parent_visits)
            if s > best_score:
                best_score, best = s, child
        return best


class PUCT:
    """PUCT 变体（AlphaCFG 方案）"""

    def __init__(self, c_puct: float = 1.0):
        self.c_puct = c_puct

    def score(self, node: 'MCTSNode', parent_visits: int) -> float:
        Q = node.q_value if node.visit_count > 0 else 0.0
        prior_prob = node.prior_quality
        explore = (self.c_puct * prior_prob *
                   math.sqrt(max(parent_visits, 1)) / (1 + node.visit_count))
        return Q + explore

    def select_child(self, children, parent_visits: int):
        best, best_score = None, -float('inf')
        for child in children:
            s = self.score(child, parent_visits)
            if s > best_score:
                best_score, best = s, child
        return best


# 工厂函数（便捷选择）
_SELECTION_REGISTRY = {
    'standard_ucb': StandardUCB,
    'bayesian_ucb': BayesianUCB,
    'puct': PUCT,
}


def create_selection(mode: str = 'bayesian_ucb', **kwargs) -> SelectionStrategy:
    """根据 mode 创建选择策略"""
    cls = _SELECTION_REGISTRY.get(mode)
    if cls is None:
        raise ValueError(f"未知选择模式: {mode}，可用: {list(_SELECTION_REGISTRY.keys())}")
    return cls(**kwargs)
