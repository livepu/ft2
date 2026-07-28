"""
utils/ast/v21/dsl.py — 语法层
=============================================================================

求值路径:
  evaluate(tree, data)  → _eval_node_fallback(tree.body, data)   [与 v2 等价]
  eval_colwise(...)      → 预编译表达式 → compiled_fn 逐列调用   [v21 优化]
  compile_expression(s)  → 返回 compiled_fn, 供 GP 引擎外层编译  [v21 新增]

编译缓存:
  仅用于 eval_colwise (面板求值) 和 compile_expression (公开 API)。
  evaluate() 单次调用不使用编译缓存 — ast.unparse 开销 (14us) > 编译收益 (~4us)。

安全校验: 无变化 (复用 v2 的 parse_expression + 白名单/黑名单)
"""
import ast
import operator
import numpy as np
from typing import Dict, Any, Callable, Optional

from .registry import (
    FUNC_REGISTRY, SAFE_CONSTANTS,
    is_valid_variable, VALID_VAR_PREFIXES,
)

# ============================================================
# 数据键规范化 — 应用端统一入口 (ALL_CAPS 约定)
# [新增] 2026-06-22 全大写规范化, 对齐 WQ101 行业标准
# ============================================================

def normalize_data_keys(data: Dict[str, Any]) -> Dict[str, np.ndarray]:
    """[新增] 2026-06-22 规范化数据键名, 统一大小写

    规则:
      1. 所有键统一转为大写 (ALL_CAPS 约定, 对齐 WQ/聚宽 等行业标准)
      2. 所有值转为 float ndarray
      3. 冲突处理: 同名键 (如同时有 close 和 CLOSE) 后者覆盖前者

    业内规范:
      WorldQuant (WQ101/GT191)、聚宽、RiceQuant 等量化平台均采用
      ALL_CAPS 作为公式变量命名约定。数据源 (Yahoo/d2) 通常小写,
      在进入 AST 引擎前统一归一化。

    Args:
        data: 原始数据字典, 键名大小写不敏感

    Returns:
        规范化后的字典 {全部大写键: ndarray}
    """
    result = {}
    for k, v in data.items():
        key = k.upper()
        # [修复] 2026-07-06 大小写归一冲突时 warn (原静默覆盖, 难以排查数据丢失)
        if key in result:
            import warnings
            warnings.warn(
                f"normalize_data_keys: 键 '{k}' 与已有键冲突 "
                f"(归一后均为 '{key}'), 后者覆盖前者"
            )
        result[key] = np.asarray(v, dtype=float)
    return result

# ============================================================
# 安全白名单 — 允许的 AST 节点类型
# ============================================================

ALLOWED_NODE_TYPES = {
    ast.Expression,     # 顶层
    ast.BinOp,          # + - * / // % **
    ast.UnaryOp,        # -x, +x, not x
    ast.BoolOp,         # and, or
    ast.Compare,        # > < >= <= == !=
    ast.IfExp,          # a if cond else b
    ast.Call,           # 函数调用
    ast.Name,           # 变量引用
    ast.Constant,       # 常量
    ast.Load,           # 加载上下文
    ast.Add, ast.Sub, ast.Mult, ast.Div,
    ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.Invert,
    ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    # [修复] 2026-07-06 移除 ast.Is/IsNot: 身份比较对 ndarray 无意义, 易误用为值相等
    ast.keyword,        # 关键字参数
}

# 禁止的节点类型（如有则直接拒绝）
_FORBIDDEN_TYPES = {
    ast.Import, ast.ImportFrom,
    ast.Attribute,
    ast.Subscript,
    ast.Lambda,
    ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp,
    ast.Yield, ast.YieldFrom,
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
    ast.Global, ast.Nonlocal,
    ast.Await, ast.AsyncFor, ast.AsyncWith,
    ast.Raise, ast.Try, ast.Assert,
    ast.Delete, ast.Pass, ast.Break, ast.Continue,
    ast.Return,
    ast.With, ast.AsyncWith,
    ast.For, ast.AsyncFor, ast.While,
    ast.If,  # 只允许 IfExp（三元），不允许 If 语句块
    ast.JoinedStr, ast.FormattedValue,
}

