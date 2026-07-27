"""
utils/mcts/v1/mutations.py — 自包含树生成 + 变异算子（零 v5 依赖）

完全独立于 v5 的 tree_gen.py / FUNC_REGISTRY / ast.v2.spec。
仅依赖: stdlib ast, random, copy + 本地 config.py, ast_utils.py
"""

import ast
import copy
import random
from typing import Optional

from .config import MutationConfig, MCTS_VARIABLES, MCTS_CONSTANTS
from .ast_utils import (
    _expr_str, _collect_replaceable, _replace_subtree,
    _simplify_ast, _parent_map, _walk_nodes,
)


# ============================================================
# 本地函数规格表（替代 ast.v2.registry.FUNC_REGISTRY）
# ============================================================
# 格式: func_name → (data_args, data_vars, param_pool, param_ranges)
#   data_args:   子树参数个数（如果 data_vars 为 None）
#   data_vars:   固定变量名元组（优先于 data_args）
#   param_pool:  离散参数的可选值列表
#   param_ranges: 连续参数范围列表 [(lo, hi, dtype), ...]

_FUNC_SPECS = {
    # 时序函数
    'ts_rank':   (1, None, [5, 10, 20, 40, 60], []),
    'ts_roc':    (1, None, [5, 10, 20, 40, 60], []),
    'ts_mean':   (1, None, [5, 10, 20, 40, 60], []),
    'ts_std':    (1, None, [5, 10, 20, 40, 60], []),
    'ts_delta':  (1, None, [5, 10, 20, 40, 60], []),
    'ts_sum':    (1, None, [5, 10, 20, 40, 60], []),
    'ts_max':    (1, None, [5, 10, 20, 40, 60], []),
    'ts_min':    (1, None, [5, 10, 20, 40, 60], []),
    'ts_skew':   (1, None, [5, 10, 20, 40, 60], []),
    'ts_kurt':   (1, None, [5, 10, 20, 40, 60], []),
    'ts_mad':    (1, None, [5, 10, 20, 40, 60], []),
    'ts_ema':    (1, None, [5, 10, 20, 40, 60], []),
    'ts_wma':    (1, None, [5, 10, 20, 40, 60], []),
    'ts_delay':  (1, None, [1, 2, 3, 5, 10], []),
    'ts_cov':    (2, None, [5, 10, 20, 40, 60], []),
    'ts_corr':   (2, None, [5, 10, 20, 40, 60], []),

    # 截面函数
    'cs_rank':   (1, None, [], []),
    'cs_zscore': (1, None, [], []),
    'cs_scale':  (1, None, [], []),

    # 数学函数
    'abs':       (1, None, [], []),
    'log':       (1, None, [], []),
    'sign':      (1, None, [], []),
    'sqrt':      (1, None, [], []),
    'square':    (1, None, [], []),
    'cube':      (1, None, [], []),
}


def _get_func_spec(func_name: str):
    """查询本地函数规格表"""
    return _FUNC_SPECS.get(func_name.lower())


# ============================================================
# 基础 AST 构造器（替代 ast.v2.spec.make_*）
# ============================================================

def _make_var(name: str) -> ast.Name:
    return ast.Name(id=name, ctx=ast.Load())


def _make_const(value) -> ast.Constant:
    return ast.Constant(value=value)


def _make_compare(left: ast.AST, op_class, right: ast.AST) -> ast.Compare:
    return ast.Compare(
        left=left,
        ops=[op_class()],
        comparators=[right],
    )


def _make_boolop(op_class, left: ast.AST, right: ast.AST) -> ast.BoolOp:
    return ast.BoolOp(op=op_class(), values=[left, right])


def _make_ifexp(test: ast.AST, body: ast.AST, orelse: ast.AST) -> ast.IfExp:
    return ast.IfExp(test=test, body=body, orelse=orelse)


def _make_unaryop(op_class, operand: ast.AST) -> ast.UnaryOp:
    return ast.UnaryOp(op=op_class(), operand=operand)


# ============================================================
# 随机终端生成
# ============================================================

def _random_variable(cfg: MutationConfig) -> ast.Name:
    rng = cfg.rng
    vw = cfg.var_weights

    if cfg.var_allowlist:
        if vw:
            choices = list(cfg.var_allowlist & set(vw.keys()))
        else:
            choices = list(cfg.var_allowlist)
        if choices:
            return _make_var(rng.choice(choices))

    if vw:
        var_names = list(vw.keys())
        var_weights = [vw[v] for v in var_names]
        return _make_var(rng.choices(var_names, weights=var_weights, k=1)[0])

    return _make_var(rng.choice(MCTS_VARIABLES))


