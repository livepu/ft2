"""
utils/ic/ — 独立 IC 检验模块（标准化，供后续持续跟踪使用）
=============================================================================

定位:
  因子/择时探索的"后检验"阶段统一出口。
  方法论：先 SR 探索 → 后 IC 检验。

与 utils/gp、utils/mcts 平级；零引擎依赖，numpy/pandas/scipy 即可运行。

用法:
  >>> from utils.ic import ICValidator, compute_ic_series, ICResult
  >>> validator = ICValidator(future_returns_df, forward_period=5)
  >>> result = validator.validate(factor_values, expression='my_factor')
  >>> print(result.ic_mean, result.icir)          # IC / ICIR
  >>> df = validator.validate_pool([f1, f2])      # 候选池批量排序
  >>> decay_df = validator.decay(f1)              # 多期衰减曲线
  >>> yearly = validator.yearly_ic(f1)            # 分年度 IC

[新增] 2026-08-06 独立抽取：统一 factor/v5/validator、
  factor/v5/industry_fitness、AI_yinzi_mc/shared/evaluator 三处 IC 口径。
"""
from .validator import (
    ICValidator,
    ICResult,
    compute_ic_series,
    summarize_ics,
)

__all__ = [
    'ICValidator',
    'ICResult',
    'compute_ic_series',
    'summarize_ics',
]