# Python 3.10+ 的 match-case
if hasattr(ast, 'Match'):
    _FORBIDDEN_TYPES.add(ast.Match)

# [废弃] Python 3.8+ 已移除 ast.Exec, 仅保留注释供参考
# if hasattr(ast, 'Exec'):
#     _FORBIDDEN_TYPES.add(ast.Exec)

FORBIDDEN_NODE_TYPES = frozenset(_FORBIDDEN_TYPES)

# ============================================================
# 运算符映射
# ============================================================

BINOP_MAP = {
    ast.Add:      operator.add,
    ast.Sub:      operator.sub,
    ast.Mult:     operator.mul,
    ast.Div:      lambda a, b: np.where(np.abs(b) > 1e-10, a / b, 0.0),
    ast.FloorDiv: lambda a, b: np.floor(np.where(np.abs(b) > 1e-10, a / b, 0.0)),
    ast.Mod:      lambda a, b: np.where(np.abs(b) > 1e-10, a % b, 0.0),
    ast.Pow:      lambda a, b: np.power(np.clip(a, -1e6, 1e6), np.clip(b, -10, 10)),
}

UNARYOP_MAP = {
    ast.USub:   operator.neg,
    ast.UAdd:   operator.pos,
    ast.Not:    lambda x: np.where(x == 0, 1.0, 0.0),
    ast.Invert: operator.inv,
}

CMPOP_MAP = {
    ast.Eq:    lambda a, b: np.where(np.abs(a - b) < 1e-10, 1.0, 0.0),
    ast.NotEq: lambda a, b: np.where(np.abs(a - b) >= 1e-10, 1.0, 0.0),
    ast.Lt:    lambda a, b: np.where(a < b, 1.0, 0.0),
    ast.LtE:   lambda a, b: np.where(a <= b, 1.0, 0.0),
    ast.Gt:    lambda a, b: np.where(a > b, 1.0, 0.0),
    ast.GtE:   lambda a, b: np.where(a >= b, 1.0, 0.0),
    # [修复] 2026-07-06 移除 ast.Is/IsNot: 身份比较对 ndarray 无意义
}

# ============================================================
# [v21] 运算符包装函数 — 编译缓存求值用
# 语义与 BINOP_MAP/CMPOP_MAP/UNARYOP_MAP 完全一致
# ============================================================

def _op_add(a, b):      return a + b
def _op_sub(a, b):      return a - b
def _op_mul(a, b):      return a * b
def _op_div(a, b):      return np.where(np.abs(b) > 1e-10, a / b, 0.0)
def _op_floordiv(a, b): return np.floor(np.where(np.abs(b) > 1e-10, a / b, 0.0))
def _op_mod(a, b):      return np.where(np.abs(b) > 1e-10, a % b, 0.0)
def _op_pow(a, b):      return np.power(np.clip(a, -1e6, 1e6), np.clip(b, -10, 10))
def _op_neg(a):         return -a
def _op_pos(a):         return +a
def _op_not(a):         return np.where(a == 0, 1.0, 0.0)
def _op_invert(a):      return ~a
def _op_eq(a, b):       return np.where(np.abs(a - b) < 1e-10, 1.0, 0.0)
def _op_ne(a, b):       return np.where(np.abs(a - b) >= 1e-10, 1.0, 0.0)
def _op_lt(a, b):       return np.where(a < b, 1.0, 0.0)
def _op_le(a, b):       return np.where(a <= b, 1.0, 0.0)
def _op_gt(a, b):       return np.where(a > b, 1.0, 0.0)
def _op_ge(a, b):       return np.where(a >= b, 1.0, 0.0)

