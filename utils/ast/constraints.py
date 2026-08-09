"""
utils/ast/constraints.py — 分级约束系统（版本无关的树合法性检查）
=============================================================================

定位:
  对 Python ast.Expression 树做"合法性判断"，与 surgery.py（对树"改"）互补：
    - surgery.py      : 结构手术 —— 怎么改一棵树（子树替换/化简/签名）
    - constraints.py  : 分级约束 —— 一棵树是否合法（过滤强度可调）

设计（对齐 logging 级别语义）:
  约束级别 NONE < SYNTAX < SEMANTIC < TYPED < STRICT，运行时可切换，
  决定哪些约束器生效。低级别硬拒绝（数学确定非法），高级别软惩罚
  （特殊表达仍可进池，仅降权）——"探索自由、验证严格"哲学固化成一个旋钮。

级别定义:
  NONE     = 0    无约束：纯自由搜索（离线探索，最大化特殊表达空间）
  SYNTAX   = 10   语法层：函数白名单 / arity / 参数池（只剪数学确定非法）
  SEMANTIC = 20   语义层：恒等冗余 / 深度 / 嵌套 / 变量（剪真冗余）
  TYPED    = 30   类型层：vector/scalar 签名匹配（可选，谨慎——签名数据源注入）
  STRICT   = 40   金融语义层：领域规则（默认不启用——会剪掉特殊表达）

归属原则:
  约束器纯逻辑版本无关（只依赖 AST 结构），放本文件；
  依赖注册表的（TypeConstraint 的类型签名）通过 get_spec 注入，不内置 import v1/v2/v21。

与 surgery.py 的关系（改/判分离，零依赖）:
  - constraints.py  : 对树"判"——合法性检查（被动过滤）
  - surgery.py      : 对树"改"——子树替换/化简/签名（主动优化）
  同一模式（如 x-x→0）surgery 化简、constraints 拒绝，二者不冲突：
  约定"先简化后验证"——演化中先 _simplify_ast 去掉冗余，再交给本约束系统判断。

  **独立性约定（2026-08-09 用户确认）**:
  - 本文件与 surgery.py **零依赖、互不 import**，功能完全独立
  - 配合仅发生在应用编排层（GP/MCTS 引擎按"先改后判"顺序串联），模块内部不感知对方
  - 本文件的深度计算（_compute_depth）与 surgery._ast_depth 各自独立实现、不跨模块复用，
    保持"判"与"改"两套工具各自完备

[新增] 2026-08-08 从 utils/mcts/v1,v2/constraints.py 提升 + 分级调度封装。
  设计决策见 2026-08-08 讨论：放弃"生成时强类型硬约束"，改为可配置分级约束；
  高级别约束默认软惩罚，避免剪掉意外 alpha（如 ts_cov(SHARE, ts_max(HIGH,38),3)）。
"""

import ast as ast_module
from enum import IntEnum
from typing import Callable, Dict, List, Optional, Set, Tuple


# ============================================================
# 约束级别
# ============================================================

class ConstraintLevel(IntEnum):
    """约束过滤级别（对齐 logging 级别语义：越高过滤越严）"""
    NONE = 0      # 无约束：纯自由搜索
    SYNTAX = 10   # 语法层：白名单 / arity / 参数池
    SEMANTIC = 20 # 语义层：恒等冗余 / 深度 / 嵌套
    TYPED = 30    # 类型层：vector/scalar 签名匹配
    STRICT = 40   # 金融语义层（默认不启用）


# ============================================================
# 约束器基类
# ============================================================

class BaseConstraint:
    """约束器基类：检查一棵 AST 树是否满足某类约束

    子类需设置 level 并实现 check(tree) -> (bool, reason)。
    reason 为不通过时的简短原因（"" 表示通过）。
    """

    level: ConstraintLevel = ConstraintLevel.SYNTAX
    name: str = 'base'

    def check(self, tree: ast_module.AST) -> Tuple[bool, str]:
        raise NotImplementedError


# ============================================================
# 语法层约束（SYNTAX）—— 从 mcts CFGGrammar 提升，逻辑不变
# ============================================================

