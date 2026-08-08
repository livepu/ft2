"""
core/best_tracker.py — 最优状态单一维护点（v2 新增）
=============================================================================

v1 教训: global_best / best_pool / tree.best_node 三处分散维护，导致死代码。
v2 根治: 所有最优状态收敛到 BestTracker 单文件，引擎只调 update()。

职责:
  - 全局最优 (global_best)
  - 最优池 (best_pool, top-N 去重)
  - 树最优同步 (各树 best_node ← global_best)
  - 评估统计 (evaluated_style/return_distribution 预留)

[新增] 2026-08-06 v1 global_best 死代码的架构根治。
"""

from typing import List, Optional, Set
from .node import MCTSNode


class BestTracker:
    """最优状态单一维护点

    引擎 lifecycle:
      每次评估后: tracker.update(node, trees)
      查询最优: tracker.global_best / tracker.top()
      最终报告: tracker.report()
    """

    def __init__(self, best_pool_size: int = 10,
                 enable_diverse_pool: bool = True,
                 signature_fn: Optional[callable] = None):
        """BestTracker 最优状态单一维护点

        Args:
          best_pool_size: 最优池容量（v1 默认 20）
          enable_diverse_pool: 结构去重（v1 默认 True）
          signature_fn: 去重签名计算函数 node → str。
                        [修复] 2026-08-07 对齐 v1 用 _structural_signature（跳过
                        cs_rank/cs_zscore 等等价外层包装），v1 默认用此签名去重。
                        None 时用 node.signature（完整 canonicalize）。
        """
        self._global_best: Optional[MCTSNode] = None
        self._best_pool: List[MCTSNode] = []
        self._pool_size = best_pool_size
        self._enable_diverse = enable_diverse_pool
        self._signature_fn = signature_fn
        self._signature_tracker: Set[str] = set()
        self.total_evaluated: int = 0

    # ── 核心更新（唯一入口！）──

    def _sig(self, node: MCTSNode) -> str:
        if self._signature_fn is not None:
            return self._signature_fn(node)
        return node.signature or ""

    def update(self, node: MCTSNode, trees: Optional[List] = None):
        """评估完一个节点后调用此方法

        职责:
          1. 更新 best_pool（含可选结构多样性去重）
          2. 更新 global_best
          3. 同步各树 best_node

        Args:
          node: 刚评估完的节点
          trees: MCTSTree 列表（用于同步 tree.best_node）
        """
        self.total_evaluated += 1

        if not node.is_evaluated or node.fitness <= -999:
            return

        sig = self._sig(node)

        # 1. 更新最优池
        if self._enable_diverse and sig:
            if sig in self._signature_tracker:
                # 同签名已存在，替换更高 fitness
                for i, existing in enumerate(self._best_pool):
                    if self._sig(existing) == sig:
                        if node.fitness > existing.fitness:
                            self._best_pool[i] = node
                        break
            else:
                self._best_pool.append(node)
                self._signature_tracker.add(sig)
        else:
            self._best_pool.append(node)

        # 排序 + 截断
        self._best_pool.sort(key=lambda n: n.fitness, reverse=True)
        if len(self._best_pool) > self._pool_size:
            removed = self._best_pool[self._pool_size:]
            self._best_pool = self._best_pool[:self._pool_size]
            if self._enable_diverse:
                for r in removed:
                    if self._sig(r):
                        self._signature_tracker.discard(self._sig(r))

        # 2. 更新全局最优
        if self._global_best is None or node.fitness > self._global_best.fitness:
            self._global_best = node
            # 3. 同步各树 best_node
            if trees:
                for tree in trees:
                    tree.best_node = node

    # ── 查询 ──

    @property
    def global_best(self) -> Optional[MCTSNode]:
        return self._global_best

    def top(self, n: int = None) -> List[MCTSNode]:
        if n is None:
            return list(self._best_pool)
        return self._best_pool[:n]

    def best_expr(self) -> str:
        if self._global_best:
            return self._global_best.expression
        return ""

    # ── 统计 ──

    def best_fitness(self) -> float:
        return self._global_best.fitness if self._global_best else -999.0

    def pool_fitnesses(self) -> List[float]:
        return [n.fitness for n in self._best_pool]

    def report(self) -> dict:
        return {
            'total_evaluated': self.total_evaluated,
            'best_fitness': self.best_fitness(),
            'best_expression': self.best_expr(),
            'pool_size': len(self._best_pool),
            'pool_top5': [n.fitness for n in self._best_pool[:5]],
        }
