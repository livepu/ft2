"""
engine.py — MCTS 搜索引擎 v2（主循环编排）
=============================================================================

命名规范（统一数据流）:
  evaluator(tree) → evaluated → fitness.compute(evaluated) → score

设计原则（v2 根治 v1 事故）:
  - 引擎只编排 select→expand→evaluate→backprop，0 业务判断
  - 所有策略显式注入（无默认值），适配因子/择时/任意场景
  - 最优状态收敛到 BestTracker 单一维护点
  - 树操作委派给 MCTSTree，选择委派给 SelectionStrategy

[重构] 2026-08-06 基于 v1 事故教训完全重构。
[修复] 2026-08-07 主循环对齐 v1 行为：出度感知选树、select 后直接 expand、
  逐 child 评估/回传/更新池/注册子树、similarity discount 在评估内、early stop 用 stats 序列。
"""

import random
import time
from typing import List, Optional

from .node import MCTSNode
from .tree import MCTSTree
from .best_tracker import BestTracker
from .config import EngineConfig, ActionConfig
from .dedup import SubtreeHasher, FrequentSubtreeMonitor
from .cache import SimpleFitnessCache
from utils.ast.surgery import _canonicalize_key
from utils.ast.constraints import ConstraintManager
from .selection import SelectionStrategy, BayesianUCB


