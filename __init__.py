# 从不同模块导入类和函数
from .account import AccountManager,account
from .storage import Context,context
from .engine import Engine  # 这里是类
from .save2html import account_to_html,generate_backtest_report
# 可以在这里定义包级别的变量或函数
__all__ = [
    'AccountManager',
    'account',
    'Context',
    'context',
    'Engine',
    'account_to_html','generate_backtest_report'
]