class SyntaxConstraint(BaseConstraint):
    """语法层约束：函数白名单（版本无关，函数集外部传入）

    [收敛] 2026-08-08 从 utils/mcts/v1,v2/constraints.py 的 CFGGrammar 提升，
    接口统一为 check(tree) -> (bool, reason)。
    """

    level = ConstraintLevel.SYNTAX
    name = 'syntax'

    def __init__(self, allowed_functions: Optional[Set[str]] = None):
        """
        Args:
          allowed_functions: 允许的函数名集合。None 表示不限制（仅结构合法）。
        """
        self.allowed_functions = allowed_functions

    def check(self, tree: ast_module.AST) -> Tuple[bool, str]:
        try:
            for node in ast_module.walk(tree):
                if isinstance(node, ast_module.Call):
                    func_name = self._get_func_name(node)
                    if func_name and self.allowed_functions:
                        if func_name not in self.allowed_functions:
                            return False, f"函数 '{func_name}' 不在允许列表中"
            return True, ""
        except Exception as e:
            return False, f"AST 遍历异常: {e}"

    def with_allowed_functions(self, func_set: Set[str]) -> 'SyntaxConstraint':
        """返回使用指定函数白名单的新实例"""
        return SyntaxConstraint(allowed_functions=func_set)

    @staticmethod
    def _get_func_name(call_node: ast_module.Call) -> Optional[str]:
        if isinstance(call_node.func, ast_module.Name):
            return call_node.func.id
        if isinstance(call_node.func, ast_module.Attribute):
            return call_node.func.attr
        return None


# ============================================================
# 语义层约束（SEMANTIC）—— 从 mcts SemanticValidator 提升，逻辑不变
# ============================================================

# 已知冗余嵌套模式（同函数套同函数无意义）
_REDUNDANT_NESTING: Set[str] = {
    'cs_rank',     # 排名套排名无意义
    'abs',         # abs(abs(x)) = abs(x)
    'sign',        # sign(sign(x)) = sign(x)
    'log',         # log(log(x)) 高度冗余
}


class SemanticConstraint(BaseConstraint):
    """语义层约束：剪掉"数学上确定无意义"的表达

    检查项:
      1. AST 深度上限（max_depth）
      2. 至少包含 1 个数据变量（非纯常数）
      3. 无恒等变换冗余（x+0 / x*1 / x-x / x/x）
      4. 无冗余函数嵌套（cs_rank(cs_rank)、abs(abs)）

    [收敛] 2026-08-08 从 utils/mcts/v1,v2/constraints.py 的 SemanticValidator 提升，
    接口统一为 check(tree) -> (bool, reason)。
    """

    level = ConstraintLevel.SEMANTIC
    name = 'semantic'

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
        """计算 AST 最大深度（接受任意子节点；与 surgery._ast_depth 语义互补）

        [标注] 2026-08-09 补充类型标注；与 surgery.py 的 _ast_depth 是两处独立实现
        （本方法接受任意 node，_ast_depth 处理 tree.body），保持自包含不跨模块依赖。
        """
        max_d = current_depth
        for child in ast_module.iter_child_nodes(node):
            child_d = self._compute_depth(child, current_depth + 1)
            max_d = max(max_d, child_d)
        return max_d

    def _count_variables(self, node: ast_module.AST) -> int:
        """统计 AST 中引用的数据变量数（去重，排除 Python 内置名）"""
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

    @staticmethod
    def _get_func_name(call_node: ast_module.Call) -> Optional[str]:
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


# ============================================================
# 类型层约束（TYPED）—— 签名数据源注入，版本无关
# ============================================================

