"""
utils/mcts/v2/constraints.py — 约束兼容层（收敛到 utils/ast/constraints.py）
=============================================================================

[收敛] 2026-08-09 分级约束系统统一到 utils/ast/constraints.py（版本无关，
对齐 surgery.py 定位）。本文件保留为薄壳兼容层，保证旧类名/旧 import 路径
（`from utils.mcts.v2.constraints import CFGGrammar, SemanticValidator`）不破坏。

新旧映射:
  CFGGrammar        → SyntaxConstraint   （语法层：函数白名单）
  SemanticValidator → SemanticConstraint （语义层：深度/变量/恒等冗余/嵌套）
  新增能力（本层透传）:
    ConstraintLevel / ConstraintManager / BaseConstraint / TypeConstraint /
    FinancialSemanticConstraint / default_manager —— 分级约束调度系统

推荐新用法（直接走统一入口）:
  from utils.ast.constraints import ConstraintManager, ConstraintLevel, default_manager
  cm = default_manager(level=ConstraintLevel.SYNTAX, allowed_functions=func_set)
  engine = MCTSEngine(..., constraint_mgr=cm)
"""

# 统一入口：全部约束能力来自 utils/ast/constraints.py（版本无关、零依赖）
from utils.ast.constraints import (
    ConstraintLevel,
    ConstraintManager,
    BaseConstraint,
    SyntaxConstraint,
    SemanticConstraint,
    TypeConstraint,
    FinancialSemanticConstraint,
    default_manager,
)

# 旧类名兼容（v1 提升前的名字；本质是 SyntaxConstraint / SemanticConstraint）
CFGGrammar = SyntaxConstraint
SemanticValidator = SemanticConstraint

__all__ = [
    'ConstraintLevel', 'ConstraintManager', 'BaseConstraint',
    'SyntaxConstraint', 'SemanticConstraint', 'TypeConstraint',
    'FinancialSemanticConstraint', 'default_manager',
    'CFGGrammar', 'SemanticValidator',
]