class MCTSEngine:
    """MCTS 搜索引擎 v2 — 显式注入、编排纯化

    v1 → v2 变化:
      - 所有策略外部注入（selection / fitness），构造时传入
      - BestTracker 替代 v1 的三处分散 best 状态
      - 主循环行为与 v1 完全一致（保证结果可复现）
    """

    def __init__(self,
                 # ── 核心注入（必须）──
                 evaluator,              # evaluator(tree) → evaluated
                 fitness,                # fitness.compute(evaluated) → score
                 action_config: ActionConfig,            # 动作空间边界

                 # ── 可选策略注入──
                 selection: Optional[SelectionStrategy] = None,  # 默认 BayesianUCB
                 validator=None,                         # ValidationStrategy（可选）
                 constraint_mgr: Optional[ConstraintManager] = None,  # [新] 分级约束
                 cfg_grammar=None,  # [兼容] 旧参数，自动包装进 ConstraintManager
                 semantic_validator=None,  # [兼容] 旧参数，自动包装进 ConstraintManager
                 subtree_monitor: Optional[FrequentSubtreeMonitor] = None,

                 # ── 引擎参数──
                 config: Optional[EngineConfig] = None,
                 # ── 种子表达式──
                 seed_expressions: Optional[List[str]] = None,
                 ):
        # 必需
        self.evaluator = evaluator
        self.fitness = fitness
        self.action_config = action_config

        # 策略（v2 显式注入，无隐藏默认值）
        self.selection = selection or BayesianUCB()
        self.validator = validator
        self.monitor = subtree_monitor

        # 约束系统统一走 ConstraintManager（分级约束，版本无关）
        # [收敛] 2026-08-09 旧的 cfg_grammar/semantic_validator 参数自动包装，
        # 新代码用 constraint_mgr=default_manager(...) 直接注入。
        self.cm = self._build_constraint_manager(
            constraint_mgr, cfg_grammar, semantic_validator)

        # 参数
        self.config = config or EngineConfig()

        # 状态
        self.best_tracker = BestTracker(
            best_pool_size=self.config.best_pool_size,
            enable_diverse_pool=self.config.enable_diverse_pool,
            signature_fn=self._structural_signature,   # [修复] 2026-08-07 对齐 v1 去重签名
        )
        self.trees: List[MCTSTree] = []

        # 缓存
        self._cache = SimpleFitnessCache()

        # 随机数
        self._rng = random.Random(self.config.seed)

        # 种子
        self.seed_expressions = seed_expressions or ['CLOSE']

        # 统计（对齐 v1 stats 结构）
        self.stats = {
            'best_fitness': [],
            'avg_fitness': [],
            'evaluations': [],
        }
        self.iteration: int = 0

        # 计时
        self.start_time: float = 0
        self.end_time: float = 0

    # ================================================================
    # 主循环（对齐 v1）
    # ================================================================

    def run(self):
        """执行 MCTS 搜索（主入口）"""
        self.start_time = time.time()

        # 1. 初始化树（每种子一棵树）
        self.trees = [MCTSTree(expr) for expr in self.seed_expressions]
        self._evaluate_seeds()

        # 2. 主迭代（v1 对齐）
        for i in range(self.config.n_iterations):
            self.iteration = i

            # 出度感知树选择（AlphaPROBE: 被探索多的树退避）
            outdegrees = [t.root.outdegree for t in self.trees]
            max_od = max(outdegrees) if outdegrees else 1
            weights = [max_od - od + 1 for od in outdegrees]  # 低出度→高权重
            tree = self._rng.choices(self.trees, weights=weights, k=1)[0]

            # Step 1: Selection（parent_visits 由 tree.select 内部用 node.visit_count）
            leaf = tree.select(self.selection)

            # Step 2: Expansion（v1: select 后直接 expand，不评估 leaf）
            children = tree.expand(
                leaf,
                action_config=self.action_config,
                n_branches=self.config.n_branches,
                max_depth=self.config.max_depth,
                cm=self.cm,                 # 分级约束（统一 ConstraintManager 入口）
                subtree_monitor=self.monitor,
                best_pool=self.best_tracker.top(),
                enable_graft=self.config.enable_graft,
                rng=self._rng,
            )

            # Step 3: Evaluation + Backprop（逐 child，v1 对齐）
            for child in children:
                score = self._evaluate_node(child)          # 评估（含缓存+折扣）
                tree.backpropagate(child, score,
                                   child.train_fitness, child.valid_fitness)
                self.best_tracker.update(child, trees=self.trees)
                if self.monitor is not None:
                    self.monitor.register(child.tree)

            # 统计 + 日志 + 早停（v1 对齐）
            self._record_stats()
            if self.config.verbose and (i + 1) % self.config.log_every == 0:
                self._log_progress(i + 1)
            if self._should_early_stop():
                if self.config.verbose:
                    print(f"[MCTS v2] 早停触发 (iter={i + 1})")
                break

        # 最终池验证（如果 validator 注入）
        self._verify_pool()

        self.end_time = time.time()

    # ================================================================
    # 内部方法
    # ================================================================

    def _build_constraint_manager(self, constraint_mgr, cfg_grammar,
                                  semantic_validator) -> Optional[ConstraintManager]:
        """构建统一约束管理器（单入口）

        优先级: constraint_mgr（新 API）> 旧 cfg_grammar/semantic_validator 自动包装 > None

        [收敛] 2026-08-09 旧的"语法白名单 + 语义校验"双参数收敛为
        utils/ast/constraints.py 的 ConstraintManager 分级约束；旧参数保留
        向后兼容（自动包装），新代码用 constraint_mgr=default_manager(...) 注入。
        """
        if constraint_mgr is not None:
            return constraint_mgr
        if cfg_grammar is None and semantic_validator is None:
            return None

        # 旧参数包装：语法层 + 语义层（级别按 SEMANTIC = 两段都启用）
        from utils.ast.constraints import (ConstraintLevel, SyntaxConstraint,
                                           SemanticConstraint)
        cm = ConstraintManager(level=ConstraintLevel.SEMANTIC)
        if cfg_grammar is not None:
            allowed = getattr(cfg_grammar, 'allowed_functions', None)
            cm.add(SyntaxConstraint(allowed_functions=allowed))
        if semantic_validator is not None:
            md = getattr(semantic_validator, 'max_depth', 6)
            mv = getattr(semantic_validator, 'min_variables', 1)
            cm.add(SemanticConstraint(max_depth=md, min_variables=mv))
        return cm

    def _evaluate_seeds(self):
        """评估所有种子节点，建立初始最优池（v1 对齐：含 backprop + pool + monitor）"""
        for tree in self.trees:
            root = tree.root
            if not root.is_evaluated:
                score = self._evaluate_node(root)
                tree.backpropagate(root, score,
                                   root.train_fitness, root.valid_fitness)
                self.best_tracker.update(root, trees=self.trees)
                if self.monitor is not None:
                    self.monitor.register(root.tree)

    def _evaluate_node(self, node: MCTSNode) -> float:
        """评估单节点（含缓存 + 相似度折扣），返回 score

        数据流: node.tree → evaluator → evaluated → fitness.compute → score
        [修复] 2026-08-07 相似度折扣对齐 v1：在评估内、条件 len(pool)>=10 且 depth>=3。
        """
        sig = node.signature or _canonicalize_key(node.tree)

        # 1. 查缓存
        cached = self._cache.get(sig)
        if cached is not None:
            node.fitness, node.train_fitness, node.valid_fitness = cached
            return node.fitness

        # 2. 求值
        try:
            evaluated = self.evaluator(node.tree)
            score = self.fitness.compute(evaluated)
        except Exception:
            score = -999.0

        # 3. AlphaCFG 相似度折扣（v1 对齐：池≥10 且 深度≥3）
        if (self.config.enable_similarity_discount
                and score > -999
                and len(self.best_tracker.top()) >= 10
                and node.depth >= 3):
            discount = self._compute_similarity_discount(node)
            score = score * discount

        node.fitness = float(score)
        node.train_fitness = float(score)
        node.valid_fitness = -999.0  # 搜索阶段不做切分，由 verify 做

        # 4. 写缓存
        self._cache.put(sig, (node.fitness, node.train_fitness, node.valid_fitness))
        return node.fitness

    # ── 相似度折扣（v1 对齐）──

    def _compute_similarity_discount(self, node: MCTSNode,
                                     alpha: float = 0.5) -> float:
        """AlphaCFG 结构相似度折扣（v1 对齐）

        仅池≥3 才计算；基于子树哈希 Jaccard 相似度；<80% 不扣，≥80% 轻度扣。
        """
        pool = self.best_tracker.top()
        if len(pool) < 3:
            return 1.0
        hasher = SubtreeHasher()
        node_hashes = set(hasher.extract_all_subtrees(node.tree))
        if not node_hashes:
            return 1.0
        max_sim = 0.0
        for best_node in pool[:5]:  # Top-5 冠军
            try:
                best_hashes = set(hasher.extract_all_subtrees(best_node.tree))
                if not best_hashes:
                    continue
                intersection = node_hashes & best_hashes
                union = node_hashes | best_hashes
                sim = len(intersection) / len(union)
                max_sim = max(max_sim, sim)
            except Exception:
                continue
        if max_sim < 0.8:
            return 1.0
        discount = 1.0 - alpha * max_sim
        return max(discount, 0.5)

    # ── 去重签名（v1 对齐：跳过等价外层包装）──

    def _structural_signature(self, node: MCTSNode) -> str:
        """提取结构签名：内层调用链（跳过 cs_rank/cs_zscore 等价包装）"""
        import ast as _ast
        hasher = SubtreeHasher()
        _cosmetic_wraps = {'cs_rank', 'cs_zscore', 'cs_scale', 'abs', 'log', 'sign'}
        tree = node.tree.body
        while isinstance(tree, _ast.Call):
            func_name = tree.func.id if isinstance(tree.func, _ast.Name) else ''
            if func_name not in _cosmetic_wraps:
                break
            tree = tree.args[0]
        return hasher.compute_full_tree(tree)

    # ── 统计 / 日志 / 早停（v1 对齐）──

    def _record_stats(self):
        all_fitness = [n.fitness for tree in self.trees
                       for n in tree.all_nodes.values()
                       if n.is_evaluated]
        self.stats['best_fitness'].append(
            max(all_fitness) if all_fitness else -999.0)
        self.stats['avg_fitness'].append(
            sum(all_fitness) / len(all_fitness) if all_fitness else -999.0)
        self.stats['evaluations'].append(
            sum(tree.total_evaluations for tree in self.trees))

    def _should_early_stop(self) -> bool:
        if self.config.early_stop_rounds <= 0:
            return False
        best_series = self.stats['best_fitness']
        if len(best_series) <= self.config.early_stop_rounds:
            return False
        recent_best = best_series[-self.config.early_stop_rounds:]
        historical_best = max(best_series[:-self.config.early_stop_rounds])
        if max(recent_best) <= historical_best:
            return True
        return False

    def _log_progress(self, iteration: int):
        elapsed = time.time() - self.start_time
        best_f = self.stats['best_fitness'][-1] if self.stats['best_fitness'] else -999
        total_nodes = sum(t.node_count() for t in self.trees)
        total_evals = sum(t.total_evaluations for t in self.trees)
        best_expr = self.best_tracker.best_expr()[:50] if self.best_tracker.best_expr() else ''
        print(f"[MCTS v2] iter={iteration:4d}/{self.config.n_iterations} "
              f"| best={best_f:.4f} | evals={total_evals} "
              f"| nodes={total_nodes} | elapsed={elapsed:.1f}s")
        if best_expr:
            print(f"           best_expr: {best_expr}")

    # ── 池验证 ──

    def _verify_pool(self):
        """候选池 IC 检验（如果 validator 注入）"""
        if self.validator is None:
            return
        if hasattr(self.fitness, 'verify'):
            try:
                for node in self.best_tracker.top():
                    self.fitness.verify(node.tree)
            except Exception:
                pass

    # ================================================================
    # 查询接口（对齐 v1 API，方便迁移）
    # ================================================================

    def best(self) -> Optional[MCTSNode]:
        """返回全局最优节点（对齐 v1 engine.best()）"""
        return self.best_tracker.global_best

    def best_pool(self) -> List[MCTSNode]:
        """返回全局最优池（对齐 v1 best_pool）"""
        return self.best_tracker.top()

    def report(self) -> dict:
        """搜索报告"""
        elapsed = self.end_time - self.start_time if self.end_time > 0 else 0
        return {
            **self.best_tracker.report(),
            'elapsed_sec': round(elapsed, 1),
            'trees': len(self.trees),
            'total_nodes': sum(t.node_count() for t in self.trees),
            'cache_size': len(self._cache),
        }