class TypeConstraint(BaseConstraint):
    """类型层约束：参数个数（arity）+ 参数类型（vector/scalar/boolean）

    版本无关设计:
      - 判断逻辑只依赖 AST 结构
      - 签名数据源 get_spec(func_name) -> spec 由应用侧注入
        （通常传 utils.ast.v2.registry.FUNC_REGISTRY.get；None 表示未启用类型检查）

    检查逻辑（两级）:
      1. arity（确定性）: Call 参数个数 == data_args + 窗口参数数（param_pool 推导）
      2. 类型（签名就绪时）: 若 spec 提供 input_types，逐参数匹配

    [新增] 2026-08-08 类型层约束框架。默认 soft（应用侧决定硬/软）。
    """

    level = ConstraintLevel.TYPED
    name = 'typed'

    def __init__(self, get_spec: Optional[Callable] = None):
        """
        Args:
          get_spec: func_name(str) -> spec，提供函数规格（data_args/param_pool/input_types）。
                    None 时 arity 检查跳过（约束退化为空操作）。
        """
        self._get_spec = get_spec

    def check(self, tree: ast_module.AST) -> Tuple[bool, str]:
        if self._get_spec is None:
            return True, ""
        for node in ast_module.walk(tree):
            if not (isinstance(node, ast_module.Call) and isinstance(node.func, ast_module.Name)):
                continue
            spec = self._get_spec(node.func.id.lower())
            if spec is None:
                continue
            # 1. arity 检查：参数个数 == data_args + 窗口参数数
            n_data = getattr(spec, 'data_args', None)
            n_window = self._n_window(spec)
            if n_data is not None and len(node.args) != n_data + n_window:
                return False, (f"参数个数不符: {node.func.id}({len(node.args)} 个, "
                               f"期望 {n_data}+{n_window})")
            # 2. 类型检查：仅当 spec 提供 input_types 时启用
            input_types = getattr(spec, 'input_types', None)
            if input_types and len(input_types) == len(node.args):
                for i, (arg, want) in enumerate(zip(node.args, input_types)):
                    got = self._infer_type(arg)
                    if want is not None and got is not None and got != want:
                        return False, (f"参数类型不符: {node.func.id} 第{i+1}个参数 "
                                       f"{got} != {want}")
        return True, ""

    @staticmethod
    def _n_window(spec) -> int:
        """从 param_pool 推导窗口参数个数（对齐 mcts actions._get_func_arity）"""
        pool = getattr(spec, 'param_pool', None)
        if not pool:
            return 0
        first = pool[0]
        return len(first) if isinstance(first, (tuple, list)) else 1

    def _infer_type(self, node: ast_module.AST) -> Optional[str]:
        """推断节点输出类型（vector/scalar/boolean），None 表示未知（不判错）

        [标注] 2026-08-09 本方法为**启发式推断**，依赖项目命名约定，不可用于严格验证：
          - ast.Constant  → scalar（常数）
          - ast.Name 且全大写 → vector（项目约定全大写=数据列如 CLOSE/AMOUNT；
            注意 PI/EPSILON 这类全大写常量在本项目因子 DSL 中不出现）
          - ast.Call → 查 spec.output_type（有字段才用，宽松处理）
          未知一律返回 None（不判错）——"探索自由"哲学下宁可放行不可误杀。
        """
        if isinstance(node, ast_module.Constant):
            return 'scalar'
        if isinstance(node, ast_module.Name):
            # 启发式：全大写约定 → 数据列 → vector（见 docstring 说明）
            return 'vector' if node.id.isupper() else None
        if isinstance(node, ast_module.Call) and isinstance(node.func, ast_module.Name):
            spec = self._get_spec(node.func.id.lower()) if self._get_spec else None
            if spec is not None and hasattr(spec, 'output_type'):
                return getattr(spec, 'output_type')
            return None  # 无 output_type 字段时宽松处理
        return None


# ============================================================
# 金融语义层约束（STRICT）—— 预留位，默认不启用
# ============================================================

class FinancialSemanticConstraint(BaseConstraint):
    """金融语义约束（STRICT 级别预留位）

    [新增] 2026-08-08 框架预留，默认不启用。
    设计决策（2026-08-08 讨论）: 金融语义规则（必须含特征/窗口一致性/算子领域合理）
    属于"危险约束"——会剪掉特殊表达（如 ts_cov(SHARE, ts_max(HIGH,38),3) 这类
    意外发现的强因子）。如需使用，请在外部定义规则并显式 add 到 STRICT 级别。
    """

    level = ConstraintLevel.STRICT
    name = 'financial_semantic'

    def __init__(self, rules: Optional[List[Callable]] = None):
        """
        Args:
          rules: 规则列表，每条为 callable(tree) -> (bool, reason)。
        """
        self.rules: List[Callable] = list(rules) if rules else []

    def check(self, tree: ast_module.AST) -> Tuple[bool, str]:
        for rule in self.rules:
            ok, reason = rule(tree)
            if not ok:
                return False, reason
        return True, ""


# ============================================================
# 约束管理器 —— 按级别调度（对齐 logging logger）
# ============================================================