# 运算符 → 包装函数名 映射 (编译代码生成用)
_BINOP_FN = {
    ast.Add: '_op_add', ast.Sub: '_op_sub', ast.Mult: '_op_mul',
    ast.Div: '_op_div', ast.FloorDiv: '_op_floordiv',
    ast.Mod: '_op_mod', ast.Pow: '_op_pow',
}
_UNARYOP_FN = {
    ast.USub: '_op_neg', ast.UAdd: '_op_pos',
    ast.Not: '_op_not', ast.Invert: '_op_invert',
}
_CMPOP_FN = {
    ast.Eq: '_op_eq', ast.NotEq: '_op_ne',
    ast.Lt: '_op_lt', ast.LtE: '_op_le',
    ast.Gt: '_op_gt', ast.GtE: '_op_ge',
}

# ============================================================
# 解析 + 校验
# ============================================================

class DSLSecurityError(Exception):
    """安全校验失败"""
    pass

class DSLSyntaxError(Exception):
    """语法错误"""
    pass


def _check_node_safety(node: ast.AST):
    """递归检查 AST 节点安全性"""
    # 禁止节点检查
    for forbidden in FORBIDDEN_NODE_TYPES:
        if isinstance(node, forbidden):
            raise DSLSecurityError(
                f"禁止的节点类型: {type(node).__name__}。"
                f"只允许数学表达式和函数调用。"
            )
    
    # 白名单检查
    if not any(isinstance(node, allowed) for allowed in ALLOWED_NODE_TYPES):
        raise DSLSecurityError(
            f"不允许的节点类型: {type(node).__name__}"
        )
    
    # 额外检查：函数调用必须是白名单
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name not in FUNC_REGISTRY:
                raise DSLSecurityError(
                    f"未注册的函数: '{func_name}'。"
                    f"可用函数: {sorted(FUNC_REGISTRY.keys())}"
                )
        else:
            raise DSLSecurityError("只允许直接函数调用，不支持属性/下标调用")
    
    # 变量名检查（跳过函数名——它们在 Call 节点中已校验）
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        name = node.id
        if name in SAFE_CONSTANTS or name in FUNC_REGISTRY:
            return  # 安全常量 / 注册函数名通过
        if not is_valid_variable(name):
            raise DSLSecurityError(
                f"未注册的变量: '{name}'。"
                f"变量名必须匹配前缀: {VALID_VAR_PREFIXES}"
            )
    
    # 递归检查子节点
    for child in ast.iter_child_nodes(node):
        _check_node_safety(child)


def _check_complexity(node: ast.AST, max_depth: int = 30, max_nodes: int = 500):
    """检查表达式复杂度
    [修正] 2026-06-25 max_depth 15→30, max_nodes 200→500.
    原限制 15 深度不足以支撑分层组合(多组 cs_rank 嵌套+算术)."""
    depth = _ast_depth(node)
    if depth > max_depth:
        raise DSLSecurityError(f"表达式深度 {depth} 超过上限 {max_depth}")
    
    node_count = sum(1 for _ in ast.walk(node))
    if node_count > max_nodes:
        raise DSLSecurityError(f"表达式节点数 {node_count} 超过上限 {max_nodes}")


def _ast_depth(node: ast.AST) -> int:
    """计算 AST 最大深度"""
    if not list(ast.iter_child_nodes(node)):
        return 1
    return 1 + max(_ast_depth(child) for child in ast.iter_child_nodes(node))


def parse_expression(expr_str: str, 
                     max_depth: int = 30,
                     max_nodes: int = 500) -> ast.Expression:
    """
    解析并校验表达式字符串
    
    Returns:
        ast.Expression 节点
    
    Raises:
        DSLSyntaxError: 语法错误
        DSLSecurityError: 安全/语义校验失败
    """
    # 清理
    expr_str = expr_str.strip()
    if not expr_str:
        raise DSLSyntaxError("表达式为空")
    
    # 解析
    try:
        tree = ast.parse(expr_str, mode='eval')
    except SyntaxError as e:
        raise DSLSyntaxError(f"Python 语法错误: {e.msg} (位置: 行{e.lineno}, 列{e.offset})")
    
    # 三层校验
    _check_node_safety(tree.body)
    _check_complexity(tree.body, max_depth, max_nodes)
    
    return tree


# ============================================================
# 求值器
# ============================================================

