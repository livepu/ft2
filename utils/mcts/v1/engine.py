"""
MCTSEngine — MCTS 树搜索主循环

流程（每轮迭代）:
  1. Selection   : tree.select() → 选择最优叶节点
  2. Expansion   : tree.expand() → 生成子节点
  3. Evaluation  : 逐个评估子节点 fitness
  4. Backprop    : tree.backpropagate() → 反向传播更新统计

定位:
  - 不是 GP（无种群/交叉/选择），是树搜索
  - 适合深挖掘（对已有种子深度优化），不适合从零宽探索
  - LLM-free: 核心循环不依赖 LLM，动作由本地规则算子完成
  - 零外部依赖: 完全独立于 gp/v5/v6 和 factor/v5，自包含
  - 评估逻辑通过外部注入 (evaluator + fitness_calculator)

依赖:
  - 本地 actions.py（7 种 AST 搜索动作）
  - 外部 evaluator + fitness_calculator（调用方注入）
"""

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set

from .node import MCTSNode
from .tree import MCTSTree
from .constraints import CFGGrammar, SemanticValidator
from .dedup import FrequentSubtreeMonitor

# 本地模块
from .config import ActionConfig
from .cache import SimpleFitnessCache


@dataclass
class MCTSConfig:
    """MCTS 引擎配置

    所有参数有合理默认值，按需覆盖。
    """

    # ── 搜索 ──
    n_iterations: int = 1000                # 总搜索迭代次数
    selection_mode: str = 'bayesian_ucb'    # 选择模式: standard_ucb | bayesian_ucb | puct
    ucb_constant: float = 1.414             # UCB 探索常数
    gamma: float = 0.05                     # 贝叶斯深度惩罚系数
    beta: float = 0.01                      # 贝叶斯出度惩罚系数
    n_branches: int = 3                     # 每次扩路生成子节点数
    max_depth: int = 10                     # 树最大深度

    # ── 约束 ──
    enable_cfg: bool = True                 # 启用 CFG 语法约束
    enable_semantic: bool = True            # 启用语义检查（冗余过滤）
    enable_subtree_avoid: bool = True       # 启用频繁子树回避
    freq_subtree_threshold: int = 5         # 频繁子树阈值
    enable_graft: bool = False              # 启用嫁接变异
    enable_similarity_discount: bool = False  # AlphaCFG: 谨慎开启，伤浅层结构
    enable_diverse_pool: bool = True           # 最优池结构去重（每签名只保留最优）
    best_pool_size: int = 20                   # 最优池容量

    # ── 评估 ──
    fitness_mode: str = 'ic'                # ic | sharpe | gt_score
    use_cache: bool = True                  # 使用本地缓存

    # ── 早停 ──
    early_stop_rounds: int = 50             # 全局最优连续 N 轮无提升 → 早停
    early_stop_path_rounds: int = 20        # 当前路径连续 M 步下降 → 放弃该路径

    # ── 并行 ──
    parallel_trees: int = 1                 # 并行树数量

    # ── 日志 ──
    verbose: bool = True                    # 打印进度
    log_every: int = 50                     # 每 N 轮打印

    # ── 随机 ──
    random_seed: Optional[int] = None       # 随机种子


