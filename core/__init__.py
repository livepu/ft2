"""
ft2.core - 核心回测模块

包含：
- engine: 回测引擎
- storage: 数据存储和上下文
- account: 账户管理
- analyzer: 账户分析
"""

from .engine import engine, Engine
from .storage import context, Context, _Cache
from .account import account, AccountManager, PositionSnapshot, AccountSnapshot, TradeRecord
from .analyzer import AccountAnalyzer, TimeRange, metric

__all__ = [
    'engine', 'Engine',
    'context', 'Context', '_Cache',
    'account', 'AccountManager', 'PositionSnapshot', 'AccountSnapshot', 'TradeRecord',
    'AccountAnalyzer', 'Analyzer', 'TimeRange', 'metric',
]