# ============================================================
# [v21] 编译缓存求值器 — 方案A: 编译可调用函数 + lru_cache
# ============================================================

# 编译缓存: {expr_str: callable}
_EXPR_CACHE: Dict[str, Callable] = {}

# 编译用命名空间 (延迟初始化, 包含所有注册函数 + 运算符包装)
_COMPILE_NS: Dict[str, Any] = {}

def _get_compile_namespace() -> Dict[str, Any]:
    """获取编译命名空间 (延迟初始化, 包含所有注册函数 + 运算符包装 + numpy)"""
    if not _COMPILE_NS:
        ns = {}
        # 注册函数
        for k, spec in FUNC_REGISTRY.items():
            ns[k] = spec.func
        # 运算符包装
        ns['_op_add'] = _op_add
        ns['_op_sub'] = _op_sub
        ns['_op_mul'] = _op_mul
        ns['_op_div'] = _op_div
        ns['_op_floordiv'] = _op_floordiv
        ns['_op_mod'] = _op_mod
        ns['_op_pow'] = _op_pow
        ns['_op_neg'] = _op_neg
        ns['_op_pos'] = _op_pos
        ns['_op_not'] = _op_not
        ns['_op_invert'] = _op_invert
        ns['_op_eq'] = _op_eq
        ns['_op_ne'] = _op_ne
        ns['_op_lt'] = _op_lt
        ns['_op_le'] = _op_le
        ns['_op_gt'] = _op_gt
        ns['_op_ge'] = _op_ge
        # numpy
        ns['np'] = np
        _COMPILE_NS.update(ns)
    return _COMPILE_NS


def _ast_to_expr(node: ast.AST) -> str:
    """[v21] AST 节点 → Python 表达式字符串 (编译缓存用)

    将 AST 树转换为可直接编译的 Python 表达式字符串。
    与 _eval_node_fallback 语义完全一致:
      - 运算符调用 _op_* 包装函数 (而非直接 Python 运算符)
      - 变量引用转为 data['VAR'] 查找
      - 函数调用直接使用注册函数名
      - 安全常量内联其值
    """
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None:
            return '0.0'
        if isinstance(value, bool):
            return '1.0' if value else '0.0'
        if isinstance(value, (int, float)):
            # int 保持 int, float 保持 float
            return repr(value)
        raise DSLSecurityError(f"不支持的常量类型: {type(value)}")

    if isinstance(node, ast.Name):
        name = node.id
        if name in SAFE_CONSTANTS:
            return repr(SAFE_CONSTANTS[name])
        return f"data['{name.upper()}']"

    if isinstance(node, ast.BinOp):
        left = _ast_to_expr(node.left)
        right = _ast_to_expr(node.right)
        fn_name = _BINOP_FN.get(type(node.op))
        if fn_name is None:
            raise DSLSecurityError(f"不支持的二元运算: {type(node.op).__name__}")
        return f"{fn_name}({left}, {right})"

    if isinstance(node, ast.UnaryOp):
        operand = _ast_to_expr(node.operand)
        fn_name = _UNARYOP_FN.get(type(node.op))
        if fn_name is None:
            raise DSLSecurityError(f"不支持的一元运算: {type(node.op).__name__}")
        return f"{fn_name}({operand})"

    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise DSLSecurityError("只支持单一比较运算（如 a > b，不支持 a > b > c）")
        left = _ast_to_expr(node.left)
        right = _ast_to_expr(node.comparators[0])
        fn_name = _CMPOP_FN.get(type(node.ops[0]))
        if fn_name is None:
            raise DSLSecurityError(f"不支持的比较运算: {type(node.ops[0]).__name__}")
        return f"{fn_name}({left}, {right})"

    if isinstance(node, ast.BoolOp):
        values = [_ast_to_expr(v) for v in node.values]
        if isinstance(node.op, ast.And):
            # AND: 逐元素 minimum, 两者都 >0 才为 1
            joined = ', '.join(values)
            return f"np.minimum.reduce([{joined}])"
        elif isinstance(node.op, ast.Or):
            # OR: 逐元素 maximum, 任一 >0 即为 1
            joined = ', '.join(values)
            return f"np.maximum.reduce([{joined}])"

    if isinstance(node, ast.IfExp):
        test = _ast_to_expr(node.test)
        body = _ast_to_expr(node.body)
        orelse = _ast_to_expr(node.orelse)
        return f"np.where({test} > 0, {body}, {orelse})"

    if isinstance(node, ast.Call):
        func_name = node.func.id if isinstance(node.func, ast.Name) else None
        if func_name is None:
            raise DSLSecurityError("只允许直接函数调用")
        args = [_ast_to_expr(a) for a in node.args]
        kwargs = [f"{kw.arg}={_ast_to_expr(kw.value)}" for kw in node.keywords]
        all_args = ', '.join(args + kwargs)
        return f"{func_name}({all_args})"

    raise DSLSecurityError(f"不支持的节点类型: {type(node).__name__}")


