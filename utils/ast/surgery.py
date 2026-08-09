"""
utils/ast/surgery.py — AST 手术层（版本无关的树编辑工具）
=============================================================================

定位:
  对 Python ast.Expression 树做"局部手术"（子树替换/化简/签名/提取）。
  与 utils/ast/v1,v2,v21 的"语言定义"（解析/求值/注册表）正交:
    - 语言定义 = 表达式是什么意思、值是多少（跟版本走）
    - 手术层   = 怎么改一棵树（跟版本无关，只依赖 stdlib ast + copy）

服务对象:
  - GP v5/v6 : 变异算子 _mutate_subtree 依赖 _collect_replaceable/_replace_subtree/_simplify_ast
  - MCTS v2  : 7 种搜索动作依赖 _collect_replaceable/_replace_subtree/_simplify_ast/_canonicalize_key

与 constraints.py 的关系（改/判分离，零依赖）:
  - surgery.py      : 对树"改"——子树替换/化简/签名/提取（主动优化）
  - constraints.py  : 对树"判"——合法性检查（被动过滤）
  同一模式（如 x-x→0）surgery 化简、constraints 拒绝，二者不冲突：
  约定"先简化后验证"——演化中先 _simplify_ast 去掉冗余，再交给约束系统判断。

  **独立性约定（2026-08-09 用户确认）**:
  - 本文件与 constraints.py **零依赖、互不 import**，功能完全独立
  - 配合仅发生在应用编排层（GP/MCTS 引擎按"先改后判"顺序串联），模块内部不感知对方
  - 未来若需复用（如约束层借深度计算），方向只能是 constraints → surgery（单向，干净）

参数命名约定（本文件与 constraints.py 统一遵循，2026-08-09）:
  tree          = 完整表达式树（ast.Expression）
  node          = 任意 AST 节点（子树）
  old_node / new_node = 替换操作的旧/新子树
  parent        = 定位用的父节点
  a / b         = 比较操作的两个操作数（Python 惯例）
  各函数参数名自描述语义，独立纯函数不依赖跨函数命名贯通。

收敛来源:
  [收敛] 2026-08-07 从 utils/gp/v5/ast_utils.py + utils/mcts/v2/ast_utils.py 合并为唯一真源。
  原两份拷贝核心手术函数逻辑一致（GP 版为基），本文件统一提供后删除原拷贝。
  - _walk_nodes/_ast_depth 内联实现，语义对齐 utils.ast.v2.dsl.walk_nodes/ast_depth
    （不依赖 v2.dsl，保证对 v1/v2/v21 版本无关；不含 Expression 容器、不重复根节点）
  - _canonicalize_key 保留 GP 版 memo+lock 缓存参数（MCTS 单线程调用传 None 即无缓存）
  - _extract_subtrees 为 GP Motif 库专属（MCTS 暂不需要，但收敛后可用）
"""

import ast
import copy
from typing import List


# ============================================================
# AST 遍历 / 深度（内联，语义对齐 utils.ast.v2.dsl）
# ============================================================

def _walk_nodes(tree: ast.AST) -> list:
    """安全遍历 AST 所有节点，返回节点列表（不含 Expression/Module 容器本身）

    语义对齐 utils.ast.v2.dsl.walk_nodes:
      - ast.Expression 容器本身不遍历，直接遍历 body
      - ast.Module 逐 statement 遍历
      - 不重复任何节点

    [标注] 2026-08-09 补充返回类型标注 -> list（实现返回 list，标注对齐）。
    """
    if isinstance(tree, ast.Expression):
        return list(ast.walk(tree.body))
    if isinstance(tree, ast.Module):
        nodes = []
        for stmt in tree.body:
            nodes.extend(ast.walk(stmt))
        return nodes
    return list(ast.walk(tree))


def _ast_depth(tree: ast.AST) -> int:
    """计算 AST 最大深度（语义对齐 utils.ast.v2.dsl.ast_depth）

    [标注] 2026-08-09 优化后本函数在当前文件内无内部调用（_extract_subtrees 已改
    一次后序遍历），但保留为手术层的公共深度工具——对齐 v2.dsl.ast_depth 语义，
    供外部/未来复用（如约束层深度计算收敛），不删除。
    """
    def _depth(node):
        children = list(ast.iter_child_nodes(node))
        if not children:
            return 1
        return 1 + max(_depth(c) for c in children)
    body = tree.body if hasattr(tree, 'body') else tree
    return _depth(body)


# ============================================================
# AST 工具函数
# ============================================================

def _expr_str(tree: ast.Expression) -> str:
    try:
        return ast.unparse(tree.body)
    except Exception:
        return '<invalid>'


