"""
core/constraints.py — CFG 语法约束 + 语义验证（v1 搬运）
=============================================================================

[搬运] 2026-08-06 从 utils/mcts/v1/constraints.py 搬运，逻辑不变。
"""

import ast as ast_module
from typing import Tuple, Optional, Set


_REDUNDANT_NESTING: Set[str] = {
    'cs_rank', 'abs', 'sign', 'log',
}

_IDENTITY_PATTERNS = {
    ('Add', 0), ('Add', 0.0), ('Sub', 0), ('Sub', 0.0),
    ('Mult', 1), ('Mult', 1.0), ('Div', 1), ('Div', 1.0),
}

_CS_FUNCTIONS: Set[str] = {
    'cs_rank', 'cs_scale', 'cs_zscore', 'cs_winsorize',
    'cs_quantile', 'cs_normalize',
}


class SemanticValidator:
    """语义层约束检查器"""

    def __init__(self, max_depth: int = 6, min_variables: int = 1):
        self.max_depth = max_depth
        self.min_variables = min_variables

    def check(self, tree: ast_module.AST) -> Tuple[bool, str]:
        depth = self._compute_depth(tree)
        if depth > self.max_depth:
            return False, f"AST 深度 {depth} > {self.max_depth}"
        var_count = self._count_variables(tree)
        if var_count < self.min_variables:
            return False, f"数据变量数 {var_count} < {self.min_variables}"
        id_ok, id_reason = self._check_identity(tree)
        if not id_ok:
            return False, id_reason
        nest_ok, nest_reason = self._check_redundant_nesting(tree)
        if not nest_ok:
            return False, nest_reason
        return True, ""

    def _compute_depth(self, node: ast_module.AST, current_depth: int = 0) -> int:
        max_d = current_depth
        for child in ast_module.iter_child_nodes(node):
            child_d = self._compute_depth(child, current_depth + 1)
            max_d = max(max_d, child_d)
        return max_d

    def _count_variables(self, node: ast_module.AST) -> int:
        variables: Set[str] = set()
        class VarCollector(ast_module.NodeVisitor):
            def visit_Name(self, n):
                if n.id not in ('True', 'False', 'None', 'math'):
                    variables.add(n.id)
        VarCollector().visit(node)
        return len(variables)

    def _check_identity(self, tree: ast_module.AST) -> Tuple[bool, str]:
        for node in ast_module.walk(tree):
            if isinstance(node, ast_module.BinOp):
                left_str = ast_module.dump(node.left, annotate_fields=False)
                right_str = ast_module.dump(node.right, annotate_fields=False)
                if left_str == right_str:
                    if isinstance(node.op, ast_module.Sub):
                        return False, "冗余: x - x (恒为 0)"
                    if isinstance(node.op, ast_module.Div):
                        return False, "冗余: x / x (恒为 1)"
            if isinstance(node, ast_module.BinOp):
                if isinstance(node.op, (ast_module.Add, ast_module.Sub)):
                    if self._is_constant(node.left, 0):
                        return False, "冗余: 0 ± x"
                    if isinstance(node.op, ast_module.Add) and self._is_constant(node.right, 0):
                        return False, "冗余: x + 0"
                    if isinstance(node.op, ast_module.Sub) and self._is_constant(node.right, 0):
                        return False, "冗余: x - 0"
                if isinstance(node.op, ast_module.Mult):
                    if self._is_constant(node.left, 1) or self._is_constant(node.right, 1):
                        return False, "冗余: x * 1"
                if isinstance(node.op, ast_module.Div):
                    if self._is_constant(node.right, 1):
                        return False, "冗余: x / 1"
        return True, ""

    def _check_redundant_nesting(self, tree: ast_module.AST) -> Tuple[bool, str]:
        for node in ast_module.walk(tree):
            if isinstance(node, ast_module.Call):
                func_name = self._get_func_name(node)
                if func_name is None:
                    continue
                if func_name in _REDUNDANT_NESTING:
                    for arg in node.args:
                        if isinstance(arg, ast_module.Call):
                            inner_name = self._get_func_name(arg)
                            if inner_name == func_name:
                                return False, f"冗余嵌套: {func_name}({func_name}(...))"
        return True, ""

    def _get_func_name(self, call_node: ast_module.Call) -> Optional[str]:
        if isinstance(call_node.func, ast_module.Name):
            return call_node.func.id
        if isinstance(call_node.func, ast_module.Attribute):
            return call_node.func.attr
        return None

    @staticmethod
    def _is_constant(node: ast_module.AST, value) -> bool:
        if isinstance(node, ast_module.Constant):
            return node.value == value
        if isinstance(node, ast_module.UnaryOp) and isinstance(node.op, ast_module.USub):
            if isinstance(node.operand, ast_module.Constant):
                return -node.operand.value == value
        return False


class CFGGrammar:
    """上下文无关文法约束"""

    def __init__(self, allowed_functions: Optional[Set[str]] = None):
        self.allowed_functions = allowed_functions

    def is_syntactically_valid(self, tree: ast_module.AST) -> Tuple[bool, str]:
        try:
            for node in ast_module.walk(tree):
                if isinstance(node, ast_module.Call):
                    func_name = None
                    if isinstance(node.func, ast_module.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast_module.Attribute):
                        func_name = node.func.attr
                    if func_name and self.allowed_functions:
                        if func_name not in self.allowed_functions:
                            return False, f"函数 '{func_name}' 不在允许列表中"
            return True, ""
        except Exception as e:
            return False, f"AST 遍历异常: {e}"

    def with_allowed_functions(self, func_set: Set[str]) -> 'CFGGrammar':
        return CFGGrammar(allowed_functions=func_set)
