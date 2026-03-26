"""
简化测试因子模块
"""
import pandas as pd
import numpy as np
from datetime import date, datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from factor import (
    Factor, FactorMetadata, FactorCategory, FactorFrequency,
    FactorCalculator, DataSource, create_sample_data
)

# 创建简单因子
class SimpleTestFactor(Factor):
    """简单测试因子"""
    
    def __init__(self):
        metadata = FactorMetadata(
            name="SimpleTestFactor",
            description="简单测试因子",
            category=FactorCategory.PRICE,
            frequency=FactorFrequency.DAILY
        )
        super().__init__(metadata)
    
    def calculate(self, data: dict, symbols: list, dates: list) -> pd.DataFrame:
        """简单计算：收盘价的对数"""
        print(f"计算因子: symbols={len(symbols)}, dates={len(dates)}")
        print(f"数据字段: {list(data.keys())}")
        
        if 'close' not in data:
            raise ValueError("需要收盘价数据")
            
        close_prices = data['close']
        print(f"收盘价形状: {close_prices.shape}")
        print(f"收盘价前5行:\n{close_prices.head()}")
        
        # 简单计算：对数价格
        factor_values = np.log(close_prices)
        print(f"因子值形状: {factor_values.shape}")
        print(f"因子值有效比例: {factor_values.notna().mean().mean():.2%}")
        
        return factor_values

# 测试
def test_simple():
    print("=" * 60)
    print("简单测试因子计算")
    print("=" * 60)
    
    # 创建少量数据
    symbols = ["STOCK_001", "STOCK_002", "STOCK_003"]
    dates = pd.date_range(start='2024-01-01', end='2024-01-10', freq='B')
    
    print(f"标的: {symbols}")
    print(f"日期: {len(dates)}个交易日")
    
    # 创建示例数据
    data = create_sample_data(symbols, dates, seed=42)
    print(f"数据字段: {list(data.keys())}")
    print(f"收盘价形状: {data['close'].shape}")
    
    # 创建数据源
    data_source = DataSource(data)
    
    # 创建因子计算引擎
    calculator = FactorCalculator(data_source=data_source, max_workers=1, use_cache=False)
    
    # 创建因子实例
    factor = SimpleTestFactor()
    
    # 注册因子
    calculator.register_factor(factor)
    
    # 计算因子
    print("\n计算因子...")
    try:
        result = calculator.calculate_single(
            factor_name="SimpleTestFactor",
            symbols=symbols,
            dates=dates,
            required_fields=['close']
        )
        
        print(f"\n计算结果形状: {result.shape}")
        print(f"计算结果有效比例: {result.notna().mean().mean():.2%}")
        print(f"计算结果前5行:\n{result.head()}")
        
    except Exception as e:
        print(f"计算失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple()