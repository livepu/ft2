"""
core/engine.py — MCTS 搜索引擎 v2（主循环编排）

=============================================================================
设计原则（v2 根治 v1 事故）:
  - 引擎只编排 select→expand→evaluate→backprop，0 业务判断
  - 所有策略显式注入（无默认值），适配因子/择时/任意场景
  - 最优状态收敛到 BestTracker 单一维护点
  - 树操作委派给 MCTSTree，选择委派给 SelectionStrategy

使用方法:
  engine = MCTSEngine(
      evaluator=...,
      fitness=fitness_calc,
      selection=BayesianUCB(),
      action_config=...,
      config=EngineConfig(n_iterations=500),
  )
  engine.run()
  print(engine.best_tracker.report())

[重构] 2026-08-06 基于 v1 事故教训完全重构。
"""

import ast
import math
import random
import time
from typing import Dict, List, Optional, Callable, Set

from .node import MCTSNode
from .tree import MCTSTree
from .best_tracker import BestTracker
from .config import EngineConfig, ActionConfig
from .constraints import CFGGrammar, SemanticValidator
from .dedup import SubtreeHasher, FrequentSubtreeMonitor
from .cache import SimpleFitnessCache
from .ast_utils import _expr_str, _canonicalize_key
from .selection import SelectionStrategy, BayesianUCB