def _random_constant(cfg: MutationConfig) -> ast.Constant:
    return _make_const(cfg.rng.choice(MCTS_CONSTANTS))


def _random_terminal(cfg: MutationConfig) -> ast.AST:
    if cfg.rng.random() < 0.85:
        return _random_variable(cfg)
    return _random_constant(cfg)


# ============================================================
# 随机比较 / 模式过滤
# ============================================================

def _random_compare(cfg: MutationConfig, left: ast.AST) -> ast.Compare:
    rng = cfg.rng
    threshold = rng.choice([0, 0, 0, 1.0, 1.5, 2.0, -1.0])
    op = rng.choice([ast.Gt, ast.Lt, ast.GtE, ast.LtE])
    return _make_compare(left, op, _make_const(threshold))


def _mode_filtered_groups(gw: dict, mode: Optional[str]) -> dict:
    if not mode or mode == 'hybrid':
        return gw
    if mode == 'continuous':
        invalid = {'comparison', 'logic', 'ternary'}
    elif mode == 'predicate':
        invalid = {'ts_function', 'cs_function', 'ta_function',
                   'feature_function', 'signal_function',
                   'math_function', 'binary_op', 'unary_op'}
    else:
        return gw
    return {k: v for k, v in gw.items() if k not in invalid}


# ============================================================
# 随机函数调用生成
# ============================================================

def _random_call(cfg: MutationConfig, depth: int, weight_key: str) -> ast.Call:
    """统一函数调用生成器（替代 v5 _random_call）

    weight_key: 'ts_weights' 或 'math_weights'
    """
    rng = cfg.rng
    weights = getattr(cfg, weight_key, None)

    if weights:
        func_names = list(weights.keys())
        func_weights = [weights[fn] for fn in func_names]
        if cfg.func_allowlist:
            filtered = [(n, w) for n, w in zip(func_names, func_weights)
                        if n in cfg.func_allowlist]
            if filtered:
                func_names, func_weights = zip(*filtered)
        func_name = rng.choices(func_names, weights=func_weights, k=1)[0]
    else:
        # fallback: 从本地规格表随机选
        func_name = rng.choice(list(_FUNC_SPECS.keys()))

    spec = _get_func_spec(func_name)
    args = _build_call_args(cfg, spec, depth, func_name)
    return ast.Call(
        func=ast.Name(id=func_name, ctx=ast.Load()),
        args=args, keywords=[],
    )


def _build_call_args(cfg: MutationConfig, spec, depth: int,
                     func_name: str) -> list:
    """根据函数规格构建参数列表"""
    rng = cfg.rng
    args = []

    if spec is None:
        # 未知函数：默认 1 个数据参数 + 1 个常数
        args.append(_grow_tree(cfg, depth - 1, prefer_variable=True))
        args.append(_make_const(rng.choice([5, 10, 20])))
        return args

    data_args, data_vars, param_pool, param_ranges = spec

    # 1. 数据参数
    if data_vars:
        for v in data_vars:
            args.append(_make_var(v))
    else:
        for _ in range(data_args):
            args.append(_grow_tree(cfg, depth - 1, prefer_variable=True))

    # 2. 离散参数: 从 param_pool 抽选
    if param_pool:
        chosen = rng.choice(param_pool)
        if isinstance(chosen, tuple):
            for p in chosen:
                args.append(_make_const(p))
        else:
            args.append(_make_const(chosen))

    # 3. 连续参数: 从 param_ranges 采样
    if param_ranges:
        for lo, hi, dtype in param_ranges:
            if dtype == 'int':
                args.append(_make_const(rng.randint(int(lo), int(hi))))
            else:
                args.append(_make_const(round(rng.uniform(lo, hi), 4)))

    return args


# ============================================================
# 递归树生长
# ============================================================