def _compile_expression(expr_str: str) -> Callable:
    """[v21] 编译表达式字符串为可调用函数 (编译缓存)

    流程:
      1. parse_expression() 安全校验 (同 v2, 白名单/黑名单不变)
      2. _ast_to_expr() 生成 Python 表达式代码
      3. eval() 编译为 lambda 函数
      4. 缓存到 _EXPR_CACHE

    Returns:
        可调用函数: Callable[[Dict[str, np.ndarray]], np.ndarray]

    线程安全:
      - 阶段1 (单线程): 首次编译写入 _EXPR_CACHE
      - 阶段2 (多线程): 只读 _EXPR_CACHE, GIL 保护下安全
      - 禁止: 在阶段2 动态注册新函数后访问旧缓存
    """
    if expr_str in _EXPR_CACHE:
        return _EXPR_CACHE[expr_str]

    # 1. 解析并安全校验 (同 v2)
    tree = parse_expression(expr_str)

    # 2. 生成 Python 表达式代码
    expr_code = _ast_to_expr(tree.body)

    # 3. 编译为 lambda 函数
    ns = _get_compile_namespace()
    lambda_code = f"lambda data: {expr_code}"
    compiled = eval(lambda_code, ns)

    # 4. 缓存
    _EXPR_CACHE[expr_str] = compiled
    return compiled


def compile_expression(expr_str: str) -> Callable:
    """[v21] 编译表达式为可调用函数 (公开 API)

    与 evaluate() 的区别:
      - evaluate(tree, data)  → 一次性求值
      - compile_expression(str) → 返回可重复调用的 compiled(data)

    GP 引擎使用场景: 同一表达式在面板不同列上反复求值时,
    编译一次, 多次调用 compiled_fn(data), 避免重复解析开销。

    Example:
        >>> from utils.ast.v21 import compile_expression
        >>> fn = compile_expression('ts_roc(CLOSE, 20)')
        >>> result = fn(data)  # 直接调用, 零递归开销
    """
    return _compile_expression(expr_str)


def evaluate(tree: ast.Expression,
             data: Dict[str, np.ndarray]) -> np.ndarray:
    """求值 AST 表达式

    直接调用 _eval_node_fallback 递归求值，保持与 v2 一致。
    编译缓存路径通过 compile_expression() 公开发用,
    eval_colwise 内部自动使用预编译模式。

    Args:
        tree: parse_expression() 返回的 AST
        data: 数据字典 {变量名: np.ndarray}
              包含原始 OHLCV (CLOSE, OPEN, HIGH, LOW, VOLUME)
              和预计算特征 (RSI_14, ATR_7, EMA_20, ...)

    Returns:
        np.ndarray，形状与数据长度一致
    """
    return _eval_node_fallback(tree.body, data)