class ConstraintManager:
    """分级约束调度器

    核心能力（对齐 logging 语义）:
      - add(constraint, level=None): 注册约束器到某级别（默认用约束器自带 level）
      - set_level(level): 运行时切换过滤强度（像 logger.setLevel）
      - check(tree) -> (bool, reason): 只运行 level 及以下的约束器
      - penalty(tree, factor) -> float: 软惩罚系数（通过→1.0，不通过→factor）

    设计:
      - NONE 级别不运行任何约束器（纯自由搜索）
      - 低级别（SYNTAX/SEMANTIC）语义上应"硬拒绝"：check 不过 → 不评估
      - 高级别（TYPED/STRICT）语义上应"软惩罚"：penalty 折扣 → 特殊表达仍可进池
      - 硬/软由应用侧按 level 决定（见模块顶部文档示例）

    [新增] 2026-08-08 分级约束调度框架。
    """

    def __init__(self, level: ConstraintLevel = ConstraintLevel.SYNTAX):
        self.level = level
        self._registry: Dict[ConstraintLevel, List[BaseConstraint]] = {}

    def add(self, constraint: BaseConstraint,
            level: Optional[ConstraintLevel] = None) -> 'ConstraintManager':
        """注册约束器到指定级别（默认用约束器自带 level）"""
        lv = level if level is not None else constraint.level
        self._registry.setdefault(lv, []).append(constraint)
        return self

    def remove(self, name: str) -> bool:
        """按名字移除约束器（跨级别扫描）"""
        for lv in list(self._registry.keys()):
            before = len(self._registry[lv])
            self._registry[lv] = [c for c in self._registry[lv] if c.name != name]
            if len(self._registry[lv]) != before:
                if not self._registry[lv]:
                    del self._registry[lv]
                return True
        return False

    def set_level(self, level: ConstraintLevel) -> 'ConstraintManager':
        """运行时切换过滤强度（像 logger.setLevel）"""
        self.level = ConstraintLevel(level)
        return self

    @property
    def level_name(self) -> str:
        return self.level.name

    def check(self, tree: ast_module.AST) -> Tuple[bool, str]:
        """按当前级别运行约束器：level 及以下全部通过才算通过"""
        if self.level == ConstraintLevel.NONE:
            return True, ""
        for lv in sorted(ConstraintLevel):
            if lv == ConstraintLevel.NONE:
                continue
            if lv > self.level:
                break
            for c in self._registry.get(lv, []):
                ok, reason = c.check(tree)
                if not ok:
                    return False, f"[{c.name}] {reason}"
        return True, ""

    def penalty(self, tree: ast_module.AST, factor: float = 0.8) -> float:
        """软惩罚系数：通过 → 1.0；不通过 → factor（供高级别约束降权用）"""
        ok, _ = self.check(tree)
        return 1.0 if ok else factor

    def active_constraints(self) -> List[str]:
        """当前级别生效的约束器名字列表（调试用）"""
        names = []
        for lv in sorted(ConstraintLevel):
            if lv == ConstraintLevel.NONE:
                continue
            if lv > self.level:
                break
            names.extend(c.name for c in self._registry.get(lv, []))
        return names

    def __repr__(self):
        return (f"ConstraintManager(level={self.level.name}, "
                f"constraints={self.active_constraints()})")


# ============================================================
# 默认构建
# ============================================================

def default_manager(
    level: ConstraintLevel = ConstraintLevel.SYNTAX,
    allowed_functions: Optional[Set[str]] = None,
    max_depth: int = 6,
    min_variables: int = 1,
    get_spec: Optional[Callable] = None,
    strict_rules: Optional[List[Callable]] = None,
) -> ConstraintManager:
    """构建带默认约束器的管理器（应用侧可再 add 自定义约束器）

    Args:
      level: 初始级别（默认 SYNTAX）
      allowed_functions: 语法层白名单（None = 不限制）
      max_depth / min_variables: 语义层参数
      get_spec: 类型层签名数据源（None = 不启用类型约束）
      strict_rules: 金融语义层规则（None = 不启用 STRICT）

    示例:
      # 常规搜索：语法层（只剪数学非法）
      cm = default_manager(ConstraintLevel.SYNTAX, allowed_functions=func_set)

      # 收紧：语义层
      cm.set_level(ConstraintLevel.SEMANTIC)

      # 类型层（签名数据源注入后启用）
      from utils.ast.v2.registry import FUNC_REGISTRY
      cm2 = default_manager(ConstraintLevel.TYPED, get_spec=FUNC_REGISTRY.get)

      # 放风：纯自由搜索
      cm.set_level(ConstraintLevel.NONE)
    """
    cm = ConstraintManager(level)
    if allowed_functions is not None:
        cm.add(SyntaxConstraint(allowed_functions))
    cm.add(SemanticConstraint(max_depth=max_depth, min_variables=min_variables))
    if get_spec is not None:
        cm.add(TypeConstraint(get_spec))
    if strict_rules:
        cm.add(FinancialSemanticConstraint(strict_rules))
    return cm