def _grow_tree(cfg: MutationConfig, depth: int,
               prefer_variable: bool = False) -> ast.AST:
    """递归生长随机 AST 树（替代 v5 _grow_tree）"""
    rng = cfg.rng
    if depth <= 1 or (prefer_variable and rng.random() < 0.7):
        return _random_terminal(cfg)

    gw = _mode_filtered_groups(cfg.group_weights, cfg.mode)
    groups = list(gw.keys())
    gweights = [gw[g] for g in groups]
    chosen = rng.choices(groups, weights=gweights, k=1)[0]

    if chosen in ('ts_function', 'cs_function', 'ta_function',
                  'feature_function', 'signal_function'):
        return _random_call(cfg, depth, 'ts_weights')
    elif chosen == 'math_function':
        return _random_call(cfg, depth, 'math_weights')
    elif chosen == 'comparison':
        return _random_compare(cfg,
                               _grow_tree(cfg, depth - 1, prefer_variable=True))
    elif chosen == 'logic':
        left = _grow_tree(cfg, depth - 1)
        right = _grow_tree(cfg, depth - 1)
        op = ast.And if rng.random() < 0.6 else ast.Or
        return _make_boolop(op, left, right)
    elif chosen == 'binary_op':
        left = _grow_tree(cfg, depth - 1, prefer_variable=True)
        right = _grow_tree(cfg, depth - 1, prefer_variable=True)
        op = rng.choice([ast.Add(), ast.Sub(), ast.Mult(), ast.Div()])
        return ast.BinOp(left=left, op=op, right=right)
    elif chosen == 'unary_op':
        operand = _grow_tree(cfg, depth - 1)
        if cfg.mode == 'continuous':
            if isinstance(operand, ast.UnaryOp) and isinstance(operand.op, ast.USub):
                return operand.operand
            return _make_unaryop(ast.USub, operand)
        elif cfg.mode == 'predicate':
            if isinstance(operand, ast.UnaryOp) and isinstance(operand.op, ast.Not):
                return operand.operand
            return _make_unaryop(ast.Not, operand)
        else:
            if rng.random() < 0.5:
                if isinstance(operand, ast.UnaryOp) and isinstance(operand.op, ast.USub):
                    return operand.operand
                return _make_unaryop(ast.USub, operand)
            if isinstance(operand, ast.UnaryOp) and isinstance(operand.op, ast.Not):
                return operand.operand
            return _make_unaryop(ast.Not, operand)
    else:  # ternary
        cond = _grow_tree(cfg, depth - 1)
        a_val = _grow_tree(cfg, depth - 1, prefer_variable=True)
        b_val = _grow_tree(cfg, depth - 1, prefer_variable=True)
        return _make_ifexp(cond, a_val, b_val)


def _random_tree(cfg: MutationConfig, max_depth: int = 6) -> ast.Expression:
    """生成完整随机表达式树"""
    rng = cfg.rng
    depth = rng.randint(2, max(2, max_depth))
    body = _grow_tree(cfg, depth)
    tree = ast.Expression(body=body)
    ast.fix_missing_locations(tree)
    return _simplify_ast(tree)


# ============================================================
# 变异算子
# ============================================================

def _mutate_subtree(cfg: MutationConfig, tree: ast.Expression,
                    max_depth: int = 4) -> ast.Expression:
    """子树替换变异

    随机选一个可替换节点 → 用新生成的随机子树替换。
    使用等权配置以避免变异强化已有方向。
    """
    rng = cfg.rng
    new_tree = copy.deepcopy(tree)
    candidates = _collect_replaceable(new_tree)
    if not candidates:
        return new_tree

    target = rng.choice(candidates)

    # 等权探索配置：所有函数权重为 1.0
    explore_cfg = MutationConfig(
        mode=cfg.mode,
        group_weights=dict(cfg.group_weights),
        ts_weights={f: 1.0 for f in cfg.ts_weights},
        math_weights={f: 1.0 for f in cfg.math_weights},
        var_weights=dict(cfg.var_weights),
        var_allowlist=cfg.var_allowlist,
        func_allowlist=cfg.func_allowlist,
        rng=cfg.rng,
    )

    replacement = _grow_tree(explore_cfg, rng.randint(1, max_depth))
    _replace_subtree(new_tree, target, replacement)
    ast.fix_missing_locations(new_tree)
    return _simplify_ast(new_tree)


