"""
ft2 - 量化回测框架

模块结构：
- core: 核心回测模块（引擎、存储、账户、分析）
- notebook: Notebook风格输出模块
"""

# 核心模块
from .core import (
    engine, Engine,
    context,
    account, AccountManager,
    AccountAnalyzer,
    OrderSide, PositionEffect, PositionSide, OrderType,
)

# Notebook模块
from .notebook import Notebook

__all__ = [
    'engine', 'Engine',
    'context',
    'account', 'AccountManager',
    'OrderSide',       # 买卖方向: OrderSide.Buy, OrderSide.Sell
    'PositionEffect',  # 开平标志: PositionEffect.Open, PositionEffect.Close
    'PositionSide',    # 持仓方向: PositionSide.Long, PositionSide.Short
    'OrderType',       # 委托类型: OrderType.Limit, OrderType.Market
    'AccountAnalyzer',
    'Notebook',
]
