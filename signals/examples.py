# signal/examples.py - 使用示例
"""
信号层使用示例

运行方式：
  python i:\qev1\signal\examples.py
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, r'i:\qev1')

from signals import (
    # 基类
    Signal, SignalType, SignalDirection, TradingSignal,
    # 生成器
    SignalGenerator, MASignal, MACDSignal, RSISignal, KDJSignal, 
    BOLLSignal, VOLSignal, RSRSMSignal, CompositeSignal,
    # 融合器
    SignalCombiner, VotingCombiner, ScoringCombiner, 
    WeightedCombiner, EqualWeightCombiner,
    # 注册器
    SignalRegistry,
    # 阈值
    ThresholdPolicy, SimpleThreshold, PercentileThreshold, DualThreshold,
)


# =============================================================================
# 示例 1：生成模拟数据
# =============================================================================

def generate_sample_data(days: int = 300, symbol: str = '000001.SZ') -> pd.DataFrame:
    """生成模拟 K 线数据"""
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    # 生成随机价格
    np.random.seed(42)
    returns = np.random.randn(days) * 0.02
    close = 10 * (1 + returns).cumprod()
    
    # 生成 OHLC
    high = close * (1 + np.random.rand(days) * 0.01)
    low = close * (1 - np.random.rand(days) * 0.01)
    open_price = low + (high - low) * np.random.rand(days)
    volume = np.random.randint(1e6, 1e8, days)
    
    df = pd.DataFrame({
        'symbol': symbol,
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }, index=dates)
    
    df.index.name = 'date'
    return df


# =============================================================================
# 示例 2：基础信号生成
# =============================================================================

def example_basic_signals():
    """基础信号生成示例"""
    print("\n" + "=" * 60)
    print("示例 2: 基础信号生成")
    print("=" * 60)
    
    # 生成数据
    data = generate_sample_data(300)
    print(f"\n数据形状: {data.shape}")
    print(f"数据列: {list(data.columns)}")
    print(f"\n最新5行:")
    print(data.tail())
    
    # 创建信号生成器
    print("\n--- 创建信号生成器 ---")
    
    ma_signal = MASignal(short_period=5, long_period=20)
    macd_signal = MACDSignal(fast=12, slow=26, signal=9)
    rsi_signal = RSISignal(period=14)
    kdj_signal = KDJSignal(n=9, m1=3, m2=3)
    boll_signal = BOLLSignal(period=20, std_dev=2)
    
    # 生成信号
    print("\n--- 生成信号 ---")
    
    ma_series = ma_signal.generate(data)
    macd_series = macd_signal.generate(data)
    rsi_series = rsi_signal.generate(data)
    kdj_series = kdj_signal.generate(data)
    boll_series = boll_signal.generate(data)
    
    print(f"MA 信号: {ma_signal.name}")
    print(f"  最新值: {ma_series.iloc[-1]:.4f}")
    print(f"  均值: {ma_series.mean():.4f}")
    
    print(f"\nMACD 信号: {macd_signal.name}")
    print(f"  最新值: {macd_series.iloc[-1]:.4f}")
    
    print(f"\nRSI 信号: {rsi_signal.name}")
    print(f"  最新值: {rsi_series.iloc[-1]:.2f}")
    
    print(f"\nKDJ 信号: {kdj_signal.name}")
    print(f"  最新值: {kdj_series.iloc[-1]:.2f}")
    
    print(f"\nBOLL 信号: {boll_signal.name}")
    print(f"  最新值: {boll_series.iloc[-1]:.4f}")
    
    # 生成最新信号
    print("\n--- 最新信号 ---")
    
    ma_latest = ma_signal.generate_latest(data)
    print(f"MA 最新: value={ma_latest.value:.4f}, direction={ma_latest.direction.name}")


# =============================================================================
# 示例 3：信号融合
# =============================================================================

def example_signal_combination():
    """信号融合示例"""
    print("\n" + "=" * 60)
    print("示例 3: 信号融合")
    print("=" * 60)
    
    # 生成数据
    data = generate_sample_data(300)
    
    # 创建多个信号生成器
    generators = [
        MASignal(short_period=5, long_period=20),
        MASignal(short_period=10, long_period=60),
        MACDSignal(fast=12, slow=26, signal=9),
        RSISignal(period=14),
        KDJSignal(n=9, m1=3, m2=3),
    ]
    
    # 生成信号序列
    signal_dict = {}
    for gen in generators:
        signal_dict[gen.name] = gen.generate(data)
    
    signals_df = pd.DataFrame(signal_dict)
    
    print(f"\n信号数据形状: {signals_df.shape}")
    print(f"信号列: {list(signals_df.columns)}")
    print(f"\n最新信号值:")
    print(signals_df.tail())
    
    # 融合器
    print("\n--- 融合器 ---")
    
    # 1. 投票融合
    voting_combiner = VotingCombiner()
    voting_result = voting_combiner.combine_series(
        type('SignalSeries', (), {'signals': signals_df})()
    )
    print(f"投票融合（最新）: {voting_result.iloc[-1]}")
    
    # 2. 打分融合
    weights = {
        'MA5_20': 0.3,
        'MA10_60': 0.2,
        'Macd12_26_9': 0.25,
        'RSI14': 0.15,
        'KDJ9_3_3': 0.1,
    }
    scoring_combiner = ScoringCombiner(weights=weights)
    scoring_result = scoring_combiner.combine_series(
        type('SignalSeries', (), {'signals': signals_df})()
    )
    print(f"打分融合（最新）: {scoring_result.iloc[-1]:.4f}")
    
    # 3. 等权融合
    equal_combiner = EqualWeightCombiner()
    equal_result = equal_combiner.combine_series(
        type('SignalSeries', (), {'signals': signals_df})()
    )
    print(f"等权融合（最新）: {equal_result.iloc[-1]:.4f}")


# =============================================================================
# 示例 4：组合信号生成器
# =============================================================================

def example_composite_signal():
    """组合信号示例"""
    print("\n" + "=" * 60)
    print("示例 4: 组合信号")
    print("=" * 60)
    
    # 生成数据
    data = generate_sample_data(300)
    
    # 创建组合信号
    composite = CompositeSignal([
        MASignal(short_period=5, long_period=20),
        MACDSignal(fast=12, slow=26, signal=9),
        RSISignal(period=14),
    ], name='CompositeTrend')
    
    print(f"\n组合信号: {composite.name}")
    
    # 生成
    signal_series = composite.generate(data)
    latest_signal = composite.generate_latest(data)
    
    print(f"信号序列长度: {len(signal_series)}")
    print(f"最新信号值: {signal_series.iloc[-1]:.4f}")
    print(f"最新信号方向: {latest_signal.direction.name}")


# =============================================================================
# 示例 5：阈值策略
# =============================================================================

def example_threshold():
    """阈值策略示例"""
    print("\n" + "=" * 60)
    print("示例 5: 阈值策略")
    print("=" * 60)
    
    # 生成数据
    data = generate_sample_data(300)
    
    # 生成信号
    ma = MASignal(short_period=5, long_period=20)
    signal = ma.generate(data)
    
    print(f"\n信号统计:")
    print(f"  均值: {signal.mean():.4f}")
    print(f"  标准差: {signal.std():.4f}")
    print(f"  最小: {signal.min():.4f}")
    print(f"  最大: {signal.max():.4f}")
    
    # 简单阈值
    simple = SimpleThreshold(upper_threshold=0, lower_threshold=0)
    directions = simple.apply_series(signal)
    
    print(f"\n简单阈值 (0, 0):")
    print(f"  做多次数: {(directions == 1).sum()}")
    print(f"  做空次数: {(directions == -1).sum()}")
    print(f"  中立次数: {(directions == 0).sum()}")
    
    # 分位数阈值
    percentile = PercentileThreshold(upper_percentile=75, lower_percentile=25)
    percentile.fit(signal)
    directions_pct = percentile.apply_series(signal)
    
    print(f"\n分位数阈值 (75%, 25%):")
    print(f"  做多次数: {(directions_pct == 1).sum()}")
    print(f"  做空次数: {(directions_pct == -1).sum()}")
    print(f"  中立次数: {(directions_pct == 0).sum()}")


# =============================================================================
# 示例 6：完整流程
# =============================================================================

def example_full_workflow():
    """完整工作流程"""
    print("\n" + "=" * 60)
    print("示例 6: 完整工作流程")
    print("=" * 60)
    
    # 1. 生成数据
    print("\n[1] 生成模拟数据...")
    data = generate_sample_data(300)
    
    # 2. 创建信号生成器
    print("[2] 创建信号生成器...")
    generators = [
        MASignal(short_period=5, long_period=20),
        MACDSignal(fast=12, slow=26, signal=9),
        RSISignal(period=14),
        KDJSignal(n=9, m1=3, m2=3),
        BOLLSignal(period=20, std_dev=2),
    ]
    
    # 3. 生成信号
    print("[3] 生成信号...")
    signal_dict = {}
    for gen in generators:
        signal_dict[gen.name] = gen.generate(data)
    signals_df = pd.DataFrame(signal_dict)
    
    # 4. 融合信号
    print("[4] 融合信号...")
    combiner = EqualWeightCombiner()
    combined = combiner.combine_series(
        type('SignalSeries', (), {'signals': signals_df})()
    )
    
    # 5. 阈值化
    print("[5] 阈值化...")
    threshold = SimpleThreshold(upper_threshold=0, lower_threshold=0)
    trading_signals = threshold.apply_series(combined)
    
    # 6. 统计
    print("\n[6] 统计结果:")
    print(f"  做多天数: {(trading_signals == 1).sum()}")
    print(f"  做空天数: {(trading_signals == -1).sum()}")
    print(f"  中立天数: {(trading_signals == 0).sum()}")
    
    # 7. 计算收益
    print("\n[7] 计算收益...")
    returns = data['close'].pct_change()
    strategy_returns = returns * trading_signals.shift(1)
    
    total_return = (1 + strategy_returns).prod() - 1
    print(f"  策略总收益: {total_return:.2%}")
    print(f"  买入持有收益: {(1 + returns).prod() - 1:.2%}")


# =============================================================================
# 主程序
# =============================================================================

def main():
    print("=" * 60)
    print("信号层 (signal) 使用示例")
    print("=" * 60)
    
    example_basic_signals()
    example_signal_combination()
    example_composite_signal()
    example_threshold()
    example_full_workflow()
    
    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