def _collect_func_name_ids(tree: ast.Expression) -> set:
    """收集所有 Call.func 位置的 Name 节点 id（函数名不是可替换子树）

    [重构] 2026-08-09 从 _collect_replaceable / _extract_subtrees 抽出的公共逻辑，
    消除重复实现。
    """
    ids = set()
    for node in _walk_nodes(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            ids.add(id(node.func))
    return ids


def _collect_replaceable(tree: ast.Expression, mode: str = 'any') -> list:
    """收集可替换的语义子树节点

    自动排除：
    - Load/Store 等元信息节点
    - Call.func 位置的 Name 节点（函数名不是子树）

    mode:
      'any'      — 所有语义节点
      'value'    — 产生数值的子树
      'bool'     — 产生布尔值的子树
    """
    func_names = _collect_func_name_ids(tree)

    if mode == 'any':
        meaningful = (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
                      ast.IfExp, ast.Call, ast.Name, ast.Constant)
    elif mode == 'value':
        meaningful = (ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Constant, ast.IfExp)
    elif mode == 'bool':
        meaningful = (ast.BoolOp, ast.Compare, ast.UnaryOp, ast.Call)
    else:
        meaningful = (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
                      ast.IfExp, ast.Call, ast.Name, ast.Constant)

    return [n for n in _walk_nodes(tree)
            if isinstance(n, meaningful) and id(n) not in func_names]


def _parent_map(tree: ast.Expression) -> dict:
    parents = {}
    for node in _walk_nodes(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _is_func_name_position(parent: ast.AST, old_node: ast.AST) -> bool:
    """检查 old_node 是否在 Call.func 位置（函数名）"""
    return isinstance(parent, ast.Call) and parent.func is old_node


def _is_int_arg_position(parent: ast.AST, old_node: ast.AST) -> bool:
    """检查 old_node 是否在父节点的整数参数位（如 ts_rank(x, 20) 中的 20）"""
    if not isinstance(parent, ast.Call):
        return False
    for i, arg in enumerate(parent.args):
        if arg is old_node and i > 0:
            if isinstance(old_node, ast.Constant) and isinstance(old_node.value, int):
                return True
    return False


def _replace_subtree(tree: ast.Expression, old_node: ast.AST, new_node: ast.AST) -> bool:
    """将 tree 中的 old_node 替换为 new_node

    安全检查：
    - 不允许替换 Call.func 位置的节点
    - 不允许将非整数子树插入函数的整数参数位
    """
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
        if not (isinstance(new_node, ast.Constant) and isinstance(new_node.value, int)):
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


# ============================================================
# AST 轻量简化
# ============================================================

def _nodes_equal(a: ast.AST, b: ast.AST) -> bool:
    """快速判断两个 AST 子树是否结构相同（比 ast.unparse 字符串化快很多）

    [新增] 2026-07-08 用于 _simplify_ast 中的 x-x / x/x 恒等式检查。
    """
    if type(a) is not type(b):
        return False
    if isinstance(a, ast.Constant):
        return a.value == b.value
    if isinstance(a, ast.Name):
        return a.id == b.id
    if isinstance(a, ast.BinOp):
        return type(a.op) is type(b.op) and _nodes_equal(a.left, b.left) and _nodes_equal(a.right, b.right)
    if isinstance(a, ast.UnaryOp):
        return type(a.op) is type(b.op) and _nodes_equal(a.operand, b.operand)
    if isinstance(a, ast.BoolOp):
        return type(a.op) is type(b.op) and all(_nodes_equal(x, y) for x, y in zip(a.values, b.values))
    if isinstance(a, ast.Compare):
        if len(a.ops) != len(b.ops) or len(a.comparators) != len(b.comparators):
            return False
        # [修复] 2026-08-09 原实现只比较 ops[0]，多操作符比较链（如 a>b<c 的
        # ops=[Gt,Lt]）在 ops[1:] 不同时会误判相等，改为逐操作符类型比较。
        return (all(type(o1) is type(o2) for o1, o2 in zip(a.ops, b.ops)) and
                _nodes_equal(a.left, b.left) and
                all(_nodes_equal(x, y) for x, y in zip(a.comparators, b.comparators)))
    # fallback: 用 ast.dump 兜底（比 unparse 快但比结构比较慢）
    return ast.dump(a) == ast.dump(b)


def _simplify_ast(tree: ast.Expression) -> ast.Expression:
    """后处理简化 AST，消除双重否定和恒等运算。

    在随机生成/变异/交叉后调用，节省节点数并提升可读性。
    不改变语义，只做结构简化。
    """
    def _walk(node):
        if node is None:
            return None
        for child in ast.iter_child_nodes(node):
            _walk_child = _walk(child)
            for field_name, field_value in ast.iter_fields(node):
                if isinstance(field_value, list):
                    for i, item in enumerate(field_value):
                        if item is child and _walk_child is not None:
                            field_value[i] = _walk_child
                elif field_value is child and _walk_child is not None:
                    setattr(node, field_name, _walk_child)

        # neg(neg(x)) → x
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            if isinstance(node.operand, ast.UnaryOp) and isinstance(node.operand.op, ast.USub):
                return node.operand.operand
        # not(not(x)) → x
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            if isinstance(node.operand, ast.UnaryOp) and isinstance(node.operand.op, ast.Not):
                return node.operand.operand
        # cos(neg(x)) → cos(x)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'cos':
            if node.args and isinstance(node.args[0], ast.UnaryOp) and isinstance(node.args[0].op, ast.USub):
                node.args[0] = node.args[0].operand
        # x * 1 → x, 1 * x → x
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            if isinstance(node.right, ast.Constant) and node.right.value == 1:
                return node.left
            if isinstance(node.left, ast.Constant) and node.left.value == 1:
                return node.right
        # x + 0 → x, 0 + x → x
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                return node.left
            if isinstance(node.left, ast.Constant) and node.left.value == 0:
                return node.right
        # x - 0 → x
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                return node.left
        # x / 1 → x
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if isinstance(node.right, ast.Constant) and node.right.value == 1:
                return node.left
        # x - x → 0
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
            if _nodes_equal(node.left, node.right):
                return ast.Constant(value=0.0)
        # x / x → 1
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if _nodes_equal(node.left, node.right):
                return ast.Constant(value=1.0)
        return node

    tree.body = _walk(tree.body)
    ast.fix_missing_locations(tree)
    return tree


# ============================================================
# AST 规范化（用于缓存 key 语义去重）
# ============================================================

def _canonicalize_key(tree: ast.Expression,
                      expr_str: str = None,
                      memo: dict = None,
                      lock=None) -> str:
    """生成规范化的缓存 key 字符串。

    安全规则:
      - Add/Mult 交换律排序（按子树字符串字典序）
      - 纯常数折叠（1+2→3 等）
      - 不处理非交换函数参数（如 ts_corr(a,b) ≠ ts_corr(b,a)）
    """
    if expr_str is None:
        expr_str = _expr_str(tree)

    if memo is not None:
        if lock is not None:
            with lock:
                if expr_str in memo:
                    return memo[expr_str]
        else:
            if expr_str in memo:
                return memo[expr_str]

    # [优化] 2026-08-09 子树签名缓存：每节点 canonical 后 unparse 一次并复用，
    # 避免交换律排序时对 Add/Mult 左右子树重复 unparse 导致的 O(n²) 开销。
    # 排序比较的字符串不变，canonical key 输出与原实现完全一致。
    sig_memo: dict = {}  # id(node) -> 子树 canonical 后的 unparse 字符串

    def _record(node: ast.AST) -> ast.AST:
        """记录节点签名并原样返回（常数折叠产生的新节点也记录）"""
        sig_memo[id(node)] = ast.unparse(node)
        return node

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

        # 纯常数折叠
        if isinstance(node, ast.BinOp):
            if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
                try:
                    l, r = node.left.value, node.right.value
                    if isinstance(node.op, ast.Add):
                        return _record(ast.Constant(value=l + r))
                    elif isinstance(node.op, ast.Sub):
                        return _record(ast.Constant(value=l - r))
                    elif isinstance(node.op, ast.Mult):
                        return _record(ast.Constant(value=l * r))
                    elif isinstance(node.op, ast.Div) and r != 0:
                        return _record(ast.Constant(value=l / r))
                except Exception:
                    pass

            # 交换律排序：Add/Mult 按子树签名排序（子节点已先 canonicalize 并记录）
            if isinstance(node.op, (ast.Add, ast.Mult)):
                left_sig = sig_memo.get(id(node.left))
                right_sig = sig_memo.get(id(node.right))
                if left_sig is None:
                    left_sig = ast.unparse(node.left)
                if right_sig is None:
                    right_sig = ast.unparse(node.right)
                if right_sig < left_sig:
                    node.left, node.right = node.right, node.left

        return _record(node)

    new_tree = copy.deepcopy(tree)
    new_tree.body = _canonicalize(new_tree.body)
    ast.fix_missing_locations(new_tree)
    key = _expr_str(new_tree)

    if memo is not None:
        if lock is not None:
            with lock:
                memo[expr_str] = key
        else:
            memo[expr_str] = key
    return key


def _extract_subtrees(tree: ast.Expression,
                       min_depth: int = 1,
                       max_depth: int = 3) -> List[ast.AST]:
    """提取所有深度在 [min_depth, max_depth] 范围内的有效子树

    [新增] 2026-07-08 用于 Motif 库构建：从高 fitness 个体中提取有潜力的子结构。
    排除：纯函数名节点、Load/Store 元节点、单变量/常数节点。
    [优化] 2026-08-09 深度计算改为一次后序遍历（O(n)），替代原先对每个节点
    重复调用 _ast_depth 的 O(n²) 实现；深度语义不变（子树高度）。
    """
    func_names = _collect_func_name_ids(tree)

    meaningful = (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
                  ast.IfExp, ast.Call)

    subtrees = []

    def _walk(node: ast.AST) -> int:
        """后序遍历：返回以 node 为根的子树深度，同时收集深度范围内的子树"""
        children = list(ast.iter_child_nodes(node))
        depth = 1 + max((_walk(c) for c in children), default=0)
        if isinstance(node, meaningful) and id(node) not in func_names:
            if min_depth <= depth <= max_depth:
                subtrees.append(node)
        return depth

    body = tree.body if hasattr(tree, 'body') else tree
    _walk(body)
    return subtrees