def _eval_node_fallback(node: ast.AST, data: Dict[str, np.ndarray]) -> np.ndarray:
    """[v21] 递归求值 AST 节点 (回退路径, 同 v2 的 _eval_node)

    保留原 _eval_node 作为安全网, 仅在编译缓存失败时调用。
    """
    # 常量
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None:
            return np.array([0.0])
        if isinstance(value, bool):
            return np.array([1.0 if value else 0.0])
        if isinstance(value, (int, float)):
            return np.array([float(value)])
        raise DSLSecurityError(f"不支持的常量类型: {type(value)}")

    # 变量引用
    if isinstance(node, ast.Name):
        name = node.id
        if name in SAFE_CONSTANTS:  # 安全常量（True/False/None/pi/e）
            return np.array([SAFE_CONSTANTS[name]])
        # 数据变量
        name_upper = name.upper()
        if name_upper in data:
            return np.asarray(data[name_upper], dtype=float).copy()
        if name in data:
            return np.asarray(data[name], dtype=float).copy()
        # 模糊匹配（允许大小写容错）
        for key in data:
            if key.upper() == name_upper:
                return np.asarray(data[key], dtype=float).copy()
        raise KeyError(
            f"变量 '{name}' 不在数据字典中。"
            f"可用变量: {sorted(data.keys())}"
        )

    # 二元运算: a + b, a * b, etc.
    if isinstance(node, ast.BinOp):
        left = _eval_node_fallback(node.left, data)
        right = _eval_node_fallback(node.right, data)
        op_func = BINOP_MAP.get(type(node.op))
        if op_func is None:
            raise DSLSecurityError(f"不支持的二元运算: {type(node.op).__name__}")
        return op_func(left, right)

    # 一元运算: -x, +x, not x
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node_fallback(node.operand, data)
        op_func = UNARYOP_MAP.get(type(node.op))
        if op_func is None:
            raise DSLSecurityError(f"不支持的一元运算: {type(node.op).__name__}")
        return op_func(operand)

    # 比较运算: a > b, a < b, a == b, etc.
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise DSLSecurityError("只支持单一比较运算（如 a > b，不支持 a > b > c）")
        left = _eval_node_fallback(node.left, data)
        right = _eval_node_fallback(node.comparators[0], data)
        op_func = CMPOP_MAP.get(type(node.ops[0]))
        if op_func is None:
            raise DSLSecurityError(f"不支持的比较运算: {type(node.ops[0]).__name__}")
        return op_func(left, right)

    # 布尔运算: a and b, a or b
    if isinstance(node, ast.BoolOp):
        values = [_eval_node_fallback(v, data) for v in node.values]
        if isinstance(node.op, ast.And):
            result = np.ones_like(values[0])
            for v in values:
                result = np.minimum(result, v)
            return result
        elif isinstance(node.op, ast.Or):
            result = np.zeros_like(values[0])
            for v in values:
                result = np.maximum(result, v)
            return result

    # 三元表达式: a if cond else b
    if isinstance(node, ast.IfExp):
        cond = _eval_node_fallback(node.test, data)
        a_val = _eval_node_fallback(node.body, data)
        b_val = _eval_node_fallback(node.orelse, data)
        return np.where(cond > 0, a_val, b_val)

    # 函数调用
    if isinstance(node, ast.Call):
        func_name = node.func.id if isinstance(node.func, ast.Name) else None
        if func_name is None or func_name not in FUNC_REGISTRY:
            raise DSLSecurityError(f"未注册的函数: {func_name}")

        func = FUNC_REGISTRY[func_name]
        args = []
        for arg_node in node.args:
            val = _eval_node_fallback(arg_node, data)
            args.append(_unwrap_scalar(val))
        kwargs = {}
        for kw in node.keywords:
            val = _eval_node_fallback(kw.value, data)
            kwargs[kw.arg] = _unwrap_scalar(val)

        return func(*args, **kwargs)

    raise DSLSecurityError(f"不支持的节点类型: {type(node).__name__}")


def _unwrap_scalar(val: np.ndarray):
    """将标量数组解包为 Python 原生类型（int 或 float）"""
    if val.size != 1:
        return val
    v = val.item()
    if isinstance(v, float) and v == int(v) and abs(v) < 1e12:
        return int(v)
    return v


# ============================================================
# 工具函数
# ============================================================

