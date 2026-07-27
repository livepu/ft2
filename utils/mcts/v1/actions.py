"""
utils/mcts/v1/actions.py — MCTS 因子动作空间（7 种局部变换）

设计哲学:
  MCTS 的每一步是小幅度、可归因的局部变换，不是 GP 式的随机变异。
  每个动作只改变因子的一个维度（参数/变量/函数/结构），让 UCB 能追踪
  "哪个维度的变换带来了收益"。

动作清单:
  change_param     — 改窗口/常数参数
  change_variable  — 换变量
  change_function  — 换函数（含逻辑算子 and↔or）
  wrap_function    — 外包一层函数
  unwrap_function  — 去掉外层函数
  add_condition    — 加条件门控
  graft            — 嫁接最优池子树（需要 best_pool 参数）

依赖: 仅 stdlib ast + 本地 ast_utils / config
"""

import ast
import copy
import random
from typing import Optional, List, Dict, Tuple

from .ast_utils import (
    _simplify_ast, _collect_replaceable, _replace_subtree,
    _parent_map, _walk_nodes,
)
from .config import ActionConfig


# ============================================================
# 函数元数据（元数 + 是否需要窗口参数）
# ============================================================
# (n_data_args, n_window_params)
# n_data_args: 数据参数个数（子树/变量）
# n_window_params: 窗口参数个数（整数）

_FUNC_META: Dict[str, Tuple[int, int]] = {
    # 时序（1 数据 + 1 窗口）
    'ts_rank': (1, 1), 'ts_mean': (1, 1), 'ts_std': (1, 1),
    'ts_roc': (1, 1), 'ts_delta': (1, 1), 'ts_sum': (1, 1),
    'ts_max': (1, 1), 'ts_min': (1, 1), 'ts_skew': (1, 1),
    'ts_kurt': (1, 1), 'ts_mad': (1, 1), 'ts_ema': (1, 1),
    'ts_wma': (1, 1), 'ts_delay': (1, 1),
    # 时序成对（2 数据 + 1 窗口）
    'ts_cov': (2, 1), 'ts_corr': (2, 1),
    # 截面（1 数据，无窗口）
    'cs_rank': (1, 0), 'cs_zscore': (1, 0), 'cs_scale': (1, 0),
    # 数学（1 数据，无窗口）
    'abs': (1, 0), 'log': (1, 0), 'sign': (1, 0),
    'sqrt': (1, 0), 'square': (1, 0), 'cube': (1, 0),
}


def _get_func_name(call: ast.Call) -> Optional[str]:
    """从 Call 节点提取函数名"""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _get_func_arity(func_name: str) -> Optional[Tuple[int, int]]:
    """查询函数元数 (n_data_args, n_window_params)"""
    return _FUNC_META.get(func_name.lower())


def _funcs_with_same_arity(func_name: str,
                           allowed: set) -> List[str]:
    """找出元数相同的函数（用于 change_function）"""
    meta = _get_func_arity(func_name)
    if meta is None:
        return []
    return [f for f in allowed
            if f != func_name
            and _get_func_arity(f) == meta]


def _unary_functions(allowed: set) -> List[str]:
    """找出一元函数（1 数据参数），用于 wrap_function"""
    return [f for f in allowed
            if _get_func_arity(f) is not None
            and _get_func_arity(f)[0] == 1]


# ============================================================
# 动作 1: change_param — 改窗口/常数参数
# ============================================================

