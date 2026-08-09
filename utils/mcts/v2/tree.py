"""
core/tree.py — MCTS 树管理（v1 搬运 + v2 策略接口改造）
=============================================================================

核心改动（相比 v1）:
  - select() 接受 SelectionStrategy（外部注入，不硬编码 UCB 公式）
  - backpropagate 直接比较 best_node（v1 修复版，无 UNIQUE_MARKER_v4）
  - best_node 仅供树内最优，全局最优由 engine.best_tracker 维护

[搬运+改造] 2026-08-06 从 utils/mcts/v1/tree.py 搬运，select 接口策略化。
"""

import ast
import math
import random
from typing import Dict, List, Optional, Set

from .node import MCTSNode
from .dedup import SubtreeHasher, FrequentSubtreeMonitor
from .actions import apply_action, get_available_actions
from utils.ast.surgery import _simplify_ast, _canonicalize_key, _expr_str
from .config import ActionConfig


class MCTSTree:
    """MCTS 树：管理所有节点、路径、统计

    v2 变化：select 接受 SelectionStrategy 作为参数，不内置 UCB 公式。
    """

    def __init__(self, root_expression: str):
        root_tree = self._parse_expression(root_expression)
        self.root = MCTSNode(
            expression=root_expression,
            tree=root_tree,
            depth=0,
            is_seed=True,
            expression_str=_expr_str(root_tree),
            signature=_canonicalize_key(root_tree),
        )
        self.all_nodes: Dict[str, MCTSNode] = {}
        self.signature_index: Dict[str, MCTSNode] = {}
        self.subtree_freq: Dict[str, int] = {}

        self.best_node: MCTSNode = self.root
        self.best_path_nodes: List[MCTSNode] = []
        self.total_evaluations: int = 0

        if self.root.signature:
            self.all_nodes[self.root.signature] = self.root
            self.signature_index[self.root.signature] = self.root

    # ── Step 1: Selection（v2 改造：策略参数注入）──

    def select(self, selection_strategy,
               parent_visits: Optional[int] = None) -> MCTSNode:
        """从根开始按选择策略选路，直到叶节点

        Args:
          selection_strategy: SelectionStrategy（含 select_child 方法）
          parent_visits: 父访问次数（可选，用于跨树 UCB）
        """
        node = self.root
        while not node.is_leaf:
            pv = parent_visits if parent_visits is not None else node.visit_count
            best_child = selection_strategy.select_child(node.children, pv)
            if best_child is None:
                break
            node = best_child
        return node

    # ── Step 2: Expansion（v1 搬运，逻辑不变）──

    def expand(self, node: MCTSNode,
               action_config: ActionConfig,
               n_branches: int = 3,
               max_depth: int = 6,
               cm=None,  # 分级约束管理器（ConstraintManager，None=不约束）
               subtree_monitor: Optional[FrequentSubtreeMonitor] = None,
               best_pool: Optional[List[MCTSNode]] = None,
               enable_graft: bool = False,
               rng: Optional[random.Random] = None) -> List[MCTSNode]:
        if rng is None:
            rng = random.Random()
        children: List[MCTSNode] = []
        tried_signatures: set = set()
        available = get_available_actions(action_config, enable_graft)
        if not available:
            return children
        selected_actions = [rng.choice(available) for _ in range(n_branches * 2)]
        for action_name in selected_actions:
            if len(children) >= n_branches:
                break
            try:
                new_tree = apply_action(action_name, node.tree, action_config, rng, best_pool)
            except Exception:
                continue
            if new_tree is None:
                continue
            new_tree = _simplify_ast(new_tree)
            sig = _canonicalize_key(new_tree)
            if sig in self.signature_index or sig in tried_signatures:
                continue
            tried_signatures.add(sig)
            # 分级约束统一检查（Syntax/Semantic/Type 按 ConstraintManager 级别调度）
            # [收敛] 2026-08-09 原 cfg.is_syntactically_valid + semantic.check 双分支
            # 收敛为 cm.check 单入口（utils/ast/constraints.py）。
            if cm is not None:
                ok, _ = cm.check(new_tree)
                if not ok:
                    continue
            if subtree_monitor is not None:
                hasher = SubtreeHasher()
                full_hash = hasher.compute_full_tree(new_tree)
                if subtree_monitor.is_frequent(full_hash):
                    avoid_weight = subtree_monitor.get_avoidance_weight(full_hash)
                    if rng.random() > avoid_weight:
                        continue
            child = MCTSNode(
                expression=_expr_str(new_tree),
                tree=new_tree,
                parent=node,
                depth=node.depth + 1,
                generation=self.total_evaluations + len(children) + 1,
                expression_str=_expr_str(new_tree),
                signature=sig,
                edge=action_name,
            )
            self.all_nodes[sig] = child
            self.signature_index[sig] = child
            node.children.append(child)
            children.append(child)
        return children

    # ── Step 4: Backpropagation（v1 修复版，无 UNIQUE_MARKER_v4）──

    def backpropagate(self, node: MCTSNode, score: float,
                      train_fitness: float = -999.0,
                      valid_fitness: float = -999.0):
        """从叶节点向根反向传播更新统计

        数据流: score → node.fitness / total_value / best_node 比较

        [修复] 2026-08-06 直接比较 best_node（规范围写法，v1 原为 UNIQUE_MARKER_v4）。
        """
        node.fitness = score
        if train_fitness > -999:
            node.train_fitness = train_fitness
        if valid_fitness > -999:
            node.valid_fitness = valid_fitness

        # 更新树内最优
        if self.best_node is None or score > self.best_node.fitness:
            self.best_node = node
            self.best_path_nodes = node.path_to_root()

        self.total_evaluations += 1

        current = node
        while current is not None:
            current.visit_count += 1
            current.total_value += score
            current.reward_history.append(score)
            if current.visit_count > 0:
                raw_q = current.q_value
                z = raw_q * 2.0
                if z > 20.0:
                    current.prior_quality = 1.0
                elif z < -20.0:
                    current.prior_quality = 0.0
                else:
                    current.prior_quality = 1.0 / (1.0 + math.exp(-z))
            if current.parent is not None:
                current.parent.outdegree += 1
            current = current.parent

    # ── 路径与查询 ──

    def best_path(self) -> List[MCTSNode]:
        if not self.best_path_nodes:
            self.best_path_nodes = self.best_node.path_to_root()
        return list(reversed(self.best_path_nodes))

    def get_node(self, signature: str) -> Optional[MCTSNode]:
        return self.signature_index.get(signature)

    def node_count(self) -> int:
        return len(self.all_nodes)

    @staticmethod
    def _parse_expression(expr_str: str) -> ast.Expression:
        tree = ast.parse(expr_str.strip(), mode='eval')
        if not isinstance(tree, ast.Expression):
            raise ValueError(f"无法解析表达式: {expr_str}")
        return _simplify_ast(tree)
