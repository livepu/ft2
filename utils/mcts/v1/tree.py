"""
MCTSTree — MCTS 树管理类

核心职责:
  1. select()      — 从根按 UCB/贝叶斯增强 UCB 选路到叶节点
  2. expand()      — 从叶节点生成子节点（变异 + CFG 约束 + 去重）
  3. backpropagate() — 从叶往根反向传播更新统计
  4. best_path()   — 回溯最优路径

选择策略（§4.1）:
  - standard_ucb  : 标准 UCB1
  - bayesian_ucb  : 贝叶斯增强 UCB（AlphaPROBE，默认推荐）
  - puct          : PUCT 变体（AlphaCFG，需要策略网络时使用）

依赖:
  - 复用 v5 tree_gen 变异算子
  - 复用 v5 ast_utils 工具函数
  - 复用本地 config.py MutationConfig
"""

import ast
import math
import random
from typing import Dict, List, Optional, Tuple, Callable

from .node import MCTSNode
from .constraints import CFGGrammar, SemanticValidator
from .dedup import SubtreeHasher, FrequentSubtreeMonitor

# 本地模块
from .mutations import (
    _mutate_subtree,
    _mutate_param,
    _mutate_logic,
    _mutate_insert_condition,
)
from .ast_utils import (
    _simplify_ast,
    _canonicalize_key,
    _expr_str,
    _replace_subtree,
    _collect_replaceable,
)
from .config import MutationConfig


# ── 可用的变异算子 ──
_MUTATION_OPS = {
    'subtree': _mutate_subtree,
    'param': _mutate_param,
    'logic': _mutate_logic,
    'condition': _mutate_insert_condition,
}


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
          root_expression: 根因子表达式字符串
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
               mutation_config: MutationConfig,
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
          1. 选择变异策略（从 _MUTATION_OPS 中选取）
          2. 应用变异 → AST 候选
          3. CFG 语法检查 → 过滤无效候选
          4. 语义约束检查 → 过滤冗余表达式
          5. 深度检查 → 过滤超限候选
          6. 子树同构去重 → 过滤重复结构
          7. 频繁子树回避 → 降低拥挤方向权重（不硬拒绝）
          8. 可选: 嫁接变异

        Returns:
          有效子节点列表（可能少于 n_branches）
        """
        if rng is None:
            rng = random.Random()

        children: List[MCTSNode] = []
        tried_signatures: set = set()

        # 选择变异策略
        op_names = list(_MUTATION_OPS.keys())
        rng.shuffle(op_names)
        selected_ops = op_names[:n_branches]

        for op_name in selected_ops:
            mutate_fn = _MUTATION_OPS[op_name]

            try:
                mutated_tree = mutate_fn(mutation_config, node.tree, max_depth)
            except Exception:
                continue

            # AST 简化
            mutated_tree = _simplify_ast(mutated_tree)

            # 计算 signature
            sig = _canonicalize_key(mutated_tree)

            # 去重: 跳过已有节点
            if sig in self.signature_index:
                continue
            if sig in tried_signatures:
                continue
            tried_signatures.add(sig)

            # CFG 语法检查
            if cfg is not None:
                ok, msg = cfg.is_syntactically_valid(mutated_tree)
                if not ok:
                    continue

            # 语义约束检查
            if semantic is not None:
                ok, msg = semantic.check(mutated_tree)
                if not ok:
                    continue

            # 频繁子树回避（降低权重但不硬拒绝）
            if subtree_monitor is not None:
                hasher = SubtreeHasher()
                full_hash = hasher.compute_full_tree(mutated_tree)
                if subtree_monitor.is_frequent(full_hash):
                    avoid_weight = subtree_monitor.get_avoidance_weight(full_hash)
                    if rng.random() > avoid_weight:
                        continue  # 概率性拒绝

            # 创建子节点
            child = MCTSNode(
                expression=_expr_str(mutated_tree),
                tree=mutated_tree,
                parent=node,
                depth=node.depth + 1,
                generation=self.total_evaluations + len(children) + 1,
                expression_str=_expr_str(mutated_tree),
                signature=sig,
                edge=op_name,
            )

            # 注册索引
            self.all_nodes[sig] = child
            self.signature_index[sig] = child
            node.children.append(child)
            children.append(child)

        # 可选: 嫁接变异（从最优池摘取子树）
        if enable_graft and best_pool and len(best_pool) > 1 and len(children) < n_branches:
            graft_child = self._graft_mutation(
                node, best_pool, mutation_config,
                cfg=cfg, semantic=semantic, rng=rng,
            )
            if graft_child is not None:
                children.append(graft_child)

        return children

    def _graft_mutation(self, node: MCTSNode, best_pool: List[MCTSNode],
                        cfg_config: MutationConfig,
                        cfg: Optional[CFGGrammar] = None,
                        semantic: Optional[SemanticValidator] = None,
                        max_tries: int = 5,
                        rng: Optional[random.Random] = None) -> Optional[MCTSNode]:
        """嫁接变异: 从全局最优池取子树嫁接到当前节点

        这是 MCTS 下对"交叉"的最优替代：
          - GP 交叉: 两个个体的子树随机交换
          - MCTS 嫁接: 最优池的子树 → 当前路径的叶节点
        """
        if rng is None:
            rng = random.Random()

        for _ in range(max_tries):
            donor = rng.choice(best_pool)
            if donor is node or donor.tree is None:
                continue

            # 从当前节点收集可替换位置
            replaceable = _collect_replaceable(node.tree, mode='any')
            if not replaceable:
                continue
            graft_point = rng.choice(replaceable)

            # 从捐赠者收集可摘取的子树
            donor_replaceable = _collect_replaceable(donor.tree, mode='any')
            if not donor_replaceable:
                continue
            donor_subtree = rng.choice(donor_replaceable)

            # 执行替换
            try:
                new_tree = node.tree
                ok = _replace_subtree(new_tree, graft_point, donor_subtree)
                if not ok:
                    continue
                new_tree = _simplify_ast(new_tree)
            except Exception:
                continue

            # 计算签名并去重
            sig = _canonicalize_key(new_tree)
            if sig in self.signature_index:
                continue

            # 约束检查
            if cfg is not None:
                ok, _ = cfg.is_syntactically_valid(new_tree)
                if not ok:
                    continue
            if semantic is not None:
                ok, _ = semantic.check(new_tree)
                if not ok:
                    continue

            child = MCTSNode(
                expression=_expr_str(new_tree),
                tree=new_tree,
                parent=node,
                depth=node.depth + 1,
                generation=self.total_evaluations + 1,
                expression_str=_expr_str(new_tree),
                signature=sig,
                edge=f'graft_from_{donor.signature[:8]}',
            )

            self.all_nodes[sig] = child
            self.signature_index[sig] = child
            node.children.append(child)
            return child

        return None

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

        # 更新全局最优
        if fitness > self.best_node.fitness:
            self.best_node = node
            self.best_path_nodes = node.path_to_root()

        self.total_evaluations += 1

        # 沿路径向上传播
        current = node
        while current is not None:
            current.visit_count += 1
            current.total_value += fitness
            current.reward_history.append(fitness)

            # prior_quality: 用平均 Q 值归一化到 [0, 1]
            if current.visit_count > 0:
                raw_q = current.q_value
                current.prior_quality = max(0.0, min(1.0, (raw_q + 1.0) / 2.0))

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
        """解析因子表达式字符串为 AST"""
        tree = ast.parse(expr_str.strip(), mode='eval')
        if not isinstance(tree, ast.Expression):
            raise ValueError(f"无法解析表达式: {expr_str}")
        # 简化
        return _simplify_ast(tree)