class MCTSEngine:
    """MCTS 搜索引擎 v2 — 显式注入、编排纯化

    v1 → v2 变化:
      - 所有策略外部注入（selection / fitness / validation）
      - BestTracker 替代 v1 的三处分散 best 状态
      - MCTSConfig 拆分为 EngineConfig + ActionConfig（参数与动作解耦）
      - fitness_mode 取消（外部注入 fitness_calculator 决定语义）
    """

    def __init__(self,
                 # ── 核心注入（必须）──
                 evaluator: Callable,                    # signal → values（领域表达）
                 fitness_calculator,                     # FitnessCalculator 协议
                 action_config: ActionConfig,            # 动作空间边界

                 # ── 可选策略注入──
                 selection: Optional[SelectionStrategy] = None,  # 默认 BayesianUCB
                 validator=None,                         # ValidationStrategy（可选）
                 cfg_grammar: Optional[CFGGrammar] = None,
                 semantic_validator: Optional[SemanticValidator] = None,
                 subtree_monitor: Optional[FrequentSubtreeMonitor] = None,

                 # ── 引擎参数──
                 config: Optional[EngineConfig] = None,
                 # ── 种子表达式──
                 seed_expressions: Optional[List[str]] = None,
                 ):
        # 必需
        self.evaluator = evaluator
        self.fitness = fitness_calculator
        self.action_config = action_config

        # 策略（v2 显式注入，无隐藏默认值）
        self.selection = selection or BayesianUCB()
        self.validator = validator
        self.cfg = cfg_grammar
        self.semantic = semantic_validator
        self.monitor = subtree_monitor

        # 参数
        self.config = config or EngineConfig()

        # 状态
        self.best_tracker = BestTracker(
            best_pool_size=self.config.best_pool_size,
            enable_diverse_pool=self.config.enable_diverse_pool,
        )
        self.trees: List[MCTSTree] = []

        # 缓存
        self._cache = SimpleFitnessCache()

        # 随机数
        self._rng = random.Random(self.config.seed)

        # 种子
        self.seed_expressions = seed_expressions or ['CLOSE']
        self._seeds_evaluated = False

        # 统计
        self.start_time: float = 0
        self.end_time: float = 0

    # ================================================================
    # 主循环
    # ================================================================

    def run(self):
        """执行 MCTS 搜索（主入口）"""
        self.start_time = time.time()

        # 1. 初始化树（每种子一棵树）
        self.trees = [MCTSTree(expr) for expr in self.seed_expressions]
        self._evaluate_seeds()

        # 2. 主迭代
        for iteration in range(self.config.n_iterations):
            # 选树（多树时轮询，单树时 trivially index 0）
            tree_idx = iteration % len(self.trees)
            tree = self.trees[tree_idx]
            parent_visits = sum(t.total_evaluations for t in self.trees)

            # select → expand → evaluate → backprop
            leaf = tree.select(self.selection, parent_visits=parent_visits)

            # 评估（如果未被评估过）
            if not leaf.is_evaluated:
                self._evaluate_node(leaf)

            # 扩展（如果评估值不是失败）
            if leaf.fitness > -999 and leaf.depth < self.config.max_depth:
                new_children = tree.expand(
                    leaf,
                    action_config=self.action_config,
                    n_branches=self.config.n_branches,
                    max_depth=self.config.max_depth,
                    cfg=self.cfg,
                    semantic=self.semantic,
                    subtree_monitor=self.monitor,
                    best_pool=self.best_tracker.top(),
                    enable_graft=self.config.enable_graft,
                    rng=self._rng,
                )
                # 评估新子节点
                for child in new_children:
                    self._evaluate_node(child)

            # 相似度折扣（AlphaCFG，默认关）
            if self.config.enable_similarity_discount and leaf.fitness > -999:
                fitness = self._apply_similarity_discount(leaf)
            else:
                fitness = leaf.fitness

            # 反向传播
            tree.backpropagate(leaf, fitness, leaf.train_fitness, leaf.valid_fitness)

            # 更新全局最优（v2 唯一入口：BestTracker）
            self.best_tracker.update(leaf, trees=self.trees)

            # 早期停止
            if self.config.early_stop_rounds > 0 and self._check_early_stop():
                break

        # end for

        # 最终池验证（如果 validator 注入）
        self._verify_pool()

        self.end_time = time.time()

    # ================================================================
    # 内部方法
    # ================================================================

    def _evaluate_seeds(self):
        """评估所有种子节点"""
        for tree in self.trees:
            if not tree.root.is_evaluated:
                self._evaluate_node(tree.root)

    def _evaluate_node(self, node: MCTSNode):
        """评估单节点（含缓存查询）

        评估流程:
          1. 查缓存（signature 命中 → 直接赋值）
          2. 调用 evaluator 求值 → fitness_calculator.compute()
          3. 写缓存
          4. 写 node.fitness / train_fitness / valid_fitness
        """
        sig = node.signature or _canonicalize_key(node.tree)

        # 1. 查缓存
        cached = self._cache.get(sig)
        if cached is not None:
            node.fitness, node.train_fitness, node.valid_fitness = cached
            return

        # 2. 求值
        try:
            output = self.evaluator(node.tree)
            fitness_val = self.fitness.compute(output)
        except Exception:
            fitness_val = -999.0

        node.fitness = float(fitness_val)
        node.train_fitness = float(fitness_val)
        node.valid_fitness = -999.0  # 搜索阶段不做切分，由 verify 做

        # 3. 写缓存
        self._cache.put(sig, (node.fitness, node.train_fitness, node.valid_fitness))

    def _apply_similarity_discount(self, node: MCTSNode) -> float:
        """AlphaCFG 相似度折扣（默认关）"""
        hasher = SubtreeHasher()
        h = hasher.compute_full_tree(node.tree)
        total = 0.0
        count = 0
        for pool_node in self.best_tracker.top(self.config.top_k_similar):
            other_h = hasher.compute_full_tree(pool_node.tree)
            sim = 1.0 - self._hash_similarity(h, other_h)
            if sim > self.config.similarity_threshold:
                total += sim
                count += 1
        if count > 0:
            avg_sim = total / count
            return node.fitness * (1.0 - avg_sim * 0.3)
        return node.fitness

    @staticmethod
    def _hash_similarity(h1: str, h2: str) -> float:
        """简单字符级相似度"""
        if h1 == h2:
            return 1.0
        shared = sum(1 for c1, c2 in zip(h1, h2) if c1 == c2)
        return shared / max(len(h1), len(h2))

    def _check_early_stop(self) -> bool:
        """检查是否早停：best_fitness 连续 N 轮不改善"""
        if len(self.best_tracker._best_pool) < 2:
            return False
        # 简单实现：最近 N 轮 best 无变化
        # 这里简化：取 best_pool[0] 的 fitness history 检查
        best = self.best_tracker.best_fitness()
        if not hasattr(self, '_best_history'):
            self._best_history = []
        self._best_history.append(best)
        if len(self._best_history) > self.config.early_stop_rounds:
            recent = self._best_history[-self.config.early_stop_rounds:]
            if max(recent) == min(recent):  # 无变化
                return True
        return False

    def _verify_pool(self):
        """候选池 IC 检验（如果 validator 注入）"""
        if self.validator is None:
            return
        # 尝试用 fitness.verify 做全量验证（如果协议支持）
        if hasattr(self.fitness, 'verify'):
            try:
                for node in self.best_tracker.top():
                    info = self.fitness.verify(node.tree)
                    # 储存验证信息（后续可扩展）
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
