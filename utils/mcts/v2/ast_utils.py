"""
core/ast_utils.py — AST 纯函数工具（v1 搬运，逻辑不变）
=============================================================================

[搬运] 2026-08-06 从 utils/mcts/v1/ast_utils.py 搬运。
  零外部依赖，仅 stdlib ast。
"""

import ast
import copy
from typing import List


def _expr_str(tree: ast.Expression) -> str:
    try:
        return ast.unparse(tree.body)
    except Exception:
        return '<invalid>'


def _walk_nodes(tree: ast.AST):
    yield tree
    for node in ast.walk(tree):
        yield node


def _ast_depth(node: ast.AST) -> int:
    if node is None:
        return 0
    max_d = 0
    for child in ast.iter_child_nodes(node):
        d = _ast_depth(child)
        max_d = max(max_d, d)
    return 1 + max_d


def _collect_replaceable(tree: ast.Expression, mode: str = 'any') -> list:
    func_name_ids = set()
    for node in _walk_nodes(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_name_ids.add(id(node.func))
    if mode == 'any':
        meaningful = (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
                      ast.IfExp, ast.Call, ast.Name, ast.Constant)
    elif mode == 'value':
        meaningful = (ast.BinOp, ast.UnaryOp, ast.Call, ast.Name,
                      ast.Constant, ast.IfExp)
    elif mode == 'bool':
        meaningful = (ast.BoolOp, ast.Compare, ast.UnaryOp, ast.Call)
    else:
        meaningful = (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
                      ast.IfExp, ast.Call, ast.Name, ast.Constant)
    return [n for n in _walk_nodes(tree)
            if isinstance(n, meaningful) and id(n) not in func_name_ids]


def _parent_map(tree: ast.Expression) -> dict:
    parents = {}
    for node in _walk_nodes(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _is_func_name_position(parent: ast.AST, old_node: ast.AST) -> bool:
    return isinstance(parent, ast.Call) and parent.func is old_node


def _is_int_arg_position(parent: ast.AST, old_node: ast.AST) -> bool:
    if not isinstance(parent, ast.Call):
        return False
    for i, arg in enumerate(parent.args):
        if arg is old_node and i > 0:
            if isinstance(old_node, ast.Constant) and isinstance(old_node.value, int):
                return True
    return False


def _replace_subtree(tree: ast.Expression, old_node: ast.AST,
                     new_node: ast.AST) -> bool:
    if tree.body is old_node:
        tree.body = new_node
        return True
    parents = _parent_map(tree)
    if old_node not in parents:
        return False
    parent = parents[old_node]
    if _is_func_name_position(parent, old_node):
        return False
    if _is_int_arg_position(parent, old_node):
        if not (isinstance(new_node, ast.Constant)
                and isinstance(new_node.value, int)):
            return False
    for field_name, field_value in ast.iter_fields(parent):
        if isinstance(field_value, list):
            for i, item in enumerate(field_value):
                if item is old_node:
                    field_value[i] = new_node
                    return True
        elif field_value is old_node:
            setattr(parent, field_name, new_node)
            return True
    return False


def _nodes_equal(a: ast.AST, b: ast.AST) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, ast.Constant):
        return a.value == b.value
    if isinstance(a, ast.Name):
        return a.id == b.id
    if isinstance(a, ast.BinOp):
        return (type(a.op) is type(b.op)
                and _nodes_equal(a.left, b.left)
                and _nodes_equal(a.right, b.right))
    if isinstance(a, ast.UnaryOp):
        return (type(a.op) is type(b.op)
                and _nodes_equal(a.operand, b.operand))
    if isinstance(a, ast.BoolOp):
        return (type(a.op) is type(b.op)
                and all(_nodes_equal(x, y)
                        for x, y in zip(a.values, b.values)))
    if isinstance(a, ast.Compare):
        if len(a.ops) != len(b.ops):
            return False
        return (type(a.ops[0]) is type(b.ops[0])
                and _nodes_equal(a.left, b.left)
                and all(_nodes_equal(x, y)
                        for x, y in zip(a.comparators, b.comparators)))
    return ast.dump(a) == ast.dump(b)


def _simplify_ast(tree: ast.Expression) -> ast.Expression:
    """后处理简化 AST: neg(neg(x))→x, x*1→x, x+0→x, x-x→0, x/x→1"""

    def _walk(node):
        if node is None:
            return None
        for child in ast.iter_child_nodes(node):
            walk_result = _walk(child)
            for field_name, field_value in ast.iter_fields(node):
                if isinstance(field_value, list):
                    for i, item in enumerate(field_value):
                        if item is child and walk_result is not None:
                            field_value[i] = walk_result
                elif field_value is child and walk_result is not None:
                    setattr(node, field_name, walk_result)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            if isinstance(node.operand, ast.UnaryOp) and isinstance(node.operand.op, ast.USub):
                return node.operand.operand
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            if isinstance(node.operand, ast.UnaryOp) and isinstance(node.operand.op, ast.Not):
                return node.operand.operand
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'cos':
            if node.args and isinstance(node.args[0], ast.UnaryOp) and isinstance(node.args[0].op, ast.USub):
                node.args[0] = node.args[0].operand
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            if isinstance(node.right, ast.Constant) and node.right.value == 1:
                return node.left
            if isinstance(node.left, ast.Constant) and node.left.value == 1:
                return node.right
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                return node.left
            if isinstance(node.left, ast.Constant) and node.left.value == 0:
                return node.right
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                return node.left
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if isinstance(node.right, ast.Constant) and node.right.value == 1:
                return node.left
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
            if _nodes_equal(node.left, node.right):
                return ast.Constant(value=0.0)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if _nodes_equal(node.left, node.right):
                return ast.Constant(value=1.0)
        return node

    tree.body = _walk(tree.body)
    ast.fix_missing_locations(tree)
    return tree


def _canonicalize_key(tree: ast.Expression, expr_str: str = None) -> str:
    if expr_str is None:
        expr_str = _expr_str(tree)

    def _canonicalize(node):
        for field_name, field_value in ast.iter_fields(node):
            if isinstance(field_value, list):
                new_list = []
                for item in field_value:
                    if isinstance(item, ast.AST):
                        new_list.append(_canonicalize(item))
                    else:
                        new_list.append(item)
                setattr(node, field_name, new_list)
            elif isinstance(field_value, ast.AST):
                setattr(node, field_name, _canonicalize(field_value))
        if isinstance(node, ast.BinOp):
            if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
                try:
                    lv, rv = node.left.value, node.right.value
                    if isinstance(node.op, ast.Add):
                        return ast.Constant(value=lv + rv)
                    elif isinstance(node.op, ast.Sub):
                        return ast.Constant(value=lv - rv)
                    elif isinstance(node.op, ast.Mult):
                        return ast.Constant(value=lv * rv)
                    elif isinstance(node.op, ast.Div) and rv != 0:
                        return ast.Constant(value=lv / rv)
                except Exception:
                    pass
            if isinstance(node.op, (ast.Add, ast.Mult)):
                left_str = ast.unparse(node.left)
                right_str = ast.unparse(node.right)
                if right_str < left_str:
                    node.left, node.right = node.right, node.left
        return node

    new_tree = copy.deepcopy(tree)
    new_tree.body = _canonicalize(new_tree.body)
    ast.fix_missing_locations(new_tree)
    return _expr_str(new_tree)
