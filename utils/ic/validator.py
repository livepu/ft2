"""
utils/ic/validator.py — 独立 IC 检验模块（标准化，供后续持续跟踪）
=============================================================================

定位:
  因子/择时探索的"后检验"阶段统一出口。
  方法论：先 SR 探索 → 后 IC 检验（本模块）。

设计原则:
  - 零引擎依赖：仅 numpy/pandas/scipy，因子侧(panel)与择时侧(状态序列)通用
  - 输入统一为 ndarray (T, N)：因子值 × 未来收益，逐日截面相关
  - 与 factor/v5/validator.FactorValidator 输出对齐（mean/std/ir/positive_ratio/t_stat）

[新增] 2026-08-06 独立抽取：参考 factor/v5/validator.information_coefficient、
  factor/v5/industry_fitness._compute_daily_ics、AI_yinzi_mc/shared/evaluator.ICFitness
  三处实现的共通口径，统一标准化，避免各探索脚本各写一套。
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, field
from scipy import stats


# ============================================================
# 数据结构
# ============================================================

@dataclass
class ICResult:
    """单次 IC 检验结果（对齐 FactorValidator.information_coefficient 输出）"""
    ic_mean: float = np.nan
    ic_std: float = np.nan
    icir: float = np.nan          # IC 均值 / IC 标准差
    positive_ratio: float = np.nan
    t_stat: float = np.nan
    p_value: float = np.nan
    n_days: int = 0
    lookforward: int = 1
    daily_ics: List[float] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    expression: str = ""
    train_ic: float = np.nan      # 训练段 IC（split 时有效）
    valid_ic: float = np.nan      # 验证段 IC（split 时有效）
    train_icir: float = np.nan
    valid_icir: float = np.nan

    def to_dict(self) -> Dict[str, float]:
        d = {k: v for k, v in self.__dict__.items()
             if not isinstance(v, list)}
        return d

    def passes(self, ic_threshold: float = 0.03,
               ir_threshold: float = 1.0) -> bool:
        """阈值判定（对齐项目 IC>0.03 且 IR>1 纪律）"""
        return (abs(self.ic_mean) >= ic_threshold
                and abs(self.icir) >= ir_threshold)


# ============================================================
# 核心计算
# ============================================================

def _rankdata(x: np.ndarray) -> np.ndarray:
    """平均排名（处理 ties），与 AI_yinzi_mc 口径一致"""
    n = len(x)
    order = np.argsort(x)
    ranks = np.empty(n, dtype=float)
    ranks[order] = np.arange(1, n + 1, dtype=float)
    unique_vals, inverse, counts = np.unique(x, return_inverse=True, return_counts=True)
    if np.any(counts > 1):
        sorted_ranks = np.arange(1, n + 1, dtype=float)
        for i, val in enumerate(unique_vals):
            if counts[i] > 1:
                mask = (inverse == i)
                ranks[mask] = sorted_ranks[mask].mean()
    return ranks


def _spearman_corr(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman 等级相关（手写，避免 scipy 对 ties 的边界差异）"""
    rx = _rankdata(x)
    ry = _rankdata(y)
    rx_centered = rx - rx.mean()
    ry_centered = ry - ry.mean()
    denom = np.sqrt(np.sum(rx_centered ** 2) * np.sum(ry_centered ** 2))
    if denom < 1e-12:
        return 0.0
    return float(np.sum(rx_centered * ry_centered) / denom)


def compute_ic_series(factor_values: np.ndarray,
                      future_returns: np.ndarray,
                      method: str = 'spearman',
                      min_samples: int = 10,
                      min_days: int = 30,
                      dates: Optional[pd.DatetimeIndex] = None,
                      ) -> tuple:
    """计算日频 IC 序列

    Args:
        factor_values: 因子值 ndarray (T, N)，NaN 表示无效
        future_returns: 未来收益 ndarray (T, N)
        method: 'spearman' | 'pearson'
        min_samples: 单日有效截面最少标的数（低于则跳过该日）
        min_days: 有效天数下限（不足返回空）
        dates: 可选日期索引，用于返回 dates

    Returns:
        (daily_ics: np.ndarray, valid_dates: np.ndarray[datetime])
    """
    T = factor_values.shape[0]
    daily_ics: List[float] = []
    valid_idx: List[int] = []

    for t in range(T):
        f_row = factor_values[t]
        r_row = future_returns[t]
        mask = np.isfinite(f_row) & np.isfinite(r_row)
        if mask.sum() < min_samples:
            continue
        fv = f_row[mask]
        rv = r_row[mask]
        if np.nanstd(fv) < 1e-12 or np.nanstd(rv) < 1e-12:
            continue
        if method == 'spearman':
            ic = _spearman_corr(fv, rv)
        elif method == 'pearson':
            ic = float(np.corrcoef(fv, rv)[0, 1])
        else:
            raise ValueError(f"不支持的 IC 方法: {method}")
        if np.isfinite(ic):
            daily_ics.append(ic)
            valid_idx.append(t)

    if len(daily_ics) < min_days:
        return np.array([]), np.array([], dtype=object)

    ics = np.array(daily_ics)
    if dates is not None:
        vdates = np.array(dates[valid_idx], dtype=object)
    else:
        vdates = np.array(valid_idx, dtype=object)
    return ics, vdates


