# utils/ic — 独立 IC 检验模块

## 定位

因子/择时探索的**后检验**阶段统一出口。

```
先 SR 探索 (搜索阶段 fitness = signed SR)
    ↓
后 IC 检验 (本模块: IC/ICIR/正占比/分年度/衰减)
```

## 为什么独立

| 痛点 | 解决 |
|------|------|
| 之前 IC 逻辑分散 5 处（validator / industry_fitness / llm eval / AI_yinzi_mc evaluator） | 统一到 `utils/ic`，口径一致 |
| 探索脚本各自手写 IC，容易漏训练/验证切分 | `ICValidator` 内置 0.7 切分 |
| 候选池手动逐条验证 | `validate_pool()` 批量排序 |
| 持续跟踪需要分年度/衰减 | `yearly_ic()` / `decay()` |

## 快速上手

```python
from utils.ic import ICValidator

# 1. 构造（future_returns: DataFrame 日期×标的, 或 ndarray T×N）
validator = ICValidator(
    future_returns=future_returns_df,   # 日收益 (T,N)
    forward_period=5,                    # 前瞻 5 日累积收益
    method='spearman',
    min_samples=10, min_days=30,         # 单日最少标的 / 最少有效天数
    train_ratio=0.7,                     # 前70%训练, 后30%验证
    ic_threshold=0.03, ir_threshold=1.0, # passes() 判定阈值
)

# 2. 单因子校验 → ICResult
res = validator.validate(factor_values, expression='cs_rank(ts_roc(CLOSE,20))')
print(res.ic_mean, res.icir, res.train_ic, res.valid_ic)
print(res.passes())          # 是否过 IC>0.03 且 IR>1

# 3. 候选池批量 → 排序 DataFrame
df = validator.validate_pool([f1, f2, f3], names=['A','B','C'], sort_by='icir')

# 4. 多期衰减曲线（跟踪信号持续性）
decay_df = validator.decay(f1, max_lookforward=20)

# 5. 分年度稳定性（跟踪年度稳健性）
yearly = validator.yearly_ic(f1)
```

## 与现有实现的关系

- 口径对齐 `factor/v5/validator.information_coefficient`（mean/std/ir/positive_ratio/t_stat）
- 多期前瞻对齐其 `[修复] 2026-05-20` 口径（N 期累积收益反向滚动）
- 手写 `_spearman_corr` 保证与 `AI_yinzi_mc/shared/evaluator` 的 ties 处理一致
- 现有 5 处实现**不删除**，新探索统一走本模块；后续可平滑迁移

## 纪律

- IC 是**检验**不是搜索目标：搜索阶段 fitness 用 signed SR（`MCTSFitnessCalculator`/`TimingFitness`），候选池产出后用本模块做 IC 过滤
- 通过线：`|IC| >= 0.03` 且 `|ICIR| >= 1.0`（对齐项目 2026-07-10 IC/IR 方法论）
- 择时侧检验样本口径：BUY 触发日的信号连续值 vs 后续 N 日收益（信号日收益法）
