# signal/combiner.py - 信号融合器
"""
多信号融合器

支持：
1. 投票融合（少数服从多数）
2. 加权融合（手动/自动权重）
3. 打分融合（归一化后加权）
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from .base import Signal, SignalDirection, TradingSignal, SignalSeries


class SignalCombiner(ABC):
    """
    信号融合器基类
    
    输入：多个信号
    输出：综合交易信号
    """
    
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
    
    @abstractmethod
    def combine(self, signals: List[Signal]) -> TradingSignal:
        """
        融合多个信号
        
        Args:
            signals: 信号列表
            
        Returns:
            TradingSignal: 综合交易信号
        """
        pass
    
    def combine_series(self, signal_series: SignalSeries) -> pd.Series:
        """
        融合信号序列
        
        Args:
            signal_series: 信号序列
            
        Returns:
            pd.Series: 综合信号序列
        """
        pass


class VotingCombiner(SignalCombiner):
    """
    投票融合器
    
    规则：
    - 多头信号 > 空头信号 → 做多
    - 空头信号 > 多头信号 → 做空
    - 数量相等 → 中立
    """
    
    def __init__(self):
        super().__init__("VotingCombiner")
    
    def combine(self, signals: List[Signal]) -> TradingSignal:
        long_count = sum(1 for s in signals if s.is_long)
        short_count = sum(1 for s in signals if s.is_short)
        neutral_count = sum(1 for s in signals if s.is_neutral)
        
        if long_count > short_count:
            return TradingSignal.long(
                strength=long_count / len(signals),
                signals=signals
            )
        elif short_count > long_count:
            return TradingSignal.short(
                strength=short_count / len(signals),
                signals=signals
            )
        else:
            return TradingSignal.neutral(signals=signals)
    
    def combine_series(self, signal_series: SignalSeries) -> pd.Series:
        """
        投票融合信号序列
        
        Args:
            signal_series: 信号序列，index=时间, columns=信号名
            
        Returns:
            pd.Series: 综合信号 -1/0/1
        """
        signals_df = signal_series.signals
        
        # 方向化：>0 = 1, <0 = -1, =0 = 0
        directions = np.sign(signals_df)
        
        # 投票：求和
        votes = directions.sum(axis=1)
        
        # 最终方向：>0 = 1, <0 = -1, =0 = 0
        result = np.sign(votes)
        
        return pd.Series(result, index=signals_df.index)


class ScoringCombiner(SignalCombiner):
    """
    打分融合器
    
    规则：
    1. 归一化所有信号到 [-1, 1]
    2. 加权求和
    3. >0 做多，<0 做空
    """
    
    def __init__(self, weights: Dict[str, float] = None):
        super().__init__("ScoringCombiner")
        self.weights = weights or {}
    
    def combine(self, signals: List[Signal]) -> TradingSignal:
        if not signals:
            return TradingSignal.neutral()
        
        total_score = 0
        total_weight = 0
        
        for signal in signals:
            weight = self.weights.get(signal.name, 1.0)
            
            # 归一化到 [-1, 1]
            normalized = np.tanh(signal.value)
            
            total_score += normalized * weight
            total_weight += weight
        
        if total_weight == 0:
            return TradingSignal.neutral(signals=signals)
        
        final_score = total_score / total_weight
        
        if final_score > 0:
            return TradingSignal.long(
                strength=abs(final_score),
                signals=signals
            )
        elif final_score < 0:
            return TradingSignal.short(
                strength=abs(final_score),
                signals=signals
            )
        else:
            return TradingSignal.neutral(signals=signals)
    
    def combine_series(self, signal_series: SignalSeries) -> pd.Series:
        """
        打分融合信号序列
        
        Args:
            signal_series: 信号序列
            
        Returns:
            pd.Series: 综合信号序列 [-1, 1]
        """
        signals_df = signal_series.signals
        
        # 归一化
        normalized = signals_df.apply(lambda x: np.tanh(x))
        
        # 加权
        if self.weights:
            for col in normalized.columns:
                if col in self.weights:
                    normalized[col] *= self.weights[col]
        
        # 求和归一化
        result = normalized.sum(axis=1)
        
        # 归一化到 [-1, 1]
        max_abs = result.abs().max()
        if max_abs > 0:
            result = result / max_abs
        
        return result


class WeightedCombiner(SignalCombiner):
    """
    加权融合器（固定权重）
    
    与 ScoringCombiner 类似，但权重必须指定
    """
    
    def __init__(self, weights: Dict[str, float]):
        super().__init__("WeightedCombiner")
        
        # 归一化权重
        total = sum(weights.values())
        self.weights = {k: v / total for k, v in weights.items()}
    
    def combine(self, signals: List[Signal]) -> TradingSignal:
        if not signals:
            return TradingSignal.neutral()
        
        total_score = 0
        
        for signal in signals:
            weight = self.weights.get(signal.name, 0)
            total_score += signal.value * weight
        
        if total_score > 0:
            return TradingSignal.long(
                strength=abs(total_score),
                signals=signals
            )
        elif total_score < 0:
            return TradingSignal.short(
                strength=abs(total_score),
                signals=signals
            )
        else:
            return TradingSignal.neutral(signals=signals)
    
    def combine_series(self, signal_series: SignalSeries) -> pd.Series:
        signals_df = signal_series.signals.copy()
        
        # 加权
        for col in signals_df.columns:
            if col in self.weights:
                signals_df[col] *= self.weights[col]
        
        return signals_df.sum(axis=1)


class AdaptiveCombiner(SignalCombiner):
    """
    自适应融合器
    
    根据历史 IC 自动调整权重
    """
    
    def __init__(self, lookback: int = 60):
        super().__init__("AdaptiveCombiner")
        self.lookback = lookback
        self.weights = {}
    
    def fit(self, signal_series: SignalSeries, returns: pd.Series):
        """
        根据历史数据拟合权重
        
        Args:
            signal_series: 信号序列
            returns: 未来收益率序列
        """
        signals_df = signal_series.signals
        
        # 计算每个信号的 IC
        for col in signals_df.columns:
            signal = signals_df[col].shift(1)  # 信号发生在收益之前
            ic = signal.corr(returns)
            
            if not np.isnan(ic):
                # IC 作为权重
                self.weights[col] = abs(ic)
        
        # 归一化
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
        else:
            self.weights = {k: 1 / len(signals_df.columns) for k in signals_df.columns}
    
    def combine(self, signals: List[Signal]) -> TradingSignal:
        if not signals:
            return TradingSignal.neutral()
        
        total_score = 0
        
        for signal in signals:
            weight = self.weights.get(signal.name, 0)
            total_score += signal.value * weight
        
        if total_score > 0:
            return TradingSignal.long(strength=abs(total_score), signals=signals)
        elif total_score < 0:
            return TradingSignal.short(strength=abs(total_score), signals=signals)
        else:
            return TradingSignal.neutral(signals=signals)
    
    def combine_series(self, signal_series: SignalSeries) -> pd.Series:
        signals_df = signal_series.signals.copy()
        
        # 加权
        for col in signals_df.columns:
            if col in self.weights:
                signals_df[col] *= self.weights[col]
        
        return signals_df.sum(axis=1)


class EqualWeightCombiner(SignalCombiner):
    """
    等权融合器
    
    所有信号权重相等
    """
    
    def __init__(self):
        super().__init__("EqualWeightCombiner")
    
    def combine(self, signals: List[Signal]) -> TradingSignal:
        if not signals:
            return TradingSignal.neutral()
        
        # 计算平均信号值
        avg_value = np.mean([s.value for s in signals])
        
        # 判断方向
        if avg_value > 0:
            return TradingSignal.long(strength=abs(avg_value), signals=signals)
        elif avg_value < 0:
            return TradingSignal.short(strength=abs(avg_value), signals=signals)
        else:
            return TradingSignal.neutral(signals=signals)
    
    def combine_series(self, signal_series: SignalSeries) -> pd.Series:
        return signal_series.signals.mean(axis=1)
