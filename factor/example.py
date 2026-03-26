"""
因子挖掘模块使用示例

这个示例展示了如何使用ft2.factor模块进行因子挖掘、检验和组合。

主要步骤：
1. 创建自定义因子
2. 使用因子计算引擎批量计算因子
3. 使用因子检验器验证因子质量
4. 使用因子组合器组合多个因子
5. 使用因子管理器管理因子库
"""

import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 导入因子挖掘模块
from ft2.factor import (
    # 基础类
    Factor, FactorMetadata, FactorCategory, FactorFrequency,
    factor_decorator, FactorMeta,
    
    # 计算引擎
    FactorCalculator, DataSource, create_sample_data,
    
    # 检验器
    FactorValidator, ValidationMetric, validation_metric,
    
    # 组合器
    FactorCombiner, CombinationMethod, OrthogonalizationMethod,
    
    # 管理器
    FactorManager, StorageFormat, FactorStatus
)


# ============================================================================
# 1. 创建自定义因子
# ============================================================================

class MomentumFactor(Factor, metaclass=FactorMeta):
    """动量因子：过去N日的收益率"""
    
    def __init__(self, lookback: int = 20):
        metadata = FactorMetadata(
            name=f"Momentum_{lookback}D",
            description=f"{lookback}日动量因子",
            category=FactorCategory.MOMENTUM,
            frequency=FactorFrequency.DAILY,
            parameters={'lookback': lookback}
        )
        super().__init__(metadata)
        self.lookback = lookback
    
    def calculate(self, data: dict, symbols: list, dates: list) -> pd.DataFrame:
        """计算动量因子"""
        if 'close' not in data:
            raise ValueError("需要收盘价数据")
            
        close_prices = data['close']
        
        # 计算收益率：当前价格 / N日前价格 - 1
        momentum = close_prices / close_prices.shift(self.lookback) - 1
        
        return momentum


class VolumeFactor(Factor, metaclass=FactorMeta):
    """成交量因子：成交量相对变化"""
    
    def __init__(self, lookback: int = 20):
        metadata = FactorMetadata(
            name=f"Volume_{lookback}D",
            description=f"{lookback}日成交量因子",
            category=FactorCategory.VOLUME,
            frequency=FactorFrequency.DAILY,
            parameters={'lookback': lookback}
        )
        super().__init__(metadata)
        self.lookback = lookback
    
    def calculate(self, data: dict, symbols: list, dates: list) -> pd.DataFrame:
        """计算成交量因子"""
        if 'volume' not in data:
            raise ValueError("需要成交量数据")
            
        volume = data['volume']
        
        # 计算成交量相对变化：当前成交量 / 过去N日平均成交量 - 1
        avg_volume = volume.rolling(window=self.lookback).mean()
        volume_factor = volume / avg_volume - 1
        
        return volume_factor


# 使用装饰器创建因子（另一种方式）
@factor_decorator(name="Volatility_20D", 
                 description="20日波动率因子",
                 category=FactorCategory.VOLATILITY,
                 frequency=FactorFrequency.DAILY)
def calculate_volatility(data: dict, symbols: list, dates: list) -> pd.DataFrame:
    """计算波动率因子"""
    if 'close' not in data:
        raise ValueError("需要收盘价数据")
        
    close_prices = data['close']
    
    # 计算20日收益率波动率
    returns = close_prices.pct_change()
    volatility = returns.rolling(window=20).std()
    
    return volatility


# ============================================================================
# 2. 准备数据
# ============================================================================

def prepare_sample_data():
    """准备示例数据"""
    # 生成示例标的和日期
    symbols = [f"STOCK_{i:03d}" for i in range(1, 51)]  # 50个标的
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='B')  # 交易日
    
    # 创建示例数据
    data = create_sample_data(symbols, dates, seed=42)
    
    # 创建未来收益率（用于因子检验）
    # 简单使用未来1日的收益率
    future_returns = data['close'].pct_change().shift(-1)
    
    return data, future_returns, symbols, dates


