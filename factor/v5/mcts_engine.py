"""
factor/v5/mcts_engine.py — 因子 MCTS 引擎 (wrapper)
=============================================================================

对标 factor/v5/gp_engine.py: 核心搜索算法在 utils/mcts/v1/，
本文件只负责注入因子端的 evaluator (_ExpressionFromAST)。

用法:
  >>> from factor.v5.mcts_engine import MCTSEngine
  >>> engine = MCTSEngine(data=data_dict, fitness_calculator=calc, ...)
"""
from utils.mcts.v1.engine import MCTSEngine as _BaseMCTSEngine
from utils.mcts.v1.config import ActionConfig
from .expression import _ExpressionFromAST


class MCTSEngine(_BaseMCTSEngine):
    """因子端 MCTS 引擎 — 注入 _ExpressionFromAST evaluator"""

    def __init__(self, *args, **kwargs):
        # auto-inject factor evaluator (can be overridden)
        if 'evaluator' not in kwargs:
            kwargs['evaluator'] = lambda data, tree: _ExpressionFromAST(tree).evaluate(data)
        super().__init__(*args, **kwargs)


# 重新导出 (保持 API 兼容)
__all__ = ['MCTSEngine', 'ActionConfig', '_ExpressionFromAST']
