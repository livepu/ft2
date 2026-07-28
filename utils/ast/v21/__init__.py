"""
utils/ast/v21 — 公共 AST 基础设施 (编译缓存优化版)
═══════════════════════════════════════════════════════════════
v21 vs v2 核心差异:
  1. evaluate() 改用编译缓存: AST → compiled lambda → lru_cache
     避免递归 _eval_node 的 isinstance 开销, 预期 5-10x 加速
  2. 新增 compile_expression() 公开 API: 直接返回可调用函数
  3. 新增 _compile_expression() 内部编译, 同 v2 安全校验不变
  4. 向后兼容: 旧 evaluate() 保留为 _eval_node_fallback
═══════════════════════════════════════════════════════════════

架构 (5 个实质文件):

  1. 语法层  (dsl.py)        → 定义"能写什么"
     parse_expression()    — Python AST 解析 (白名单/黑名单安全校验)
     evaluate()            — 编译缓存求值 (优先) / 递归求值 (回退)
     compile_expression()  — [新增] 编译 AST 为可调用函数
     eval_colwise()        — 面板逐列求值 (2D 安全)
     cross_sectional_rank()— 截面排名 0~1
     normalize_data_keys() — 数据键 ALL_CAPS 规范化

  2. 原语+变量层  (functions.py)  → 定义"能算什么"+"能引用什么"
     FUNC_REGISTRY          — 92 时序/截面/数学/特征函数
     FunctionSpec           — 函数元数据 (category/data_args/param_pool/param_ranges)
     ParamRange             — 参数值域约束 (dtype/min/max/pool)
     FUNC_CATEGORIES        — 按类别索引
     VALID_VAR_PREFIXES     — 70+ 合法变量前缀
     VAR_CATEGORIES         — 按类别索引

  3. 编排层  (resolver.py)   → 截面函数嵌套解算
     CsResolver.resolve()   — 单遍 bottom-up AST 变换
     自动发现 cs_* 前缀函数, 处理任意深度嵌套/组合

  4. 规格层  (spec.py)       → AST 构建+表达式基类
     AstExpression          — DSL 表达式基类 (解析+自省)
     make_var/make_call/... — 类型安全 AST 节点构建器 (供 GP 引擎)
     normalize_expression() — 表达式规范化
     describe_expression()  — 表达式结构化描述 (供 LLM)
     grammar_spec_for_llm() — 语法规格 (供 LLM prompt)

  依赖方向: 语法 ← 原语+变量 ← 编排 ← 规格
═══════════════════════════════════════════════════════════════

命名约定 (对齐 WQ101 行业标准):
  变量:   ALL_CAPS          CLOSE, REL_CLOSE, SECTOR_UP
  函数:   prefix_snake      ts_roc, cs_rank, expanding_std
  窗口:   参数名 d (day)      ts_mean(x, d)
  统计:   样本 ddof=1         ts_std, ts_skew, cs_zscore

[新增] 2026-07-28 v21: 编译缓存求值, 递归 _eval_node 保留为回退
"""

# ── 语法层 (dsl.py) ──
from .dsl import (
    parse_expression, evaluate, validate_expression,
    get_variables, get_functions,
    normalize_data_keys,
    eval_colwise, cross_sectional_rank,
    ast_depth, ast_node_count, walk_nodes,
    DSLSecurityError, DSLSyntaxError,
    # [v21] 编译缓存求值
    compile_expression, _compile_expression,
    _ast_to_expr, _eval_node_fallback,
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
    # [v21] 编译缓存求值
    'compile_expression', '_compile_expression', '_ast_to_expr',
    '_eval_node_fallback',

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