# ============================================================================
# 3. 使用因子计算引擎
# ============================================================================

def demo_factor_calculator():
    """演示因子计算引擎的使用"""
    print("=" * 60)
    print("因子计算引擎演示")
    print("=" * 60)
    
    # 准备数据
    data, future_returns, symbols, dates = prepare_sample_data()
    
    # 创建数据源
    data_source = DataSource(data)
    
    # 创建因子计算引擎
    calculator = FactorCalculator(data_source=data_source, max_workers=2)
    
    # 创建因子实例
    momentum_factor = MomentumFactor(lookback=20)
    volume_factor = VolumeFactor(lookback=20)
    
    # 注册因子
    calculator.register_factor(momentum_factor)
    calculator.register_factor(volume_factor)
    
    # 批量计算因子
    print(f"计算 {len(symbols)} 个标的在 {len(dates)} 个交易日的因子...")
    
    factor_names = [momentum_factor.metadata.name, volume_factor.metadata.name]
    results = calculator.calculate_batch(
        factor_names=factor_names,
        symbols=symbols,
        dates=dates,
        parallel=True
    )
    
    # 显示结果
    for factor_name, factor_values in results.items():
        print(f"\n因子: {factor_name}")
        print(f"形状: {factor_values.shape}")
        print(f"有效值比例: {factor_values.notna().mean().mean():.2%}")
        print(f"均值: {factor_values.mean().mean():.6f}")
        print(f"标准差: {factor_values.std().mean():.6f}")
    
    # 获取统计信息
    stats = calculator.get_stats()
    print(f"\n计算统计:")
    print(f"总计算次数: {stats['total_calculations']}")
    print(f"缓存命中次数: {stats['cache_hits']}")
    print(f"计算时间: {stats['calculation_time']:.2f}秒")
    
    return results, future_returns


# ============================================================================
# 4. 使用因子检验器
# ============================================================================

def demo_factor_validator(factor_results: dict, future_returns: pd.DataFrame):
    """演示因子检验器的使用"""
    print("\n" + "=" * 60)
    print("因子检验器演示")
    print("=" * 60)
    
    for factor_name, factor_values in factor_results.items():
        print(f"\n检验因子: {factor_name}")
        
        # 创建因子检验器
        validator = FactorValidator(
            factor_values=factor_values,
            future_returns=future_returns,
            group_count=10
        )
        
        # 运行所有验证
        validation_results = validator.run_all_validations(
            lookforward=1,
            save_report=False
        )
        
        # 显示关键指标
        print(f"IC均值: {validator.information_coefficient().get('mean', 'N/A'):.4f}")
        print(f"IR: {validator.information_ratio():.4f}")
        print(f"换手率: {validator.turnover_rate().get('mean', 'N/A'):.2%}")
        
        group_returns = validator.group_returns()
        if group_returns.get('returns'):
            print(f"多空收益: {group_returns.get('spread', 'N/A'):.4f}")
            print(f"单调性: {group_returns.get('monotonicity', 'N/A'):.4f}")
        
        print(f"命中率: {validator.hit_rate():.2%}")
        
        # 绘制IC序列图（注释掉以避免显示）
        # validator.plot_ic_series(lookforward=1, save_path=f"{factor_name}_ic.png")
        
        # 绘制分组收益图（注释掉以避免显示）
        # validator.plot_group_returns(lookforward=1, save_path=f"{factor_name}_groups.png")


# ============================================================================
# 5. 使用因子组合器
# ============================================================================

