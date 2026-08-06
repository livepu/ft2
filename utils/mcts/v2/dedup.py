"""
core/dedup.py — AST 子树同构检测 + 频繁子树监控（v1 搬运）
=============================================================================

[搬运] 2026-08-06 从 utils/mcts/v1/dedup.py 搬运，逻辑不变。
"""

import ast as ast_module
import hashlib
import math
from typing import Dict, List, Set, Optional


class SubtreeHasher:
    """AST 子树哈希计算器（AlphaAgent 方案）"""

    def __init__(self):
        self._var_map: Dict[str, str] = {}
        self._var_counter: int = 0

    def compute(self, node: ast_module.AST) -> str:
        self._var_map.clear()
        self._var_counter = 0
        canonical = self._canonicalize(node)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]

    def compute_full_tree(self, tree: ast_module.AST) -> str:
        return self.compute(tree)

    def _canonicalize(self, node: ast_module.AST) -> str:
        if isinstance(node, ast_module.Name):
            return self._map_variable(node.id)
        elif isinstance(node, ast_module.Constant):
            val = node.value
            if isinstance(val, bool):
                return 'True' if val else 'False'
            if isinstance(val, (int, float)):
                if isinstance(val, float):
                    val = round(val, 4)
                return f'CONST_{val}'
            return f'CONST_{str(val)[:20]}'
        elif isinstance(node, ast_module.Call):
            func_name = self._get_func_name(node)
            args_str = ','.join(self._canonicalize(a) for a in node.args)
            return f'{func_name}({args_str})'
        elif isinstance(node, ast_module.BinOp):
            op_name = type(node.op).__name__
            left = self._canonicalize(node.left)
            right = self._canonicalize(node.right)
            if op_name in ('Add', 'Mult'):
                if left > right:
                    left, right = right, left
            return f'{op_name}({left},{right})'
        elif isinstance(node, ast_module.UnaryOp):
            op_name = type(node.op).__name__
            return f'{op_name}({self._canonicalize(node.operand)})'
        elif isinstance(node, ast_module.Compare):
            left = self._canonicalize(node.left)
            ops = ','.join(type(o).__name__ for o in node.ops)
            comps = ','.join(self._canonicalize(c) for c in node.comparators)
            return f'Compare({left},{ops},{comps})'
        elif isinstance(node, ast_module.BoolOp):
            op_name = type(node.op).__name__
            vals = sorted(self._canonicalize(v) for v in node.values)
            return f'{op_name}({",".join(vals)})'
        elif isinstance(node, ast_module.IfExp):
            test = self._canonicalize(node.test)
            body = self._canonicalize(node.body)
            orelse = self._canonicalize(node.orelse)
            return f'IfExp({test},{body},{orelse})'
        elif isinstance(node, ast_module.Expression):
            return self._canonicalize(node.body)
        else:
            return type(node).__name__

    def _map_variable(self, var_name: str) -> str:
        if var_name not in self._var_map:
            self._var_map[var_name] = f'V{self._var_counter}'
            self._var_counter += 1
        return self._var_map[var_name]

    @staticmethod
    def _get_func_name(call_node: ast_module.Call) -> str:
        if isinstance(call_node.func, ast_module.Name):
            return call_node.func.id
        if isinstance(call_node.func, ast_module.Attribute):
            return call_node.func.attr
        return 'unknown'

    def extract_all_subtrees(self, tree: ast_module.AST,
                             min_depth: int = 2, max_depth: int = 4) -> List[str]:
        hashes: List[str] = []
        for node in ast_module.walk(tree):
            if isinstance(node, (ast_module.Expression, ast_module.Name, ast_module.Constant)):
                continue
            d = self._node_depth(node, tree)
            if min_depth <= d <= max_depth:
                h = self.compute(node)
                hashes.append(h)
        return hashes

    @staticmethod
    def _node_depth(node: ast_module.AST, tree: ast_module.AST) -> int:
        depth = 0
        for n in ast_module.walk(tree):
            for child in ast_module.iter_child_nodes(n):
                if child is node:
                    return depth + 1
            depth += 1
        return 0


class FrequentSubtreeMonitor:
    """频繁子树监控器（AlphaJungle 方案）"""

    def __init__(self, threshold: int = 5):
        self.threshold = threshold
        self._freq_table: Dict[str, int] = {}
        self._hasher = SubtreeHasher()

    def register(self, tree: ast_module.AST):
        hashes = self._hasher.extract_all_subtrees(tree)
        for h in set(hashes):
            self._freq_table[h] = self._freq_table.get(h, 0) + 1

    def is_frequent(self, subtree_hash: str) -> bool:
        return self._freq_table.get(subtree_hash, 0) >= self.threshold

    def count(self, subtree_hash: str) -> int:
        return self._freq_table.get(subtree_hash, 0)

    def get_avoidance_weight(self, subtree_hash: str,
                             base_weight: float = 1.0) -> float:
        count = self._freq_table.get(subtree_hash, 0)
        if count < self.threshold:
            return base_weight
        return base_weight / (1 + math.log(1 + count - self.threshold))

    def top_frequent(self, n: int = 10) -> list:
        return sorted(self._freq_table.items(),
                      key=lambda x: x[1], reverse=True)[:n]

    def reset(self):
        self._freq_table.clear()
