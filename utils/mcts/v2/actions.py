"""
core/actions.py — MCTS 搜索动作空间（7 种局部变换，v1 搬运）
=============================================================================

[搬运] 2026-08-06 从 utils/mcts/v1/actions.py 搬运，逻辑不变。
  import 路径: from .ast_utils / from .config，均为 core/ 内同级模块。
"""

import ast
import copy
import random
from typing import Optional, List, Tuple

from .ast_utils import (
    _simplify_ast, _collect_replaceable, _replace_subtree,
    _walk_nodes,
)
from .config import ActionConfig


# ============================================================
# 函数元数据
# ============================================================

def _get_func_arity(func_name: str) -> Optional[Tuple[int, int]]:
    try:
        from utils.ast.v2.registry import FUNC_REGISTRY
    except ImportError:
        return None
    spec = FUNC_REGISTRY.get(func_name.lower())
    if spec is None:
        return None
    n_data = spec.data_args
    n_window = 0
    if spec.param_pool:
        first = spec.param_pool[0]
        if isinstance(first, (tuple, list)):
            n_window = len(first)
        else:
            n_window = 1
    return (n_data, n_window)


def _get_param_candidates(func_name: str, config: ActionConfig) -> list:
    try:
        from utils.ast.v2.registry import FUNC_REGISTRY
        spec = FUNC_REGISTRY.get(func_name.lower())
        if spec and spec.param_pool:
            return spec.param_pool
    except ImportError:
        pass
    return config.param_windows


def _funcs_with_same_arity(func_name: str, allowed: set) -> List[str]:
    meta = _get_func_arity(func_name)
    if meta is None:
        return []
    return [f for f in allowed
            if f != func_name and _get_func_arity(f) == meta]


def _unary_functions(allowed: set) -> List[str]:
    return [f for f in allowed
            if (meta := _get_func_arity(f)) is not None
            and meta[0] == 1]


# ============================================================
# 动作实现（v1 搬运）
# ============================================================

