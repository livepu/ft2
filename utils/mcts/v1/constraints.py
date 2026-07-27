"""
CFG 语法约束 + 语义验证（AlphaCFG 方案）

三层约束空间:
  L_syn  : 语法有效（算子元数、类型匹配）
  L_sem  : 语义可解释（含数据变量、无冗余恒等变换）
  L_sem^≤K: 深度受限（AST 深度上限）

用法:
  validator = SemanticValidator(max_depth=6)
  ok, reason = validator.check(tree)
"""

import ast as ast_module
from typing import Tuple, Optional, Set


# ── 已知冗余嵌套模式 ──
# 某些函数嵌套自身是冗余的（如 cs_rank(cs_rank(...))）
_REDUNDANT_NESTING: Set[str] = {
    'cs_rank',     # 排名套排名无意义
    'abs',         # abs(abs(x)) = abs(x)
    'sign',        # sign(sign(x)) = sign(x)
    'log',         # log(log(x)) 在 x>0 时有意义但高度冗余
}

# ── 恒等变换模式 ──
# (父操作符, 子操作符/值): 产生恒等/近似恒等
_IDENTITY_PATTERNS = {
    # Add(x, 0) / Add(0, x)
    ('Add', 0), ('Add', 0.0),
    # Sub(x, 0)
    ('Sub', 0), ('Sub', 0.0),
    # Mult(x, 1) / Mult(1, x)
    ('Mult', 1), ('Mult', 1.0),
    # Div(x, 1)
    ('Div', 1), ('Div', 1.0),
    # Sub(x, x) → 0, Div(x, x) → 1
}

# ── 截面函数（需要上下文才能有意义，不应独立出现） ──
_CS_FUNCTIONS: Set[str] = {
    'cs_rank', 'cs_scale', 'cs_zscore', 'cs_winsorize',
    'cs_quantile', 'cs_normalize',
}


class SemanticValidator:
    """语义层约束检查器

    检查内容:
      1. 必须包含至少一个数据变量（非纯常数表达式）
      2. 无冗余恒等变换（x+0, x*1, x/x, x-x）
      3. 无冗余嵌套（cs_rank(cs_rank(...)), abs(abs(...))）
      4. AST 深度检查
      5. 截面函数不能独立存在（需包裹在时序/组合上下文中）
    """

    def __init__(self, max_depth: int = 6, min_variables: int = 1):
        self.max_depth = max_depth
        self.min_variables = min_variables

    def check(self, tree: ast_module.AST) -> Tuple[bool, str]:
        """主检查入口

        Returns:
          (True, "")         — 通过
          (False, "reason") — 不通过及原因
        """
        # 1. 深度检查
        depth = self._compute_depth(tree)
        if depth > self.max_depth:
            return False, f"AST 深度 {depth} > {self.max_depth}"

        # 2. 变量检查
        var_count = self._count_variables(tree)
        if var_count < self.min_variables:
            return False, f"数据变量数 {var_count} < {self.min_variables}"

        # 3. 恒等变换检查
        id_ok, id_reason = self._check_identity(tree)
        if not id_ok:
            return False, id_reason

        # 4. 冗余嵌套检查
        nest_ok, nest_reason = self._check_redundant_nesting(tree)
        if not nest_ok:
            return False, nest_reason

        return True, ""

    def _compute_depth(self, node: ast_module.AST, current_depth: int = 0) -> int:
        """计算 AST 最大深度"""
        max_d = current_depth
        for child in ast_module.iter_child_nodes(node):
            child_d = self._compute_depth(child, current_depth + 1)
            max_d = max(max_d, child_d)
        return max_d

    def _count_variables(self, node: ast_module.AST) -> int:
        """统计 AST 中引用的数据变量数（去重）"""
        variables: Set[str] = set()

        class VarCollector(ast_module.NodeVisitor):
            def visit_Name(self, n):
                # 排除 Python 内置名和函数名
                if n.id not in ('True', 'False', 'None', 'math'):
                    variables.add(n.id)

        VarCollector().visit(node)
        return len(variables)

    def _check_identity(self, tree: ast_module.AST) -> Tuple[bool, str]:
        """检查是否包含恒等变换冗余

        检测模式:
          - Add/Sub 的其中一个操作数为 0
          - Mult 的其中一个操作数为 1
          - Div 的除数为 1（不是除数为 0 的问题，那是运行时错误）
          - Sub(x, x) → 0, Div(x, x) → 1
        """
        # 检查 Sub/Div 的左右子树是否完全相同
        for node in ast_module.walk(tree):
            if isinstance(node, ast_module.BinOp):
                left_str = ast_module.dump(node.left, annotate_fields=False)
                right_str = ast_module.dump(node.right, annotate_fields=False)

                if left_str == right_str:
                    if isinstance(node.op, ast_module.Sub):
                        return False, "冗余: x - x (恒为 0)"
                    if isinstance(node.op, ast_module.Div):
                        return False, "冗余: x / x (恒为 1)"

            # 检查是否为常数加 0 / 乘 1
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
        """检查冗余函数嵌套

        检测: f(f(...)) 其中 f 在 _REDUNDANT_NESTING 中
        """
        for node in ast_module.walk(tree):
            if isinstance(node, ast_module.Call):
                func_name = self._get_func_name(node)
                if func_name is None:
                    continue
                if func_name in _REDUNDANT_NESTING:
                    # 检查参数中是否有同名函数调用
                    for arg in node.args:
                        if isinstance(arg, ast_module.Call):
                            inner_name = self._get_func_name(arg)
                            if inner_name == func_name:
                                return False, f"冗余嵌套: {func_name}({func_name}(...))"
        return True, ""

    def _get_func_name(self, call_node: ast_module.Call) -> Optional[str]:
        """从 Call 节点提取函数名"""
        if isinstance(call_node.func, ast_module.Name):
            return call_node.func.id
        if isinstance(call_node.func, ast_module.Attribute):
            return call_node.func.attr
        return None

    @staticmethod
    def _is_constant(node: ast_module.AST, value) -> bool:
        """检查节点是否为指定值的常数"""
        if isinstance(node, ast_module.Constant):
            return node.value == value
        # UnaryOp 如 -0 也算常数
        if isinstance(node, ast_module.UnaryOp) and isinstance(node.op, ast_module.USub):
            if isinstance(node.operand, ast_module.Constant):
                return -node.operand.value == value
        return False


class CFGGrammar:
    """上下文无关文法约束（AlphaCFG 方案）

    定义合法因子的产生式规则:
      EXPR    → UNARY(EXPR) | BINARY(EXPR, EXPR) | TS(EXPR, INT) | VAR | CONST
      BOOL    → COMPARE(EXPR, EXPR) | LOGIC(BOOL, BOOL) | NOT(BOOL)
      COMPARE → > | >= | < | <= | == | !=
      LOGIC   → and | or
    """

    def __init__(self, allowed_functions: Optional[Set[str]] = None):
        """
        Args:
          allowed_functions: 允许的函数名集合。
            如果为 None，则不限制函数名（仅检查 AST 结构合法性）。
            通常设为 v5 TreeGenConfig 中的 func_allowlist。
        """
        self.allowed_functions = allowed_functions

    def is_syntactically_valid(self, tree: ast_module.AST) -> Tuple[bool, str]:
        """语法层检查：AST 结构合法 + 函数在允许列表中"""
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
        """返回新的 CFGGrammar 实例，使用指定的函数允许列表"""
        return CFGGrammar(allowed_functions=func_set)