class MCTSEngine:
    """MCTS 树搜索引擎

    领域无关的纯搜索算法。评估通过外部注入的 evaluator +
    fitness_calculator 完成，可直接适配因子/择时等不同场景。

    用法:
      engine = MCTSEngine(
          evaluator=my_evaluator,
          fitness_calculator=my_fitness,
          data=data_dict,
          seed_expressions=['cs_rank(ts_roc(CLOSE,20))'],
          config=MCTSConfig(n_iterations=500),
      )
      engine.run()
      print(engine.report())
    """

    def __init__(self,
                 evaluator: Callable[[Any, Any], Any],
                 fitness_calculator: Any,
                 data: Dict[str, Any],
                 seed_expressions: List[str],
                 action_config: Optional[ActionConfig] = None,
                 config: Optional[MCTSConfig] = None,
                 source: str = 'mcts_v1'):
        """
        Args:
          evaluator: (data, tree) → factor_values 的函数
          fitness_calculator: 计算 fitness 的对象，需有 .compute() 方法
          data: 市场数据（OHLCV 等）
          seed_expressions: 种子表达式列表
          action_config: ActionConfig（控制动作空间，默认使用内置配置）
          config: MCTS 引擎配置
          source: 来源标识
        """
        self.evaluator = evaluator
        self.fitness_calculator = fitness_calculator
        self.data = data
        self.seed_expressions = seed_expressions
        self.config = config or MCTSConfig()
        self.rng = random.Random(self.config.random_seed)

        # ActionConfig
        if action_config is None:
            self.action_config = ActionConfig()
            self.action_config.rng = random.Random(self.config.random_seed)
        else:
            self.action_config = action_config

        # 约束组件
        self.cfg_grammar = CFGGrammar(
            allowed_functions=self.action_config.allowed_functions
        ) if self.config.enable_cfg else None

        self.semantic_validator = SemanticValidator(
            max_depth=self.config.max_depth
        ) if self.config.enable_semantic else None

        self.subtree_monitor = FrequentSubtreeMonitor(
            threshold=self.config.freq_subtree_threshold
        ) if self.config.enable_subtree_avoid else None

        # 缓存
        self.cache = SimpleFitnessCache() if self.config.use_cache else None

        # 多树（每个种子一棵树 + 共享最优池）
        self.trees: List[MCTSTree] = []
        self.best_pool: List[MCTSNode] = []   # 跨树共享最优池
        self.global_best: Optional[MCTSNode] = None

        # 统计
        self.iteration: int = 0
        self.stats: Dict[str, List[float]] = {
            'best_fitness': [],
            'avg_fitness': [],
            'evaluations': [],
        }
        self.start_time: float = 0

    # ─────────────────────────────────────────────
    # 主循环
    # ─────────────────────────────────────────────

    def run(self) -> 'MCTSEngine':
        """运行 MCTS 搜索主循环"""
        self.start_time = time.time()

        # 初始化: 每个种子一棵树
        self._init_trees()

        if self.config.verbose:
            print(f"[MCTS] 初始化 {len(self.trees)} 棵树，"
                  f"共 {self.config.n_iterations} 轮迭代")
            print(f"[MCTS] 选择模式: {self.config.selection_mode}, "
                  f"fitness: {self.config.fitness_mode}")

        # 评估种子节点（预热最优池）
        self._evaluate_seeds()

        # 主循环
        for i in range(self.config.n_iterations):
            self.iteration = i

            # 出度感知树选择（AlphaPROBE: 被探索多的树退避，让其他树有机会发展）
            outdegrees = [t.root.outdegree for t in self.trees]
            max_od = max(outdegrees) if outdegrees else 1
            weights = [max_od - od + 1 for od in outdegrees]  # 低出度→高权重
            tree = self.rng.choices(self.trees, weights=weights, k=1)[0]

            # Step 1: Selection
            leaf = tree.select(
                mode=self.config.selection_mode,
                ucb_c=self.config.ucb_constant,
                gamma=self.config.gamma,
                beta=self.config.beta,
            )

            # Step 2: Expansion
            children = tree.expand(
                leaf,
                action_config=self.action_config,
                n_branches=self.config.n_branches,
                max_depth=self.config.max_depth,
                cfg=self.cfg_grammar,
                semantic=self.semantic_validator,
                subtree_monitor=self.subtree_monitor,
                best_pool=self.best_pool,
                enable_graft=self.config.enable_graft,
                rng=self.rng,
            )

            # Step 3: Evaluation
            for child in children:
                fitness = self._evaluate_single(child)

                # Step 4: Backprop
                tree.backpropagate(child, fitness)

                # 更新全局最优池
                self._update_best_pool(child)

                # 注册子树频率
                if self.subtree_monitor is not None:
                    self.subtree_monitor.register(child.tree)

            # 统计
            self._record_stats()

            # 日志
            if self.config.verbose and (i + 1) % self.config.log_every == 0:
                self._log_progress(i + 1)

            # 早停检查
            if self._should_early_stop():
                if self.config.verbose:
                    print(f"[MCTS] 早停触发 (iter={i + 1})")
                break

        self._finalize()
        return self

    # ─────────────────────────────────────────────
    # 初始化
    # ─────────────────────────────────────────────

    def _init_trees(self):
        """为每个种子创建一棵 MCTS 树"""
        for expr in self.seed_expressions:
            try:
                tree = MCTSTree(root_expression=expr)
                self.trees.append(tree)
            except Exception as e:
                if self.config.verbose:
                    print(f"[MCTS] 警告: 跳过无效种子 '{expr[:50]}...' : {e}")

        if not self.trees:
            raise ValueError("没有有效的种子表达式")

    def _evaluate_seeds(self):
        """评估所有种子节点，建立初始最优池"""
        for tree in self.trees:
            root = tree.root
            if not root.is_evaluated:
                fitness = self._evaluate_single(root)
                tree.backpropagate(root, fitness)
                self._update_best_pool(root)
                if self.subtree_monitor is not None:
                    self.subtree_monitor.register(root.tree)

    # ─────────────────────────────────────────────
    # 评估
    # ─────────────────────────────────────────────

    def _evaluate_single(self, node: MCTSNode) -> float:
        """评估单个节点

        流程:
          1. 查缓存（如有）
          2. evaluator(data, tree) → 计算输出
          3. fitness_calculator.compute(output) → fitness
          4. 可选 GT-Score
          5. 写缓存
        """
        # 缓存命中
        if self.cache is not None and node.signature:
            cached = self.cache.get(node.signature)
            if cached is not None:
                node.fitness = cached[0]
                return cached[0]

        try:
            # 执行表达式求值
            output = self.evaluator(self.data, node.tree)

            # 计算 fitness
            fitness = self.fitness_calculator.compute(output)

            # AlphaCFG: 结构相似度折扣（池≥10且深度≥3后才生效）
            if (self.config.enable_similarity_discount
                and len(self.best_pool) >= 10
                and node.depth >= 3):
                discount = self._compute_similarity_discount(node)
                fitness = fitness * discount

            # 写缓存
            if self.cache is not None and node.signature:
                depth = node.depth
                node_count = getattr(node.tree, 'body', node.tree)
                try:
                    n = sum(1 for _ in __import__('ast').walk(node.tree))
                except Exception:
                    n = 0
                self.cache.put(node.signature, (fitness, depth, n))

            return fitness

        except Exception as e:
            # 评估失败 → 返回极低 fitness
            return -999.0

    def _compute_similarity_discount(self, node: MCTSNode,
                                      alpha: float = 0.5) -> float:
        """AlphaCFG 结构相似度折扣

        仅在最优池有足够多样性后生效（≥3个不同结构），
        防止探索初期就被扣分压制。

        Returns:
          折扣系数 ∈ [0.3, 1.0]。
        """
        if len(self.best_pool) < 3:
            return 1.0  # 最优池太小，不扣

        from .dedup import SubtreeHasher
        hasher = SubtreeHasher()
        node_hashes = set(hasher.extract_all_subtrees(node.tree))
        if not node_hashes:
            return 1.0

        max_sim = 0.0
        for best_node in self.best_pool[:5]:  # Top-5 冠军
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

        # 相似度 < 80% → 不扣；相似度 ≥ 80% → 轻度扣分
        if max_sim < 0.8:
            return 1.0
        discount = 1.0 - alpha * max_sim
        return max(discount, 0.5)

    def _update_best_pool(self, node: MCTSNode):
        """更新全局最优池（保留 top-N，可选结构多样性过滤）"""
        if not node.is_evaluated or node.fitness <= -999:
            return

        if self.config.enable_diverse_pool:
            # 结构签名去重：同签名只保留最高 fitness
            sig = self._structural_signature(node)
            for existing in self.best_pool:
                if self._structural_signature(existing) == sig:
                    if node.fitness > existing.fitness:
                        self.best_pool.remove(existing)
                        self.best_pool.append(node)
                    return  # 已有同签名且 fitness 更高 → 不加入

        self.best_pool.append(node)
        # 按 fitness 降序排序并保留 top-N
        self.best_pool.sort(key=lambda n: n.fitness, reverse=True)
        if len(self.best_pool) > self.config.best_pool_size:
            self.best_pool = self.best_pool[:self.config.best_pool_size]

    def _structural_signature(self, node: MCTSNode) -> str:
        """提取结构签名：内层调用链（跳过外层等价包装）

        例如:
          cs_rank(ts_rank(ts_delta(ts_rank(cs_zscore(CLOSE),60),20),10))
          签名 = ts_delta(ts_rank(cs_zscore),20)  ← 核心变换链

        cs_rank/abs/sign/cs_zscore/cs_scale 等单调变换不改变排序，
        视为"等价包装"跳过。
        """
        import ast as _ast

        from .dedup import SubtreeHasher
        hasher = SubtreeHasher()

        _cosmetic_wraps = {'cs_rank', 'cs_zscore', 'cs_scale', 'abs', 'log', 'sign'}

        tree = node.tree.body
        while isinstance(tree, _ast.Call):
            func_name = tree.func.id if isinstance(tree.func, _ast.Name) else ''
            if func_name not in _cosmetic_wraps:
                break
            tree = tree.args[0]

        return hasher.compute_full_tree(tree)

        # 更新全局最优
        if self.global_best is None or node.fitness > self.global_best.fitness:
            self.global_best = node
            for tree in self.trees:
                tree.best_node = node

    def _record_stats(self):
        """记录当前轮统计"""
        all_fitness = [n.fitness for tree in self.trees
                       for n in tree.all_nodes.values()
                       if n.is_evaluated]

        self.stats['best_fitness'].append(
            max(all_fitness) if all_fitness else -999.0)
        self.stats['avg_fitness'].append(
            sum(all_fitness) / len(all_fitness) if all_fitness else -999.0)
        self.stats['evaluations'].append(
            sum(tree.total_evaluations for tree in self.trees))

    # ─────────────────────────────────────────────
    # 早停
    # ─────────────────────────────────────────────

    def _should_early_stop(self) -> bool:
        """检查早停条件

        双条件:
          1. 全局最优连续 N 轮无提升
          2. 当前搜索路径连续 M 步下降（暂未实现，P2）
        """
        if self.config.early_stop_rounds <= 0:
            return False

        best_series = self.stats['best_fitness']
        # 需要至少 2*N 轮历史才能比较"历史最优"和"近期最优"
        if len(best_series) < self.config.early_stop_rounds * 2:
            return False

        recent_best = best_series[-self.config.early_stop_rounds:]
        historical_best = max(best_series[:-self.config.early_stop_rounds])
        if max(recent_best) <= historical_best:
            return True

        return False

    # ─────────────────────────────────────────────
    # 日志
    # ─────────────────────────────────────────────

    def _log_progress(self, iteration: int):
        """打印进度日志"""
        elapsed = time.time() - self.start_time
        best_f = self.stats['best_fitness'][-1] if self.stats['best_fitness'] else -999

        total_nodes = sum(t.node_count() for t in self.trees)
        total_evals = sum(t.total_evaluations for t in self.trees)

        best_expr = ''
        if self.global_best:
            best_expr = self.global_best.expression[:50]

        print(f"[MCTS] iter={iteration:4d}/{self.config.n_iterations} "
              f"| best={best_f:.4f} | evals={total_evals} "
              f"| nodes={total_nodes} | elapsed={elapsed:.1f}s")
        if best_expr:
            print(f"       best_expr: {best_expr}")

    def _finalize(self):
        """搜索结束后的收尾工作"""
        if self.config.verbose:
            elapsed = time.time() - self.start_time
            print(f"\n[MCTS] 搜索完成 ({elapsed:.1f}s)")
            print(f"  总迭代:   {self.iteration + 1}")
            print(f"  总评估:   {sum(t.total_evaluations for t in self.trees)}")
            print(f"  总节点:   {sum(t.node_count() for t in self.trees)}")
            print(f"  最优池:   {len(self.best_pool)} 个")

    # ─────────────────────────────────────────────
    # 结果查询
    # ─────────────────────────────────────────────

    def best(self) -> Optional[MCTSNode]:
        """返回全局最优节点"""
        return self.global_best

    def top(self, n: int = 10) -> List[MCTSNode]:
        """返回 Top-N 节点（从最优池）"""
        return self.best_pool[:n]

    def report(self) -> str:
        """生成搜索报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("MCTS 树搜索报告")
        lines.append("=" * 60)

        # 配置
        lines.append(f"\n## 配置")
        lines.append(f"  种子数:     {len(self.seed_expressions)}")
        lines.append(f"  迭代数:     {self.iteration + 1}")
        lines.append(f"  选择模式:   {self.config.selection_mode}")
        lines.append(f"  每轮分支:   {self.config.n_branches}")
        lines.append(f"  最大深度:   {self.config.max_depth}")

        # 统计
        lines.append(f"\n## 统计")
        lines.append(f"  总评估:     {sum(t.total_evaluations for t in self.trees)}")
        lines.append(f"  总节点:     {sum(t.node_count() for t in self.trees)}")
        lines.append(f"  最优池:     {len(self.best_pool)}")

        if self.stats['best_fitness']:
            lines.append(f"  最终最优:   {self.stats['best_fitness'][-1]:.4f}")
            lines.append(f"  历史最优:   {max(self.stats['best_fitness']):.4f}")

        # Top-10
        lines.append(f"\n## Top-10 表达式")
        for i, node in enumerate(self.top(10)):
            fit = node.fitness if node.is_evaluated else -999
            lines.append(f"  {i + 1:2d}. [{fit:.4f}] {node.expression[:80]}")

        # 最优路径
        if self.global_best:
            lines.append(f"\n## 最优路径 (根→最优)")
            for i, node in enumerate(self.global_best.path_to_root()):
                indent = "  " * (len(self.global_best.path_to_root()) - i - 1)
                lines.append(f"  {indent}{node.edge or 'ROOT'}: {node.expression[:60]}")

        return "\n".join(lines)