def summarize_ics(daily_ics: np.ndarray,
                  valid_dates: Optional[np.ndarray] = None,
                  lookforward: int = 1,
                  expression: str = "") -> ICResult:
    """从日频 IC 序列汇总统计"""
    if len(daily_ics) == 0:
        return ICResult(expression=expression, lookforward=lookforward)

    ics = daily_ics
    std = float(np.std(ics))
    result = ICResult(
        ic_mean=float(np.mean(ics)),
        ic_std=std,
        icir=float(np.mean(ics) / std) if std > 1e-10 else np.nan,
        positive_ratio=float(np.mean(ics > 0)),
        n_days=len(ics),
        lookforward=lookforward,
        daily_ics=ics.tolist(),
        expression=expression,
    )
    if len(ics) > 1:
        t, p = stats.ttest_1samp(ics, 0)
        result.t_stat = float(t)
        result.p_value = float(p)
    if valid_dates is not None and len(valid_dates) == len(ics):
        result.dates = [str(d)[:10] for d in valid_dates]
    return result


def _align_forward(factor_values: np.ndarray,
                   future_returns: np.ndarray,
                   lookforward: int) -> tuple:
    """多期前瞻对齐：N期累积收益反向滚动

    对齐 factor/v5/validator 的 [修复] 2026-05-20 口径：
    fw_cum[t] = prod(1+r[t+1..t+N]) - 1
    """
    T, N = factor_values.shape
    if lookforward <= 1:
        return factor_values[:-1], future_returns[1:]

    # fw_cum 为 (T,N) 2D：逐标的累积 N 期收益
    fw_cum = np.full((T, N), np.nan)
    for t in range(T - lookforward):
        fw_cum[t] = np.prod(1.0 + future_returns[t + 1: t + 1 + lookforward],
                            axis=0) - 1.0
    tail = lookforward - 1
    f_aligned = factor_values[:-tail] if tail > 0 else factor_values[:-1]
    r_aligned = fw_cum[:-tail] if tail > 0 else fw_cum[1:]
    return f_aligned, r_aligned


# ============================================================
# 标准化校验器（供探索脚本/MCTS 候选池统一调用）
# ============================================================