def _resolve_parent_func_name(node: ast.AST, tree: ast.AST) -> Optional[str]:
    for n in _walk_nodes(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            for child in _walk_nodes(n):
                if child is node:
                    return n.func.id
    return None


def change_param(tree: ast.Expression, config: ActionConfig,
                 rng: random.Random) -> Optional[ast.Expression]:
    new_tree = copy.deepcopy(tree)
    param_nodes = []
    for node in _walk_nodes(new_tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
           and not isinstance(node.value, bool):
            param_nodes.append(node)
    if not param_nodes:
        return None
    target = rng.choice(param_nodes)
    v = target.value
    if isinstance(v, int):
        windows = None
        func_name = _resolve_parent_func_name(target, new_tree)
        if func_name:
            pools = _get_param_candidates(func_name, config)
            if pools:
                first = pools[0]
                if isinstance(first, (int, float)):
                    windows = [w for w in pools
                               if isinstance(w, (int, float)) and w != v]
                elif isinstance(first, (tuple, list)):
                    all_vals = set()
                    for t in pools:
                        if isinstance(t, (tuple, list)):
                            all_vals.update(x for x in t
                                            if isinstance(x, (int, float)))
                    windows = sorted(w for w in all_vals if w != v)
        if not windows:
            windows = [w for w in config.param_windows if w != v]
        if windows:
            target.value = rng.choice(windows)
        else:
            target.value = max(1, v + rng.choice([-5, -2, 2, 5]))
    else:
        noise = rng.gauss(0, abs(v) * 0.1 + 0.01)
        target.value = round(v + noise, 4)
    ast.fix_missing_locations(new_tree)
    return _simplify_ast(new_tree)


def change_variable(tree: ast.Expression, config: ActionConfig,
                    rng: random.Random) -> Optional[ast.Expression]:
    new_tree = copy.deepcopy(tree)
    func_name_ids = set()
    for node in _walk_nodes(new_tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_name_ids.add(id(node.func))
    candidates = [n for n in _walk_nodes(new_tree)
                  if isinstance(n, ast.Name) and id(n) not in func_name_ids
                  and n.id in config.allowed_variables]
    if not candidates:
        return None
    target = rng.choice(candidates)
    alternatives = [v for v in config.allowed_variables if v != target.id]
    if not alternatives:
        return None
    target.id = rng.choice(alternatives)
    ast.fix_missing_locations(new_tree)
    return _simplify_ast(new_tree)


def change_function(tree: ast.Expression, config: ActionConfig,
                    rng: random.Random) -> Optional[ast.Expression]:
    new_tree = copy.deepcopy(tree)
    calls = [n for n in _walk_nodes(new_tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    boolops = [n for n in _walk_nodes(new_tree)
               if isinstance(n, ast.BoolOp)]
    if not calls and not boolops:
        return None
    if calls and (not boolops or rng.random() < 0.5):
        target = rng.choice(calls)
        func_name_node = target.func
        func_name = func_name_node.id
        replacements = _funcs_with_same_arity(func_name, config.allowed_functions)
        if not replacements:
            return None
        func_name_node.id = rng.choice(replacements)
    elif boolops:
        target = rng.choice(boolops)
        target.op = ast.Or() if isinstance(target.op, ast.And) else ast.And()
    else:
        return None
    ast.fix_missing_locations(new_tree)
    return _simplify_ast(new_tree)


def wrap_function(tree: ast.Expression, config: ActionConfig,
                  rng: random.Random) -> Optional[ast.Expression]:
    new_tree = copy.deepcopy(tree)
    unary_funcs = _unary_functions(config.allowed_functions)
    if not unary_funcs:
        return None
    candidates = [n for n in _collect_replaceable(new_tree, mode='value')
                  if isinstance(n, (ast.Call, ast.Name, ast.BinOp, ast.UnaryOp))]
    if not candidates:
        return None
    target = rng.choice(candidates)
    func_name = rng.choice(unary_funcs)
    meta = _get_func_arity(func_name)
    if meta is None:
        return None
    _, n_window = meta
    args: list = [copy.deepcopy(target)]
    if n_window > 0:
        pools = _get_param_candidates(func_name, config)
        if pools and isinstance(pools[0], (int, float)):
            args.append(ast.Constant(value=rng.choice(pools)))
        elif pools and isinstance(pools[0], (tuple, list)):
            for wi in range(n_window):
                vals_at_pos = [p[wi] for p in pools
                               if isinstance(p, (tuple, list)) and len(p) > wi]
                if vals_at_pos:
                    args.append(ast.Constant(value=rng.choice(vals_at_pos)))
                else:
                    args.append(ast.Constant(value=rng.choice(config.param_windows)))
        else:
            args.append(ast.Constant(value=rng.choice(config.param_windows)))
    wrapped = ast.Call(
        func=ast.Name(id=func_name, ctx=ast.Load()),
        args=args, keywords=[],
    )
    _replace_subtree(new_tree, target, wrapped)
    ast.fix_missing_locations(new_tree)
    return _simplify_ast(new_tree)


def unwrap_function(tree: ast.Expression, _config: ActionConfig,
                    _rng: random.Random) -> Optional[ast.Expression]:
    new_tree = copy.deepcopy(tree)
    body = new_tree.body
    if not isinstance(body, ast.Call):
        return None
    if not isinstance(body.func, ast.Name):
        return None
    func_name = body.func.id
    meta = _get_func_arity(func_name)
    if meta is None or meta[0] < 1:
        return None
    if not body.args:
        return None
    new_tree.body = copy.deepcopy(body.args[0])
    ast.fix_missing_locations(new_tree)
    return _simplify_ast(new_tree)


def add_condition(tree: ast.Expression, config: ActionConfig,
                  rng: random.Random) -> Optional[ast.Expression]:
    new_tree = copy.deepcopy(tree)
    candidates = [n for n in _collect_replaceable(new_tree, mode='value')
                  if isinstance(n, (ast.BinOp, ast.Call, ast.Name))]
    if not candidates:
        return None
    target = rng.choice(candidates)
    target_copy = copy.deepcopy(target)
    window = rng.choice(config.param_windows)
    cond_type = rng.choice(['mean_gate', 'vol_gate', 'momentum_gate'])
    if cond_type == 'mean_gate':
        condition = ast.Compare(
            left=target_copy,
            ops=[ast.Gt()],
            comparators=[ast.Call(
                func=ast.Name(id='ts_mean', ctx=ast.Load()),
                args=[copy.deepcopy(target), ast.Constant(value=window)],
                keywords=[],
            )],
        )
    elif cond_type == 'vol_gate':
        condition = ast.Compare(
            left=ast.Call(
                func=ast.Name(id='ts_std', ctx=ast.Load()),
                args=[target_copy, ast.Constant(value=window)],
                keywords=[],
            ),
            ops=[ast.Gt()],
            comparators=[ast.Constant(value=0)],
        )
    else:
        short_window = rng.choice([3, 5, 10])
        condition = ast.Compare(
            left=ast.Call(
                func=ast.Name(id='ts_roc', ctx=ast.Load()),
                args=[target_copy, ast.Constant(value=short_window)],
                keywords=[],
            ),
            ops=[ast.Gt()],
            comparators=[ast.Constant(value=0)],
        )
    ifelse = ast.IfExp(
        test=condition,
        body=copy.deepcopy(target),
        orelse=ast.Constant(value=0),
    )
    _replace_subtree(new_tree, target, ifelse)
    ast.fix_missing_locations(new_tree)
    return _simplify_ast(new_tree)


def graft(tree: ast.Expression, _config: ActionConfig,
          rng: random.Random, best_pool: List) -> Optional[ast.Expression]:
    if not best_pool or len(best_pool) < 2:
        return None
    new_tree = copy.deepcopy(tree)
    for _ in range(5):
        donor = rng.choice(best_pool)
        if donor is None or donor.tree is None:
            continue
        replaceable = _collect_replaceable(new_tree, mode='any')
        if not replaceable:
            continue
        graft_point = rng.choice(replaceable)
        donor_subtrees = _collect_replaceable(donor.tree, mode='any')
        if not donor_subtrees:
            continue
        donor_subtree = copy.deepcopy(rng.choice(donor_subtrees))
        ok = _replace_subtree(new_tree, graft_point, donor_subtree)
        if ok:
            ast.fix_missing_locations(new_tree)
            return _simplify_ast(new_tree)
    return None


# ============================================================
# 动作注册表
# ============================================================

_ACTIONS = {
    'change_param': change_param,
    'change_variable': change_variable,
    'change_function': change_function,
    'wrap_function': wrap_function,
    'unwrap_function': unwrap_function,
    'add_condition': add_condition,
}
_GRAFT_ACTION = 'graft'


def get_available_actions(config: ActionConfig,
                          enable_graft: bool = False) -> List[str]:
    actions = [a for a in config.allowed_actions if a in _ACTIONS]
    if enable_graft:
        actions.append(_GRAFT_ACTION)
    return actions


def apply_action(action_name: str,
                 tree: ast.Expression,
                 config: ActionConfig,
                 rng: random.Random,
                 best_pool: Optional[List] = None) -> Optional[ast.Expression]:
    if action_name == _GRAFT_ACTION:
        if best_pool is None:
            return None
        return graft(tree, config, rng, best_pool)
    fn = _ACTIONS.get(action_name)
    if fn is None:
        return None
    return fn(tree, config, rng)