def get_variables(tree: ast.Expression) -> list:
    """提取表达式中引用的所有变量名

    排除安全常量 (True/False/None/pi/e) 和已注册函数名
    (避免 vol_ratio/atr 等同名变量被误判)。
    """
    vars_set = set()
    for node in ast.walk(tree.body):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            name = node.id
            if name in SAFE_CONSTANTS or name.lower() in FUNC_REGISTRY:
                continue  # 跳过常量和函数名
            if is_valid_variable(name):
                vars_set.add(name.upper())
    return sorted(vars_set)


def get_functions(tree: ast.Expression) -> list:
    """提取表达式中调用的所有函数名"""
    funcs = set()
    for node in ast.walk(tree.body):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            funcs.add(node.func.id)
    return sorted(funcs)


def validate_expression(expr_str: str, available_vars: Optional[list] = None) -> dict:
    """LLM 前置校验: 表达式语法 + 变量存在性

    不依赖数据求值, 只做 parse + 变量对比。
    适合 LLM 生成表达式后立即调用, 避免等到 evaluate() 才发现 KeyError。

    Args:
        expr_str: 表达式字符串
        available_vars: 可用变量名列表 (大小写不敏感), None 则跳过变量存在性检查

    Returns:
        {'valid': bool, 'errors': [str], 'variables': [str], 'missing_vars': [str]}
    """
    result = {'valid': True, 'errors': [], 'variables': [], 'missing_vars': []}
    try:
        tree = parse_expression(expr_str)
        result['variables'] = get_variables(tree)
    except (DSLSyntaxError, DSLSecurityError) as e:
        result['valid'] = False
        result['errors'].append(str(e))
        return result

    if available_vars is not None:
        avail_upper = {v.upper() for v in available_vars}
        for var in result['variables']:
            if var.upper() not in avail_upper:
                result['missing_vars'].append(var)
                result['valid'] = False
                result['errors'].append(
                    f"变量 '{var}' 不在可用数据中。"
                    f"可用: {sorted(avail_upper)}"
                )
    return result


# ============================================================
# 面板逐列求值器 — 时序函数在 1D 上安全求值
# ============================================================

def eval_colwise(tree: ast.Expression, data: Dict[str, np.ndarray],
                 T: int, N: int, strict: bool = False) -> np.ndarray:
    """逐列求值 AST — 时序函数在 1D 上安全求值

    设计理由:
      _rolling / _expanding / _persist 只处理 1D 数组,
      因此 2D 面板必须逐列调用 evaluate()。

    [v21] 编译缓存优化:
      表达式只解析一次 (ast.unparse + _compile_expression),
      逐列循环中直接调用 compiled_fn(col_data), 避免每列 15us 的 unparse 开销。
      编译失败时自动回退到 evaluate() 路径。

    Args:
        strict: False=静默返回NaN (批量回测/搜索模式),
                True=异常立即抛出 (调试模式, 带列号定位)

    [重构] 2026-06-22 从 resolver.py 移动到 dsl.py (通用工具)
    [修复] 2026-07-13 对齐 WQ101 NaN 处理规范:
           - NaN (冷启动/求值失败) 保留为 NaN, 不转 0。
             WQ101 规范: NaN=缺失数据, 截面算子应跳过, 不参与排名。
             下游 _cs_rank_core 已 nan-aware (跳过 NaN 行), 保留 NaN 安全。
           - inf/-inf (除零等) 转为 NaN, 因 inf 非合法因子值且
             _cs_rank_core 只跳 NaN 不跳 inf, 需在此归一化。
           - 原实现 nan_to_num(nan=0.0) 把冷启动 NaN 误转为 0,
             被 cross_sectional_rank 当真实值排名, 产生假信号 (P0-1)。
    [优化] 2026-07-28 v21: 预编译表达式, 逐列直接调用 compiled_fn, 避免重复 unparse
    """
    # [v21] 预编译表达式: 只 unparse + compile 一次, 逐列复用
    compiled_fn = None
    try:
        expr_str = ast.unparse(tree)
        compiled_fn = _compile_expression(expr_str)
    except Exception:
        # 编译失败 (如含不支持节点), 回退到 evaluate() 逐列路径
        pass

    result = np.full((T, N), np.nan)
    for j in range(N):
        col_data = {}
        for k, v in data.items():
            if isinstance(v, np.ndarray) and v.ndim == 2:
                col_data[k] = v[:, j]
            else:
                col_data[k] = v
        try:
            if compiled_fn is not None:
                col_result = compiled_fn(col_data)
            else:
                col_result = evaluate(tree, col_data)
            if isinstance(col_result, np.ndarray):
                result[:, j] = col_result[:T].ravel()
            elif isinstance(col_result, (int, float, np.integer, np.floating)):
                result[:, j] = float(col_result)
        except Exception as e:
            if strict:
                raise RuntimeError(
                    f"eval_colwise 第 {j} 列求值失败: {e}"
                ) from e
            result[:, j] = np.nan
    # [修复] 2026-07-13 对齐 WQ101: 保留 NaN (下游 _cs_rank_core 跳过), 仅 inf→NaN
    return np.where(np.isinf(result), np.nan, result)