class ICValidator:
    """独立 IC 检验器 — 先 SR 探索, 后 IC 检验 的标准化出口

    用法:
        >>> validator = ICValidator(returns, forward_period=5)
        >>> result = validator.validate(factor_values)   # ICResult
        >>> df = validator.validate_pool([v1, v2], names=['f1','f2'])  # 批量排序
    """

    def __init__(self,
                 future_returns: Union[np.ndarray, pd.DataFrame],
                 forward_period: int = 1,
                 method: str = 'spearman',
                 min_samples: int = 10,
                 min_days: int = 30,
                 train_ratio: float = 0.7,
                 ic_threshold: float = 0.03,
                 ir_threshold: float = 1.0):
        """
        Args:
            future_returns: 未来收益 (T,N) 或 DataFrame(日期×标的)
            forward_period: 前瞻期数（多期时内部对齐 N 期累积收益）
            method: 'spearman' | 'pearson'
            min_samples: 单日最少有效标的
            min_days: 最少有效天数
            train_ratio: 训练/验证切分比（0.7 = 前70%训练）
            ic_threshold: IC 阈值（passes 判定用）
            ir_threshold: ICIR 阈值
        """
        if isinstance(future_returns, pd.DataFrame):
            self.dates = future_returns.index
            self._returns = future_returns.values
        else:
            self.dates = None
            self._returns = future_returns
        self.forward_period = forward_period
        self.method = method
        self.min_samples = min_samples
        self.min_days = min_days
        self.train_ratio = train_ratio
        self.ic_threshold = ic_threshold
        self.ir_threshold = ir_threshold

        T = self._returns.shape[0]
        self.train_end = int(T * train_ratio)

    # -- 单次校验 --

    def validate(self, factor_values: np.ndarray,
                 expression: str = "") -> ICResult:
        """校验单因子/单信号（返回完整统计 + 训练/验证切分）"""
        if factor_values is None or factor_values.shape != self._returns.shape:
            return ICResult(expression=expression, lookforward=self.forward_period)

        f_aligned, r_aligned = _align_forward(
            factor_values, self._returns, self.forward_period)

        ics, vdates = compute_ic_series(
            f_aligned, r_aligned, method=self.method,
            min_samples=self.min_samples, min_days=self.min_days,
            dates=(self.dates[:len(f_aligned)] if self.dates is not None else None))

        result = summarize_ics(ics, vdates, self.forward_period, expression)

        # 训练/验证切分
        n = len(ics)
        if n > self.min_days:
            split = int(n * self.train_ratio)
            if split >= 5:
                tr = summarize_ics(ics[:split], lookforward=self.forward_period)
                va = summarize_ics(ics[split:], lookforward=self.forward_period)
                result.train_ic = tr.ic_mean
                result.train_icir = tr.icir
                result.valid_ic = va.ic_mean
                result.valid_icir = va.icir
        return result

    # -- 批量校验（候选池）--

    def validate_pool(self,
                      candidates: List[np.ndarray],
                      names: Optional[List[str]] = None,
                      sort_by: str = 'icir') -> pd.DataFrame:
        """批量校验候选池 → 排序后的 DataFrame

        Args:
            candidates: [ndarray(T,N), ...] 因子值列表
            names: 候选名（表达式或编号）
            sort_by: 排序字段 'icir' | 'ic_mean' | 't_stat'

        Returns:
            DataFrame: {name, ic_mean, icir, positive_ratio, t_stat, train_ic, valid_ic, pass}
        """
        rows = []
        for i, fv in enumerate(candidates):
            name = names[i] if names and i < len(names) else f"#{i+1}"
            r = self.validate(fv, expression=name)
            rows.append({
                'name': name,
                'ic_mean': r.ic_mean,
                'icir': r.icir,
                'positive_ratio': r.positive_ratio,
                't_stat': r.t_stat,
                'n_days': r.n_days,
                'train_ic': r.train_ic,
                'valid_ic': r.valid_ic,
                'pass': r.passes(self.ic_threshold, self.ir_threshold),
            })
        df = pd.DataFrame(rows)
        if sort_by in df.columns:
            df = df.sort_values(sort_by, key=lambda s: s.abs(),
                                ascending=False).reset_index(drop=True)
        return df

    # -- 衰减曲线（多期前瞻） --

    def decay(self, factor_values: np.ndarray,
              max_lookforward: int = 20,
              expression: str = "") -> pd.DataFrame:
        """多前瞻期 IC 衰减曲线

        Returns:
            DataFrame: {lookforward, ic_mean, icir}
        """
        rows = []
        for lf in range(1, max_lookforward + 1):
            f_aligned, r_aligned = _align_forward(factor_values, self._returns, lf)
            ics, _ = compute_ic_series(
                f_aligned, r_aligned, method=self.method,
                min_samples=self.min_samples, min_days=max(5, self.min_days // 3))
            if len(ics) == 0:
                continue
            r = summarize_ics(ics, lookforward=lf)
            rows.append({'lookforward': lf, 'ic_mean': r.ic_mean, 'icir': r.icir})
        return pd.DataFrame(rows)

    # -- 分年度 IC --

    def yearly_ic(self, factor_values: np.ndarray,
                  expression: str = "") -> pd.DataFrame:
        """分年度 IC 均值/ICIR/正占比（对齐 FactorValidator.yearly_ic）"""
        f_aligned, r_aligned = _align_forward(
            factor_values, self._returns, self.forward_period)
        ics, vdates = compute_ic_series(
            f_aligned, r_aligned, method=self.method,
            min_samples=self.min_samples, min_days=1,
            dates=(self.dates[:len(f_aligned)] if self.dates is not None else None))

        if len(ics) == 0 or len(vdates) == 0:
            return pd.DataFrame()
        if not isinstance(vdates[0], (str, np.datetime64)):
            return pd.DataFrame()

        years = np.array([str(d)[:4] for d in vdates])
        rows = []
        for yr in sorted(set(years)):
            yr_ics = ics[years == yr]
            if len(yr_ics) < 5:
                continue
            r = summarize_ics(yr_ics)
            rows.append({'year': yr, 'ic_mean': r.ic_mean, 'icir': r.icir,
                         'positive_ratio': r.positive_ratio, 'n_days': r.n_days})
        return pd.DataFrame(rows)
