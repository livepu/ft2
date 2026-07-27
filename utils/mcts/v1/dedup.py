"""
AST 子树同构检测 + 频繁子树监控（AlphaAgent + AlphaJungle 方案）

核心思路:
  1. SubtreeHasher: 规范化变量名后计算子树哈希，检测结构同构
  2. FrequentSubtreeMonitor: 跟踪子树模式频率，回避拥挤方向
"""

import ast as ast_module
import hashlib
import math
from typing import Dict, List, Set, Optional


class SubtreeHasher:
    """AST 子树哈希计算器（AlphaAgent 方案）

    关键: 先规范化变量名，再计算哈希。
    同一结构不同变量名 → 同一哈希（结构同构检测）。
    不同结构相同变量 → 不同哈希（即使变量相同）。

    规范化规则:
      - Name(id='CLOSE')   → 'VAR_0'
      - Name(id='HIGH')    → 'VAR_1'
      - Name(id='VOLUME')  → 'VAR_2'
      - Constant(value=1)  → 'CONST_1'
      - Constant(value=0.5)→ 'CONST_0.5'
      - Call(func='ts_roc') → 'ts_roc'
    """

    def __init__(self):
        self._var_map: Dict[str, str] = {}
        self._var_counter: int = 0

    def compute(self, node: ast_module.AST) -> str:
        """计算规范化 AST 子树的哈希值"""
        self._var_map.clear()
        self._var_counter = 0
        canonical = self._canonicalize(node)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]

    def compute_full_tree(self, tree: ast_module.AST) -> str:
        """计算整棵树的哈希"""
        return self.compute(tree)

    def _canonicalize(self, node: ast_module.AST) -> str:
        """递归规范化节点为规范字符串"""
        if isinstance(node, ast_module.Name):
            return self._map_variable(node.id)

        elif isinstance(node, ast_module.Constant):
            val = node.value
            if isinstance(val, bool):
                return 'True' if val else 'False'
            if isinstance(val, (int, float)):
                # 合并近似常数
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
            # 交换律规范化: Add/Mult 参数排序
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

        # Expression 包装
        elif isinstance(node, ast_module.Expression):
            return self._canonicalize(node.body)

        else:
            return type(node).__name__

    def _map_variable(self, var_name: str) -> str:
        """变量名 → 规范化标识符"""
        if var_name not in self._var_map:
            self._var_map[var_name] = f'V{self._var_counter}'
            self._var_counter += 1
        return self._var_map[var_name]

    @staticmethod
    def _get_func_name(call_node: ast_module.Call) -> str:
        """从 Call 节点提取函数名"""
        if isinstance(call_node.func, ast_module.Name):
            return call_node.func.id
        if isinstance(call_node.func, ast_module.Attribute):
            return call_node.func.attr
        return 'unknown'

    def extract_all_subtrees(self, tree: ast_module.AST,
                             min_depth: int = 2, max_depth: int = 4) -> List[str]:
        """提取树中所有子树的规范化哈希（深度在 [min_depth, max_depth]）

        Args:
          tree: AST 树
          min_depth: 最小子树深度（拍除过浅的叶子节点）
          max_depth: 最大子树深度
        """
        hashes: List[str] = []
        for node in ast_module.walk(tree):
            # 跳过顶层 Expression 和太简单的节点
            if isinstance(node, (ast_module.Expression, ast_module.Name, ast_module.Constant)):
                continue
            d = self._node_depth(node, tree)
            if min_depth <= d <= max_depth:
                h = self.compute(node)
                hashes.append(h)
        return hashes

    @staticmethod
    def _node_depth(node: ast_module.AST, tree: ast_module.AST) -> int:
        """计算节点在树中的相对深度"""
        depth = 0
        for n in ast_module.walk(tree):
            for child in ast_module.iter_child_nodes(n):
                if child is node:
                    return depth + 1
            depth += 1
        return 0


class FrequentSubtreeMonitor:
    """频繁子树监控器（AlphaJungle 方案）

    维护全局子树频率表。
    当某子树模式出现次数超过阈值，变异算子降低该模式的选择权重。

    用法:
      monitor = FrequentSubtreeMonitor(threshold=5)
      for node in new_nodes:
          monitor.register(node)          # 注册新节点
      if monitor.is_frequent(hash):       # 检测是否频繁
          weight = monitor.get_avoidance_weight(hash)  # 获取衰减权重
    """

    def __init__(self, threshold: int = 5):
        self.threshold = threshold
        self._freq_table: Dict[str, int] = {}     # 子树哈希 → 频率
        self._hasher = SubtreeHasher()

    def register(self, tree: ast_module.AST):
        """注册一棵新树的所有子树到频率表"""
        hashes = self._hasher.extract_all_subtrees(tree)
        for h in set(hashes):  # 同一树内相同子树只计一次
            self._freq_table[h] = self._freq_table.get(h, 0) + 1

    def is_frequent(self, subtree_hash: str) -> bool:
        """检查某子树模式是否频繁"""
        return self._freq_table.get(subtree_hash, 0) >= self.threshold

    def count(self, subtree_hash: str) -> int:
        """获取子树模式的出现次数"""
        return self._freq_table.get(subtree_hash, 0)

    def get_avoidance_weight(self, subtree_hash: str,
                             base_weight: float = 1.0) -> float:
        """计算频繁子树的衰减权重

        频次越高，权重越低。（对数衰减，避免踩死）
        """
        count = self._freq_table.get(subtree_hash, 0)
        if count < self.threshold:
            return base_weight
        # 超过阈值后用对数衰减: w = base / (1 + log(1 + count - threshold))
        return base_weight / (1 + math.log(1 + count - self.threshold))

    def top_frequent(self, n: int = 10) -> List[tuple]:
        """返回 Top-N 最频繁的子树模式 (hash, count)"""
        return sorted(self._freq_table.items(),
                      key=lambda x: x[1], reverse=True)[:n]

    def reset(self):
        """重置频率表"""
        self._freq_table.clear()