def change_param(tree: ast.Expression, config: ActionConfig,
                 rng: random.Random) -> Optional[ast.Expression]:
    """改一个参数值（窗口或常数）

    策略:
      - 整数参数（窗口）: 从 config.param_windows 选另一个值
      - 浮点参数: 高斯扰动
    """
    new_tree = copy.deepcopy(tree)
    candidates = []

    for node in _walk_nodes(new_tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
           and not isinstance(node.value, bool):
            candidates.append(node)

    if not candidates:
        return None

    target = rng.choice(candidates)
    v = target.value

    if isinstance(v, int):
        # 窗口参数: 从可选值中选一个不同的
        windows = [w for w in config.param_windows if w != v]
        if windows:
            target.value = rng.choice(windows)
        else:
            target.value = max(1, v + rng.choice([-5, -2, 2, 5]))
    else:
        # 浮点参数: 高斯扰动
        noise = rng.gauss(0, abs(v) * 0.1 + 0.01)
        target.value = round(v + noise, 4)

    ast.fix_missing_locations(new_tree)
    return _simplify_ast(new_tree)


# ============================================================
# 动作 2: change_variable — 换变量
# ============================================================

def change_variable(tree: ast.Expression, config: ActionConfig,
                    rng: random.Random) -> Optional[ast.Expression]:
    """替换一个变量为另一个允许的变量"""
    new_tree = copy.deepcopy(tree)

    # 收集所有 Name 节点（排除函数名位置）
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


# ============================================================
# 动作 3: change_function — 换函数（含逻辑算子）
# ============================================================

def change_function(tree: ast.Expression, config: ActionConfig,
                    rng: random.Random) -> Optional[ast.Expression]:
    """替换一个函数调用为同元数的另一个函数

    也处理 BoolOp 的 and↔or 翻转。
    """
    new_tree = copy.deepcopy(tree)

    # 收集所有 Call 节点
    calls = [n for n in _walk_nodes(new_tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]

    # 收集所有 BoolOp 节点
    boolops = [n for n in _walk_nodes(new_tree)
               if isinstance(n, ast.BoolOp)]

    if not calls and not boolops:
        return None

    # 50% 概率改 Call，50% 改 BoolOp（如果都有）
    if calls and (not boolops or rng.random() < 0.5):
        target = rng.choice(calls)
        func_name = target.func.id
        replacements = _funcs_with_same_arity(func_name, config.allowed_functions)
        if not replacements:
            return None
        target.func.id = rng.choice(replacements)
    elif boolops:
        target = rng.choice(boolops)
        target.op = ast.Or() if isinstance(target.op, ast.And) else ast.And()
    else:
        return None

    ast.fix_missing_locations(new_tree)
    return _simplify_ast(new_tree)


# ============================================================
# 动作 4: wrap_function — 外包一层函数
# ============================================================

def wrap_function(tree: ast.Expression, config: ActionConfig,
                  rng: random.Random) -> Optional[ast.Expression]:
    """在某个子树外包一层一元函数

    如 ts_roc(CLOSE,20) → cs_rank(ts_roc(CLOSE,20))
    """
    new_tree = copy.deepcopy(tree)

    unary_funcs = _unary_functions(config.allowed_functions)
    if not unary_funcs:
        return None

    # 选一个可替换的值子树
    candidates = [n for n in _collect_replaceable(new_tree, mode='value')
                  if isinstance(n, (ast.Call, ast.Name, ast.BinOp, ast.UnaryOp))]
    if not candidates:
        return None

    target = rng.choice(candidates)
    func_name = rng.choice(unary_funcs)
    n_data, n_window = _get_func_arity(func_name)

    # 构建新的 Call 节点
    args = [copy.deepcopy(target)]
    if n_window > 0:
        args.append(ast.Constant(value=rng.choice(config.param_windows)))

    wrapped = ast.Call(
        func=ast.Name(id=func_name, ctx=ast.Load()),
        args=args, keywords=[],
    )

    _replace_subtree(new_tree, target, wrapped)
    ast.fix_missing_locations(new_tree)
    return _simplify_ast(new_tree)


# ============================================================
# 动作 5: unwrap_function — 去掉外层函数
# ============================================================

def unwrap_function(tree: ast.Expression, config: ActionConfig,
                    rng: random.Random) -> Optional[ast.Expression]:
    """去掉最外层的函数调用，暴露其第一个数据参数

    如 cs_rank(ts_roc(CLOSE,20)) → ts_roc(CLOSE,20)
    """
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

    # 用第一个数据参数替换整个树
    if not body.args:
        return None

    new_tree.body = copy.deepcopy(body.args[0])
    ast.fix_missing_locations(new_tree)
    return _simplify_ast(new_tree)


# ============================================================
# 动作 6: add_condition — 加条件门控
# ============================================================

def add_condition(tree: ast.Expression, config: ActionConfig,
                  rng: random.Random) -> Optional[ast.Expression]:
    """用 IfExp 包裹一个值子树

    改进: 用 ts_quantile 类的分位数阈值，而不是固定常数。
    阈值从因子自身的分位数中选，确保条件真的会触发。

    三种条件类型:
      1. 因子值大于自身均值: x > ts_mean(x, window)
      2. 波动率门控: ts_std(x, window) > ts_median(ts_std(x, window), long_window)
      3. 动量门控: ts_roc(x, short) > 0
    """
    new_tree = copy.deepcopy(tree)

    candidates = [n for n in _collect_replaceable(new_tree, mode='value')
                  if isinstance(n, (ast.BinOp, ast.Call, ast.Name))]
    if not candidates:
        return None

    target = rng.choice(candidates)
    target_copy = copy.deepcopy(target)
    window = rng.choice(config.param_windows)

    # 三种条件类型随机选
    cond_type = rng.choice(['mean_gate', 'vol_gate', 'momentum_gate'])

    if cond_type == 'mean_gate':
        # x > ts_mean(x, window) — 因子值高于近期均值时启用
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
        # ts_std(x, window) > 0 — 波动率非零时启用（简化版）
        condition = ast.Compare(
            left=ast.Call(
                func=ast.Name(id='ts_std', ctx=ast.Load()),
                args=[target_copy, ast.Constant(value=window)],
                keywords=[],
            ),
            ops=[ast.Gt()],
            comparators=[ast.Constant(value=0)],
        )
    else:  # momentum_gate
        # ts_roc(x, short_window) > 0 — 因子值上升时启用
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


# ============================================================
# 动作 7: graft — 嫁接最优池子树
# ============================================================

def graft(tree: ast.Expression, config: ActionConfig,
          rng: random.Random,
          best_pool: List) -> Optional[ast.Expression]:
    """从最优池取子树嫁接到当前树

    Args:
      best_pool: MCTSNode 列表（全局最优因子池）
    """
    if not best_pool or len(best_pool) < 2:
        return None

    new_tree = copy.deepcopy(tree)

    for _ in range(5):  # 最多尝试 5 次
        donor = rng.choice(best_pool)
        if donor is None or donor.tree is None:
            continue

        # 从当前树选一个可替换位置
        replaceable = _collect_replaceable(new_tree, mode='any')
        if not replaceable:
            continue
        graft_point = rng.choice(replaceable)

        # 从捐赠者选一个子树
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

# 普通动作（不需要 best_pool）
_ACTIONS = {
    'change_param': change_param,
    'change_variable': change_variable,
    'change_function': change_function,
    'wrap_function': wrap_function,
    'unwrap_function': unwrap_function,
    'add_condition': add_condition,
}

# graft 需要额外参数，单独处理
_GRAFT_ACTION = 'graft'


def get_available_actions(config: ActionConfig,
                          enable_graft: bool = False) -> List[str]:
    """获取当前可用的动作列表"""
    actions = [a for a in config.allowed_actions if a in _ACTIONS]
    if enable_graft:
        actions.append(_GRAFT_ACTION)
    return actions


def apply_action(action_name: str,
                 tree: ast.Expression,
                 config: ActionConfig,
                 rng: random.Random,
                 best_pool: List = None) -> Optional[ast.Expression]:
    """执行指定动作

    Args:
      action_name: 动作名称
      tree: 当前 AST 树
      config: 动作配置
      rng: 随机数生成器
      best_pool: 最优池（仅 graft 需要）

    Returns:
      变换后的新 AST 树，或 None（动作失败）
    """
    if action_name == _GRAFT_ACTION:
        if best_pool is None:
            return None
        return graft(tree, config, rng, best_pool)

    fn = _ACTIONS.get(action_name)
    if fn is None:
        return None
    return fn(tree, config, rng)
