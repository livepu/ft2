"""
MCTSTree — MCTS 树管理类

核心职责:
  1. select()        — 从根按 UCB/贝叶斯增强 UCB 选路到叶节点
  2. expand()        — 从叶节点生成子节点（动作 + 约束 + 去重）
  3. backpropagate() — 从叶往根反向传播更新统计
  4. best_path()     — 回溯最优路径

选择策略:
  - standard_ucb  : 标准 UCB1
  - bayesian_ucb  : 贝叶斯增强 UCB（AlphaPROBE，默认推荐）
  - puct          : PUCT 变体（AlphaCFG）

依赖: 本地 actions / ast_utils / config / constraints / dedup
"""

import ast
import math
import random
from typing import Dict, List, Optional

from .node import MCTSNode
from .constraints import CFGGrammar, SemanticValidator
from .dedup import SubtreeHasher, FrequentSubtreeMonitor

from .actions import apply_action, get_available_actions
from .ast_utils import (
    _simplify_ast,
    _canonicalize_key,
    _expr_str,
)
from .config import ActionConfig


class MCTSTree:
    """MCTS 树：管理所有节点、路径、统计

    结构:
      root ── child1 ── grandchild1
        │                    └─ grandchild2
        └── child2 ── grandchild3
    """

    def __init__(self, root_expression: str):
        """
        Args:
          root_expression: 根表达式字符串
        """
        root_tree = self._parse_expression(root_expression)
        self.root = MCTSNode(
            expression=root_expression,
            tree=root_tree,
            depth=0,
            is_seed=True,
            expression_str=_expr_str(root_tree),
            signature=_canonicalize_key(root_tree),
        )

        # 索引
        self.all_nodes: Dict[str, MCTSNode] = {}           # signature → node
        self.signature_index: Dict[str, MCTSNode] = {}     # 去重索引
        self.subtree_freq: Dict[str, int] = {}             # 子树模式频率

        # 全局统计
        self.best_node: MCTSNode = self.root               # 全局最优
        self.best_path_nodes: List[MCTSNode] = []           # 最优路径节点
        self.total_evaluations: int = 0

        # 索引注册根节点
        if self.root.signature:
            self.all_nodes[self.root.signature] = self.root
            self.signature_index[self.root.signature] = self.root

    # ─────────────────────────────────────────────
    # Step 1: Selection
    # ─────────────────────────────────────────────

    def select(self, mode: str = 'bayesian_ucb',
               ucb_c: float = 1.414,
               gamma: float = 0.05, beta: float = 0.01) -> MCTSNode:
        """从根开始选择最优路径，直到叶节点

        Args:
          mode: 'standard_ucb' | 'bayesian_ucb' | 'puct'
          ucb_c: UCB 探索常数
          gamma: 贝叶斯深度惩罚系数
          beta: 贝叶斯出度惩罚系数
        """
        node = self.root
        path = [node]

        while not node.is_leaf:
            best_child = None
            best_score = -float('inf')

            for child in node.children:
                score = self._selection_score(
                    child, parent_visits=node.visit_count,
                    mode=mode, ucb_c=ucb_c,
                    gamma=gamma, beta=beta,
                )
                if score > best_score:
                    best_score = score
                    best_child = child

            if best_child is None:
                break  # 叶节点

            node = best_child
            path.append(node)

        return node

    def _selection_score(self, node: MCTSNode, parent_visits: int,
                         mode: str = 'bayesian_ucb',
                         ucb_c: float = 1.414,
                         gamma: float = 0.05, beta: float = 0.01) -> float:
        """计算子节点的选择得分"""
        if mode == 'standard_ucb':
            return self._ucb_score(node, parent_visits, ucb_c)
        elif mode == 'bayesian_ucb':
            return self._bayesian_ucb_score(node, parent_visits, ucb_c, gamma, beta)
        elif mode == 'puct':
            return self._puct_score(node, parent_visits, ucb_c)
        else:
            raise ValueError(f"未知选择模式: {mode}")

    def _ucb_score(self, node: MCTSNode, parent_visits: int,
                   C: float = 1.414) -> float:
        """标准 UCB1"""
        if node.visit_count == 0:
            # 未访问节点使用父节点 Q 作为先验（优于 float('inf') 全部优先）
            if node.parent and node.parent.visit_count > 0:
                return node.parent.q_value + C
            return C * 2

        Q = node.q_value
        explore = C * math.sqrt(math.log(max(parent_visits, 1)) / node.visit_count)
        return Q + explore

    def _bayesian_ucb_score(self, node: MCTSNode, parent_visits: int,
                            C: float = 1.414,
                            gamma: float = 0.05, beta: float = 0.01) -> float:
        """贝叶斯增强 UCB（AlphaPROBE 方案）

        P(F) = Normalized_Quality × (1-γ)^depth × (1-β)^outdegree
        Score = Q × prior + C × sqrt(lnN/n)
        """
        if node.visit_count == 0:
            if node.parent and node.parent.visit_count > 0:
                return node.parent.q_value * node.prior_quality + C
            return C * 2

        Q = node.q_value
        explore = C * math.sqrt(math.log(max(parent_visits, 1)) / node.visit_count)

        # 贝叶斯先验: 质量 × 深度折扣 × 出度折扣
        depth_discount = (1 - gamma) ** node.depth
        outdeg_discount = (1 - beta) ** node.outdegree
        prior = node.prior_quality * depth_discount * outdeg_discount

        return Q * prior + explore

    def _puct_score(self, node: MCTSNode, parent_visits: int,
                    c_puct: float = 1.0) -> float:
        """PUCT 变体（AlphaCFG 方案）

        PUCT = Q + c_puct × prior_prob × sqrt(N_parent) / (1 + N_node)
        """
        Q = node.q_value if node.visit_count > 0 else 0.0
        prior_prob = node.prior_quality
        explore = (c_puct * prior_prob *
                   math.sqrt(max(parent_visits, 1)) / (1 + node.visit_count))
        return Q + explore

    # ─────────────────────────────────────────────
    # Step 2: Expansion
    # ─────────────────────────────────────────────

    def expand(self, node: MCTSNode,
               action_config: ActionConfig,
               n_branches: int = 3,
               max_depth: int = 6,
               cfg: Optional[CFGGrammar] = None,
               semantic: Optional[SemanticValidator] = None,
               subtree_monitor: Optional[FrequentSubtreeMonitor] = None,
               best_pool: Optional[List[MCTSNode]] = None,
               enable_graft: bool = False,
               rng: Optional[random.Random] = None) -> List[MCTSNode]:
        """从叶节点生成 n_branches 个子节点

        扩展流程:
          1. 从动作空间中随机选 n_branches 种动作
          2. 应用动作 → AST 候选
          3. CFG 语法检查 → 过滤无效候选
          4. 语义约束检查 → 过滤冗余表达式
          5. 子树同构去重 → 过滤重复结构
          6. 频繁子树回避 → 降低拥挤方向权重

        Returns:
          有效子节点列表（可能少于 n_branches）
        """
        if rng is None:
            rng = random.Random()

        children: List[MCTSNode] = []
        tried_signatures: set = set()

        # 获取可用动作列表
        available = get_available_actions(action_config, enable_graft)
        if not available:
            return children

        # 随机选 n_branches 种动作（可重复，因为同一动作在不同位置结果不同）
        selected_actions = [rng.choice(available) for _ in range(n_branches * 2)]  # 多选一些以防失败

        for action_name in selected_actions:
            if len(children) >= n_branches:
                break

            # 应用动作
            try:
                new_tree = apply_action(
                    action_name, node.tree, action_config, rng, best_pool,
                )
            except Exception:
                continue
            if new_tree is None:
                continue

            # AST 简化
            new_tree = _simplify_ast(new_tree)

            # 计算 signature
            sig = _canonicalize_key(new_tree)

            # 去重
            if sig in self.signature_index or sig in tried_signatures:
                continue
            tried_signatures.add(sig)

            # CFG 语法检查
            if cfg is not None:
                ok, _ = cfg.is_syntactically_valid(new_tree)
                if not ok:
                    continue

            # 语义约束检查
            if semantic is not None:
                ok, _ = semantic.check(new_tree)
                if not ok:
                    continue

            # 频繁子树回避（AlphaJungle FSA）
            if subtree_monitor is not None:
                hasher = SubtreeHasher()
                full_hash = hasher.compute_full_tree(new_tree)
                if subtree_monitor.is_frequent(full_hash):
                    avoid_weight = subtree_monitor.get_avoidance_weight(full_hash)
                    if rng.random() > avoid_weight:
                        continue

            # 创建子节点
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

    # ─────────────────────────────────────────────
    # Step 4: Backpropagation
    # ─────────────────────────────────────────────

    def backpropagate(self, node: MCTSNode, fitness: float,
                      train_fitness: float = -999.0,
                      valid_fitness: float = -999.0):
        """从叶节点向根反向传播，更新统计

        沿路径:
          1. visit_count += 1
          2. total_value += fitness
          3. reward_history 追加
          4. prior_quality 更新
          5. 父节点 outdegree += 1

        Args:
          node: 刚评估完的叶节点
          fitness: 评估 fitness（用于反向传播）
          train_fitness: 训练集 fitness（记录在节点上）
          valid_fitness: 验证集 fitness（记录在节点上）
        """
        # 更新叶节点自身
        node.fitness = fitness
        if train_fitness > -999:
            node.train_fitness = train_fitness
        if valid_fitness > -999:
            node.valid_fitness = valid_fitness

        # 更新树内最优
        # [修复] 2026-08-06 还原规范写法：原 UNIQUE_MARKER_v4 防御式改写逻辑等价
        # 但注释格式违规、变量名非语义化（_bn/_bnv），统一为直接比较。
        if self.best_node is None or fitness > self.best_node.fitness:
            self.best_node = node
            self.best_path_nodes = node.path_to_root()

        self.total_evaluations += 1

        # 沿路径向上传播
        current = node
        while current is not None:
            current.visit_count += 1
            current.total_value += fitness
            current.reward_history.append(fitness)

            # prior_quality: sigmoid(Q/t) 归一化到 (0, 1)
            #   t=0.5: Q=0→0.5, Q=±0.5→0.73/0.27, Q=±1→0.88/0.12
            #   光滑无硬截断, 在 Q>1.0 极值区间保留区分力 (clamp 会丢失)
            #   数值稳定: z=Q/t 超出 ±20 时直接取边界, 避免 exp 溢出 (fitness=-999 → Q≈-999)
            #   参考: AlphaPROBE(z-score+sigmoid) / AlphaCFG(softmax) / AlphaJungle(no prior)
            #   分析记录: k01/探索记录.md → prior_quality 归一化偏差
            if current.visit_count > 0:
                raw_q = current.q_value
                z = raw_q * 2.0          # z = Q / t, t=0.5
                if z > 20.0:
                    current.prior_quality = 1.0
                elif z < -20.0:
                    current.prior_quality = 0.0
                else:
                    current.prior_quality = 1.0 / (1.0 + math.exp(-z))

            # 父节点 outdegree += 1
            if current.parent is not None:
                current.parent.outdegree += 1

            current = current.parent

    # ─────────────────────────────────────────────
    # 贝叶斯先验
    # ─────────────────────────────────────────────

    def bayesian_prior(self, node: MCTSNode,
                       gamma: float = 0.05, beta: float = 0.01) -> float:
        """贝叶斯先验（AlphaPROBE）:
        P(F) = Normalized_Quality × (1-γ)^depth × (1-β)^outdegree
        """
        q = node.prior_quality
        depth_discount = (1 - gamma) ** node.depth
        outdeg_discount = (1 - beta) ** node.outdegree
        return q * depth_discount * outdeg_discount

    # ─────────────────────────────────────────────
    # 路径与查询
    # ─────────────────────────────────────────────

    def best_path(self) -> List[MCTSNode]:
        """返回当前最优路径（从根到最佳叶节点）"""
        if not self.best_path_nodes:
            self.best_path_nodes = self.best_node.path_to_root()
        # 反转成从根到叶
        return list(reversed(self.best_path_nodes))

    def get_node(self, signature: str) -> Optional[MCTSNode]:
        """按 signature 查询节点"""
        return self.signature_index.get(signature)

    def node_count(self) -> int:
        """树中总节点数"""
        return len(self.all_nodes)

    def leaf_count(self) -> int:
        """树中叶节点数"""
        return sum(1 for n in self.all_nodes.values() if n.is_leaf)

    def max_depth_reached(self) -> int:
        """当前最大树深度"""
        return max((n.depth for n in self.all_nodes.values()), default=0)

    # ─────────────────────────────────────────────
    # 工具
    # ─────────────────────────────────────────────

    @staticmethod
    def _parse_expression(expr_str: str) -> ast.Expression:
        """解析表达式字符串为 AST"""
        tree = ast.parse(expr_str.strip(), mode='eval')
        if not isinstance(tree, ast.Expression):
            raise ValueError(f"无法解析表达式: {expr_str}")
        # 简化
        return _simplify_ast(tree)