def cross_sectional_rank(vals: np.ndarray) -> np.ndarray:
    """每日截面排名 → (0, 1] (min 竞争排名, 与 signals/v4 cs_rank 逻辑一致)

    全 NaN 行保持 NaN (不参与排名), 对齐 WQ 规范: NaN=缺失, 截面算子应跳过.
    [修复] 2026-07-09 改为直接调用 functions._cs_rank_core (numba @njit):
           ① 统一与 cs_rank() 的语义, 消除 scipy/numba 双实现分歧 (P3-B);
           ② 全 NaN 行由 0.0 改为 NaN, 对齐 WQ "NaN 不排名" 规范 (P1-D);
           ③ ~28x 加速.
    [修正] 2026-06-25 改为 method='min', 对齐 WQ/DolphinDB 行业标准.
    [重构] 2026-06-22 从 resolver.py 移动到 dsl.py (通用工具)
    """
    vals = np.asarray(vals, dtype=float)
    if vals.ndim != 2:
        return vals
    from .functions import _cs_rank_core
    return _cs_rank_core(vals)


# ============================================================
# 表达式自省扩展 — 结构化描述
# ============================================================

def ast_depth(tree) -> int:
    """计算 AST 最大深度"""
    def _depth(node):
        children = list(ast.iter_child_nodes(node))
        if not children:
            return 1
        return 1 + max(_depth(c) for c in children)
    # [兼容] 2026-07-08 支持任意 AST 节点，不仅限于 ast.Expression
    body = tree.body if hasattr(tree, 'body') else tree
    return _depth(body)


def ast_node_count(tree) -> int:
    """计算 AST 节点总数"""
    # [兼容] 2026-07-08 支持任意 AST 节点，不仅限于 ast.Expression
    body = tree.body if hasattr(tree, 'body') else tree
    return sum(1 for _ in ast.walk(body))


# ============================================================
# AST 遍历统一入口 — 安全遍历表达式节点
# ============================================================

def walk_nodes(tree: ast.AST) -> list:
    """安全遍历 AST 所有节点（统一入口）。

    兼容 ast.Expression / ast.Module / 任意 AST 节点，
    消费者不再需要关心 .body 细节。

    用法:
        from utils.ast.v2 import walk_nodes
        for node in walk_nodes(tree):
            if isinstance(node, ast.Call):
                ...

    Args:
        tree: 任意 AST 节点（通常为 parse_expression 返回的 ast.Expression）

    Returns:
        list: 遍历得到的节点列表（不包括 Expression/Module 等容器节点本身）
    """
    # ast.Expression: 内部 body 是单节点，需要 walk(body) 避免遍历 Expression 自身
    if isinstance(tree, ast.Expression):
        return list(ast.walk(tree.body))
    # ast.Module: body 是语句列表，需要 walk 每个 statement
    if isinstance(tree, ast.Module):
        nodes = []
        for stmt in tree.body:
            nodes.extend(ast.walk(stmt))
        return nodes
    # 已经是裸节点或任意其他 AST 类型，直接 walk
    return list(ast.walk(tree))
