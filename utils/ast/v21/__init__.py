"""
utils/ast/v21 — 公共 AST 基础设施
═══════════════════════════════════════════════════════════════
v21 vs v2 核心差异:
  1. eval_colwise() 预编译表达式, 逐列直接调用 compiled_fn
     节省每列 14us 的 ast.unparse 开销, 面板级 1.1-1.4x 加速
  2. 新增 compile_expression() 公开 API: 编译表达式为可调用函数
     供 GP 引擎外层编译一次, 内层 O(1) 调用
  3. evaluate() 与 v2 等价: 直接 _eval_node_fallback 递归求值
     编译管道仅用于 eval_colwise 和 compile_expression
═══════════════════════════════════════════════════════════════

架构 (5 个文件, 自底向上):

  底层 — 注册 + 原语
    registry.py    注册表 (FunctionSpec, FUNC_REGISTRY, 宏引擎, 变量注册)
    functions.py   函数原语 (92 时序/截面/数学/特征函数, 23 numba core)

  中层 — 语法 + 编排
    dsl.py         语法层 (parse/evaluate/eval_colwise + 编译缓存)
    resolver.py    编排层 (CsResolver: cs_* 函数嵌套解算)

  顶层 — 规格 + 构建
    spec.py        AstExpression 基类 + 构建器 + LLM 语法规格

  依赖方向 (无循环):
    registry ← functions       (注册表单向依赖原语)
    dsl ← registry             (语法层依赖注册表)
    resolver ← dsl + registry   (编排层依赖语法 + 注册)
    spec ← dsl + registry + resolver  (规格层消费所有下层)
═══════════════════════════════════════════════════════════════

命名约定 (对齐 WQ101 行业标准):
  变量:   ALL_CAPS          CLOSE, REL_CLOSE, SECTOR_UP
  函数:   prefix_snake      ts_roc, cs_rank, expanding_std
  窗口:   参数名 d (day)      ts_mean(x, d)
  统计:   样本 ddof=1         ts_std, ts_skew, cs_zscore
"""

# ── 语法层 (dsl.py) ──
from .dsl import (
    parse_expression, evaluate, validate_expression,
    get_variables, get_functions,
    normalize_data_keys,
    eval_colwise, cross_sectional_rank,
    ast_depth, ast_node_count, walk_nodes,
    DSLSecurityError, DSLSyntaxError,
    # [v21] 公开 API
    compile_expression,
)

# ── 注册层 (registry.py) ──
# [重构] 2026-07-15 方案E: 统一 register 入口, 融合 _common/macros/functions 模块9-11
from .registry import (
    FUNC_REGISTRY, SAFE_CONSTANTS,
    FunctionSpec, ParamRange, VarSpec,
    register, register_function, register_macro, unregister_function,
    FUNC_CATEGORIES, VALID_FUNC_CATEGORIES, get_func_category,
    VALID_VAR_PREFIXES, is_valid_variable,
    register_variable, unregister_variable,
    VAR_CATEGORIES, get_var_category,
    is_macro, list_macros, macro_to_str, unregister_macro,
)

# ── 编排层 (resolver.py) ──
from .resolver import (
    CsResolver,
    _get_cs_functions, _has_any_cs, _is_outer_cs_rank_call,
)

# ── 基类层 (expr_base.py → spec.py) ──
from .spec import AstExpression

# ── 规格层 (spec.py) ──
from .spec import (
    # 构建器
    make_var, make_const, make_call,
    make_binop, make_unaryop, make_compare,
    make_boolop, make_ifexp,
    # 规范化器
    normalize_expression, normalize_ast,
    # 自省
    describe_expression,
    # 规格
    grammar_spec_for_llm, grammar_spec_compact,
    AST_GRAMMAR_SPEC,
)

__all__ = [
    # dsl — 语法层
    'parse_expression', 'evaluate', 'validate_expression',
    'get_variables', 'get_functions',
    'normalize_data_keys',
    'eval_colwise', 'cross_sectional_rank',
    'ast_depth', 'ast_node_count', 'walk_nodes',
    'DSLSecurityError', 'DSLSyntaxError',
    # [v21] 公开 API
    'compile_expression',

    # base — AST 表达式基类
    'AstExpression',

    # registry — 注册层 (函数+宏+变量, 统一管理)
    'FUNC_REGISTRY', 'SAFE_CONSTANTS',
    'FunctionSpec', 'ParamRange', 'VarSpec',
    'register', 'register_function', 'register_macro', 'unregister_function',
    'FUNC_CATEGORIES', 'VALID_FUNC_CATEGORIES', 'get_func_category',
    'VALID_VAR_PREFIXES', 'is_valid_variable',
    'register_variable', 'unregister_variable',
    'VAR_CATEGORIES', 'get_var_category',
    'is_macro', 'list_macros', 'macro_to_str', 'unregister_macro',

    # resolver — 编排层
    'CsResolver', '_get_cs_functions',
    '_has_any_cs', '_is_outer_cs_rank_call',

    # spec — 规格层
    'make_var', 'make_const', 'make_call',
    'make_binop', 'make_unaryop', 'make_compare',
    'make_boolop', 'make_ifexp',
    'normalize_expression', 'normalize_ast',
    'describe_expression',
    'grammar_spec_for_llm', 'grammar_spec_compact',
    'AST_GRAMMAR_SPEC',
]

# ============================================================
# 注册内置宏 (在所有模块加载完成后调用, 避免循环导入)
# [新增] 2026-07-15
# ============================================================
from .registry import _register_builtin_macros
_register_builtin_macros()