def _mutate_param(cfg: MutationConfig, tree: ast.Expression,
                  max_depth: int = 4) -> ast.Expression:
    """参数变异：重新采样函数参数值"""
    rng = cfg.rng
    new_tree = copy.deepcopy(tree)

    parents = _parent_map(new_tree)
    candidates = []

    for node in _walk_nodes(new_tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
           and not isinstance(node.value, bool):
            p = parents.get(node)
            if isinstance(p, ast.Call) and isinstance(p.func, ast.Name):
                arg_idx = p.args.index(node)
                candidates.append((node, p, arg_idx))
            else:
                candidates.append((node, None, -1))

    if not candidates:
        return new_tree

    target, call_node, arg_idx = rng.choice(candidates)

    # 尝试从本地规格表读取参数约束
    if call_node is not None:
        spec = _get_func_spec(call_node.func.id)
        if spec:
            data_args, data_vars, param_pool, param_ranges = spec
            n_data = len(data_vars) if data_vars else data_args
            n_pool = 0
            if param_pool:
                sample = param_pool[0]
                n_pool = len(sample) if isinstance(sample, tuple) else 1

            pool_start = n_data
            pool_end = pool_start + n_pool

            # 窗口参数: 从 param_pool 重新采样
            if pool_start <= arg_idx < pool_end and param_pool:
                chosen = rng.choice(param_pool)
                if isinstance(chosen, tuple):
                    target.value = chosen[arg_idx - pool_start]
                else:
                    target.value = chosen
                return new_tree

            # 范围参数: 从 param_ranges 重新采样
            constraint_start = pool_end
            if arg_idx >= constraint_start and param_ranges:
                ci = arg_idx - constraint_start
                if 0 <= ci < len(param_ranges):
                    lo, hi, dtype = param_ranges[ci]
                    if dtype == 'int':
                        target.value = rng.randint(int(lo), int(hi))
                    else:
                        target.value = round(rng.uniform(lo, hi), 4)
                    return new_tree

    # fallback: 通用常数扰动
    v = target.value
    if isinstance(v, int) and not isinstance(v, bool):
        delta = rng.choice([-5, -2, -1, 1, 2, 5])
        target.value = max(1, v + delta)
    elif isinstance(v, float) and abs(v) < 0.1:
        target.value = rng.choice([0.001, 0.01, 0.02, 0.05])
    else:
        noise = rng.gauss(0, abs(v) * 0.1 + 0.01)
        target.value = round(v + noise, 4)
    return new_tree


def _mutate_logic(cfg: MutationConfig, tree: ast.Expression,
                  max_depth: int = 4) -> ast.Expression:
    """逻辑变异: and↔or, 添加/移除 not"""
    rng = cfg.rng
    new_tree = copy.deepcopy(tree)
    nodes = list(_walk_nodes(new_tree))
    bool_ops = [n for n in nodes if isinstance(n, ast.BoolOp)]
    not_ops = [n for n in nodes
               if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not)]

    if bool_ops and rng.random() < 0.5:
        target = rng.choice(bool_ops)
        target.op = ast.Or() if isinstance(target.op, ast.And) else ast.And()
    elif not_ops and rng.random() < 0.6:
        target = rng.choice(not_ops)
        _replace_subtree(new_tree, target, target.operand)
        ast.fix_missing_locations(new_tree)
    else:
        candidates = [n for n in _collect_replaceable(new_tree)
                      if isinstance(n, (ast.Compare, ast.BoolOp))]
        if candidates:
            target = rng.choice(candidates)
            not_node = _make_unaryop(ast.Not, copy.deepcopy(target))
            _replace_subtree(new_tree, target, not_node)
            ast.fix_missing_locations(new_tree)

    return new_tree


def _mutate_insert_condition(cfg: MutationConfig, tree: ast.Expression,
                             max_depth: int = 3) -> ast.Expression:
    """条件插入变异: 用 if-else 或 and/or 包装子树"""
    rng = cfg.rng
    new_tree = copy.deepcopy(tree)

    if rng.random() < 0.5:
        candidates = [n for n in _collect_replaceable(new_tree, mode='value')
                      if isinstance(n, (ast.BinOp, ast.Call))]
        if candidates:
            target = rng.choice(candidates)
            condition = _grow_tree(cfg, max_depth)
            if not isinstance(condition, (ast.Compare, ast.BoolOp)):
                condition = _make_compare(condition, ast.Gt, _make_const(0))
            ifelse = _make_ifexp(condition, copy.deepcopy(target),
                                  _make_const(0))
            _replace_subtree(new_tree, target, ifelse)
    else:
        candidates = [n for n in _collect_replaceable(new_tree, mode='bool')
                      if isinstance(n, (ast.Compare, ast.BoolOp))]
        if candidates:
            target = rng.choice(candidates)
            extra_cond = _grow_tree(cfg, max_depth)
            if not isinstance(extra_cond, (ast.Compare, ast.BoolOp)):
                extra_cond = _make_compare(extra_cond, ast.Gt, _make_const(0))
            op = ast.And if rng.random() < 0.6 else ast.Or
            combined = _make_boolop(op, copy.deepcopy(target), extra_cond)
            _replace_subtree(new_tree, target, combined)

    ast.fix_missing_locations(new_tree)
    return new_tree
