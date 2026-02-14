"""
ft2 - 量化回测框架

模块结构：
- core: 核心回测模块（引擎、存储、账户、分析）
- notebook: Notebook风格输出模块
"""

# 核心模块（兼容旧导入方式）
from .core import (
    engine, Engine,
    context, Context, _Cache,
    account, AccountManager, PositionSnapshot, AccountSnapshot, TradeRecord,
    AccountAnalyzer,
)

# Notebook模块
from .notebook import Notebook, Cell, CellType

__all__ = [
    # 核心
    'engine', 'Engine',
    'context', 'Context', '_Cache',
    'account', 'AccountManager', 'PositionSnapshot', 'AccountSnapshot', 'TradeRecord',
    'AccountAnalyzer',
    # Notebook
    'Notebook', 'Cell', 'CellType',
]