def demo_factor_combiner(factor_results: dict, future_returns: pd.DataFrame):
    """演示因子组合器的使用"""
    print("\n" + "=" * 60)
    print("因子组合器演示")
    print("=" * 60)
    
    # 创建因子组合器
    combiner = FactorCombiner(
        factor_values=factor_results,
        future_returns=future_returns
    )
    
    factor_names = list(factor_results.keys())
    print(f"组合因子: {factor_names}")
    
    # 测试不同的组合方法
    methods = [
        (CombinationMethod.EQUAL_WEIGHT, "等权组合"),
        (CombinationMethod.IC_WEIGHT, "IC加权"),
        (CombinationMethod.IR_WEIGHT, "IR加权"),
        (CombinationMethod.MIN_VARIANCE, "最小方差"),
    ]
    
    for method, method_name in methods:
        print(f"\n{method_name}:")
        
        try:
            # 组合因子
            result = combiner.combine(
                factor_names=factor_names,
                method=method,
                orthogonalization=OrthogonalizationMethod.NONE,
                lookforward=1
            )
            
            # 显示结果
            print(f"  权重: {result.weights}")
            print(f"  有效因子数量: {result.metrics.get('effective_number', 'N/A'):.2f}")
            
            if 'ic' in result.metrics:
                print(f"  组合IC: {result.metrics['ic']:.4f}")
            if 'ir' in result.metrics:
                print(f"  组合IR: {result.metrics['ir']:.4f}")
                
        except Exception as e:
            print(f"  错误: {e}")
    
    # 测试正交化
    print(f"\n正交化组合 (残差正交化):")
    try:
        result = combiner.combine(
            factor_names=factor_names,
            method=CombinationMethod.EQUAL_WEIGHT,
            orthogonalization=OrthogonalizationMethod.RESIDUAL,
            lookforward=1
        )
        print(f"  权重: {result.weights}")
    except Exception as e:
        print(f"  错误: {e}")


# ============================================================================
# 6. 使用因子管理器
# ============================================================================

def demo_factor_manager():
    """演示因子管理器的使用"""
    print("\n" + "=" * 60)
    print("因子管理器演示")
    print("=" * 60)
    
    # 创建因子管理器（使用临时目录）
    import tempfile
    import os
    
    temp_dir = tempfile.mkdtemp()
    manager = FactorManager(storage_path=temp_dir, auto_load=False)
    
    # 创建因子实例
    momentum_factor = MomentumFactor(lookback=20)
    volume_factor = VolumeFactor(lookback=20)
    
    # 注册因子
    print("注册因子到因子库...")
    manager.register_factor(
        factor=momentum_factor,
        version="1.0.0",
        created_by="Demo User",
        description="20日动量因子",
        tags=["momentum", "price"],
        status=FactorStatus.ACTIVE
    )
    
    manager.register_factor(
        factor=volume_factor,
        version="1.0.0",
        created_by="Demo User",
        description="20日成交量因子",
        tags=["volume", "liquidity"],
        status=FactorStatus.ACTIVE
    )
    
    # 添加新版本
    print("\n添加因子新版本...")
    momentum_factor_v2 = MomentumFactor(lookback=60)
    momentum_factor_v2.metadata.description = "60日动量因子"
    
    manager.register_factor(
        factor=momentum_factor_v2,
        version="2.0.0",
        created_by="Demo User",
        description="60日动量因子（优化版）",
        tags=["momentum", "price", "long_term"],
        status=FactorStatus.ACTIVE
    )
    
    # 列出因子
    print("\n列出所有因子:")
    factors = manager.list_factors()
    for factor_info in factors:
        print(f"  {factor_info['name']} (v{factor_info['latest_version']}): {factor_info['description']}")
    
    # 搜索因子
    print("\n搜索'动量'因子:")
    search_results = manager.search_factors("动量")
    for result in search_results:
        print(f"  {result['name']}: {result['description']}")
    
    # 获取统计信息
    print("\n因子库统计:")
    stats = manager.get_statistics()
    print(f"  总因子数: {stats['total_factors']}")
    print(f"  总版本数: {stats['total_versions']}")
    print(f"  分类统计: {stats['category_counts']}")
    
    # 保存因子库
    print(f"\n保存因子库到: {temp_dir}")
    manager.save_library()
    
    # 清理临时目录
    import shutil
    shutil.rmtree(temp_dir)
    
    print("演示完成，临时目录已清理")


# ============================================================================
# 7. 完整工作流示例
# ============================================================================

def complete_workflow():
    """完整的工作流示例"""
    print("=" * 60)
    print("完整因子挖掘工作流")
    print("=" * 60)
    
    # 1. 准备数据
    print("\n1. 准备数据...")
    data, future_returns, symbols, dates = prepare_sample_data()
    print(f"   数据形状: {data['close'].shape}")
    
    # 2. 创建因子
    print("\n2. 创建因子...")
    factors = [
        MomentumFactor(lookback=20),
        VolumeFactor(lookback=20),
        MomentumFactor(lookback=60),
        VolumeFactor(lookback=60)
    ]
    
    for factor in factors:
        print(f"   {factor.metadata.name}: {factor.metadata.description}")
    
    # 3. 计算因子
    print("\n3. 计算因子...")
    calculator = FactorCalculator(data_source=DataSource(data))
    for factor in factors:
        calculator.register_factor(factor)
    
    factor_names = [f.metadata.name for f in factors]
    results = calculator.calculate_batch(factor_names, symbols, dates)
    print(f"   计算完成，共 {len(results)} 个因子")
    
    # 4. 检验因子
    print("\n4. 检验因子...")
    best_factor = None
    best_ic = -np.inf
    
    for factor_name, factor_values in results.items():
        validator = FactorValidator(factor_values, future_returns)
        ic = validator.information_coefficient().get('mean', -np.inf)
        
        if ic > best_ic:
            best_ic = ic
            best_factor = factor_name
            
        print(f"   {factor_name}: IC={ic:.4f}")
    
    print(f"\n   最佳因子: {best_factor} (IC={best_ic:.4f})")
    
    # 5. 组合因子
    print("\n5. 组合因子...")
    combiner = FactorCombiner(results, future_returns)
    
    # 选择IC最高的两个因子进行组合
    top_factors = sorted(
        [(name, FactorValidator(results[name], future_returns).information_coefficient().get('mean', -np.inf)) 
         for name in results.keys()],
        key=lambda x: x[1],
        reverse=True
    )[:2]
    
    top_factor_names = [name for name, _ in top_factors]
    print(f"   选择因子: {top_factor_names}")
    
    combined_result = combiner.combine(
        factor_names=top_factor_names,
        method=CombinationMethod.IC_WEIGHT,
        orthogonalization=OrthogonalizationMethod.RESIDUAL
    )
    
    print(f"   组合权重: {combined_result.weights}")
    print(f"   组合IC: {combined_result.metrics.get('ic', 'N/A'):.4f}")
    
    # 6. 管理因子
    print("\n6. 管理因子...")
    import tempfile
    temp_dir = tempfile.mkdtemp()
    
    manager = FactorManager(storage_path=temp_dir)
    for factor in factors:
        manager.register_factor(
            factor=factor,
            created_by="Workflow Demo",
            description=factor.metadata.description,
            status=FactorStatus.ACTIVE
        )
    
    print(f"   因子库已保存，共 {len(manager.list_factors())} 个因子")
    
    # 清理
    import shutil
    shutil.rmtree(temp_dir)
    
    print("\n工作流完成！")


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数"""
    print("ft2.factor 因子挖掘模块演示")
    print("=" * 60)
    
    try:
        # 演示各个组件
        factor_results, future_returns = demo_factor_calculator()
        demo_factor_validator(factor_results, future_returns)
        demo_factor_combiner(factor_results, future_returns)
        demo_factor_manager()
        
        # 完整工作流
        complete_workflow()
        
        print("\n" + "=" * 60)
        print("所有演示完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()