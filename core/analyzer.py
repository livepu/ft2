#通过 account 的快照，分析结果
from collections import defaultdict
from dateutil.relativedelta import relativedelta
import math
import os
from datetime import datetime, date
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
import json
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import inspect


@dataclass
class TimeRange:
    """时间区间配置
    
    Attributes:
        start: 开始日期，None 表示使用数据起始日
        end: 结束日期，None 表示使用数据结束日
        period: 时间周期标识，可选值：'1m', '3m', '6m', '1y', '2y', '3y', '5y', 'all'
               如果设置了 period，则 start 和 end 会被自动计算
    """
    start: Optional[date] = None
    end: Optional[date] = None
    period: Optional[str] = None


# ============================================================================
# 账户分析类
# ============================================================================

"""
账户分析器模块

输出规范:
---------
JSON输出结构:
{
    "title": "回测报告",
    "createdAt": "2024-01-01 12:00:00",
    "metrics": [{"name": "指标名", "value": 值, "order": 排序号}, ...],
    "dailyAssets": [{"date": "2024-01-01", "assets": 100000}, ...],
    "trades": [...],
    "topProfits": [...],
    "topLosses": [...]
}

指标分类排序规范:
----------------
order范围    | 类别              | 指标
------------|------------------|------------------
1-9         | 基础信息          | 回测区间、初始资金、最终资产
10-19       | 收益指标          | 累计收益率、年化收益率
20-29       | 风险指标          | 年化波动率、最大回撤、VaR、CVaR、Ulcer Index
30-39       | 风险调整收益指标   | 夏普比率、索提诺比率、UPI
40-49       | 交易分析指标       | 胜率、平均盈亏比、平均持仓时间
50-59       | 仓位建议          | 凯利公式最优仓位、半凯利仓位

新增指标规范:
------------
1. 方法名以 calc_ 开头
2. 计算结果存入 self._metrics，格式: {'name': '中文名', 'value': 值, 'order': 排序号}
3. export_html() 自动调用所有 calc_ 方法并按 order 排序
"""

class AccountAnalyzer:
    """账户分析器，负责计算各类风险收益指标和生成分析报告"""

    def __init__(self, account=None, daily_assets=None):
        """
        初始化账户分析器
        
        支持两种数据输入方式：
        1. 传入 account 实例：自动聚合快照为日数据，并计算交易盈亏
        2. 传入 daily_assets：直接使用外部提供的日数据（不计算交易盈亏）
        
        Args:
            account: AccountManager 实例，提供原始快照数据
                   如果提供，将自动调用 _aggregate_daily_assets 聚合日数据
            daily_assets: 外部每日资产数据，支持两种格式：
                         - List[Dict]: [{'date': date(2024,1,1), 'assets': 100000}, ...]
                         - Dict[date, float]: {date(2024,1,1): 100000, ...}
                        如果提供，将优先使用此数据而非 account 的快照
            
        Example:
            >>> # 方式 1：使用 account 实例
            >>> analyzer = AccountAnalyzer(account=my_account)
            >>> 
            >>> # 方式 2：使用外部日数据（List 格式）
            >>> daily_data = [
            ...     {'date': date(2024, 1, 1), 'assets': 100000},
            ...     {'date': date(2024, 1, 2), 'assets': 101000},
            ... ]
            >>> analyzer = AccountAnalyzer(daily_assets=daily_data)
            >>> 
            >>> # 方式 3：使用外部日数据（Dict 格式）
            >>> daily_dict = {date(2024,1,1): 100000, date(2024,1,2): 101000}
            >>> analyzer = AccountAnalyzer(daily_assets=daily_dict)
        """
        self.account = account
        self._metrics = {}
        
        if daily_assets is not None:
            if isinstance(daily_assets, dict):
                self._daily_assets = daily_assets
            else:
                self._daily_assets = {item['date']: item['assets'] for item in daily_assets}
            self._trade_profits = []
        elif account:
            self._daily_assets = self._aggregate_daily_assets(account.snapshots)
            self._trade_profits = self._calculate_profit(account._trade_records)
        else:
            self._daily_assets = {}
            self._trade_profits = []

        self.base_dir = self._get_caller_dir()

    @property
    def daily_assets(self) -> Dict:
        """
        获取每日资产净值的副本
        
        返回内部存储的每日资产数据的浅拷贝，防止外部修改
        数据格式：{date: nav}
        
        Returns:
            Dict[date, float]: 每日资产净值字典的副本
            
        Example:
            >>> assets = analyzer.daily_assets
            >>> print(f"最新资产：{assets[max(assets.keys())]}")
        """
        return self._daily_assets.copy()

    @property
    def trade_profits(self) -> List:
        """
        获取交易盈亏记录的副本
        
        返回内部存储的交易盈亏数据的浅拷贝，防止外部修改
        每笔交易记录包含：symbol, profit, open_time, close_time 等信息
        
        Returns:
            List[Dict]: 交易盈亏记录列表的副本
            
        Example:
            >>> profits = analyzer.trade_profits
            >>> total_profit = sum(t['profit'] for t in profits)
            >>> print(f"总盈利：{total_profit}")
        """
        return self._trade_profits.copy()

    # ------------------------------------------------------------------------
    # 统一指标获取方法
    # ------------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Dict]:
        """
        获取所有已计算的指标
        
        返回所有以 calc_ 开头的方法计算并存储的指标结果
        
        Returns:
            Dict[str, Dict]: 指标字典，格式为：
                {
                    'calc_return_rate': {
                        'name': '累计收益率',
                        'value': 0.15,
                        'order': 10,
                        'desc': '统计期间内的总收益率'
                    },
                    ...
                }
            
        Example:
            >>> analyzer.calc_return_rate()
            >>> metrics = analyzer.get_metrics()
            >>> print(metrics['calc_return_rate']['value'])
        """
        return self._metrics.copy()

    # ------------------------------------------------------------------------
    # 收益指标
    # ------------------------------------------------------------------------

    def calc_return_rate(self, time_range: TimeRange = None) -> float:
        """
        计算累计收益率
        
        计算公式：(期末资产 - 期初资产) / 期初资产
        
        Args:
            time_range: TimeRange 对象，指定统计区间。
                       None 表示使用全部数据（从第一个交易日到最后一个交易日）
            
        Returns:
            float: 收益率（小数形式，如 0.15 表示 15%）
                  数据不足时返回 None
            
        Raises:
            ValueError: 当初始资产为零时抛出
            
        Example:
            >>> analyzer.calc_return_rate()  # 全部区间
            >>> analyzer.calc_return_rate(TimeRange(period='3m'))  # 最近 3 个月
            >>> analyzer.calc_return_rate(TimeRange(start=date(2024,1,1), end=date(2024,3,31)))
        """
        sliced_data = self._slice_data_by_range(time_range)
        if len(sliced_data) < 2:
            return None

        dates = sorted(sliced_data.keys())
        start_value = sliced_data[dates[0]]
        end_value = sliced_data[dates[-1]]
        
        if start_value == 0:
            raise ValueError("初始资产不能为零")
        value = (end_value - start_value) / start_value
        self._metrics['calc_return_rate'] = {'name': '累计收益率', 'value': value, 'order': 10, 'desc': '统计期间内的总收益率'}
        return value

    def calc_annualized_return(self, time_range: TimeRange = None) -> float:
        """
        计算年化收益率
        
        将统计期间的收益率换算为年化基准，便于不同期限收益的比较
        
        计算公式：(1 + 期间收益率) ^ (365 / 持仓天数) - 1
        
        Args:
            time_range: TimeRange 对象，指定统计区间
            
        Returns:
            float: 年化收益率（小数形式）
                  数据不足时返回 None
            
        Raises:
            ValueError: 当亏损超过 100% 时无法计算年化
            
        Example:
            >>> analyzer.calc_annualized_return(TimeRange(period='1y'))
        """
        interval_return = self.calc_return_rate(time_range)
        if interval_return is None:
            return None

        sliced_data = self._slice_data_by_range(time_range)
        dates = sorted(sliced_data.keys())
        days = (dates[-1] - dates[0]).days
        
        if days == 0:
            value = 0
        elif interval_return <= -1:
            raise ValueError("亏损超过 100%，无法计算年化收益率")
        else:
            value = ((1 + interval_return) ** (365 / days)) - 1
        self._metrics['calc_annualized_return'] = {'name': '年化收益率', 'value': value, 'order': 11, 'desc': '将收益率换算为年化基准'}
        return value

    # ------------------------------------------------------------------------
    # 风险指标
    # ------------------------------------------------------------------------

    def calc_volatility(self, time_range: TimeRange = None) -> float:
        """
        计算年化波动率
        
        波动率衡量资产价格的波动程度，是风险的重要指标
        
        计算公式：日收益率标准差 × √252（年化因子）
        
        Args:
            time_range: TimeRange 对象，指定统计区间
            
        Returns:
            float: 年化波动率（小数形式，如 0.2 表示 20%）
                  数据不足时返回 None
            
        Raises:
            ValueError: 至少需要 2 个数据点才能计算
            
        Example:
            >>> analyzer.calc_volatility(TimeRange(period='6m'))
        """
        sliced_data = self._slice_data_by_range(time_range)
        if len(sliced_data) < 2:
            return None

        daily_returns = self._calculate_daily_returns(sliced_data)

        if len(daily_returns) < 2:
            raise ValueError("至少需要 2 个数据点计算波动率")
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
        daily_volatility = math.sqrt(variance)
        value = daily_volatility * math.sqrt(252)
        self._metrics['calc_volatility'] = {'name': '年化波动率', 'value': value, 'order': 20}
        return value

    def calc_max_drawdown(self, time_range: TimeRange = None) -> Tuple[float, date, date]:
        """
        计算最大回撤
        
        最大回撤是历史上从最高点下跌的最大幅度，反映最坏情况下的亏损程度
        
        计算方法：遍历所有交易日，记录峰值，计算当前值相对峰值的下跌幅度
        
        Args:
            time_range: TimeRange 对象，指定统计区间
                       None 表示使用全部数据
            
        Returns:
            Tuple[float, date, date]: 
                - 最大回撤比例（小数形式，如 0.3 表示 30%）
                - 回撤开始日期（峰值日期）
                - 回撤结束日期（最低点日期）
                如果无回撤数据，返回 (0, None, None)
            
        Example:
            >>> drawdown, start, end = analyzer.calc_max_drawdown()
            >>> print(f"最大回撤：{drawdown:.2%}，从{start}到{end}")
            >>> 
            >>> # 计算最近 6 个月的最大回撤
            >>> drawdown, start, end = analyzer.calc_max_drawdown(TimeRange(period='6m'))
        """
        # 使用 _slice_data_by_range 处理时间区间
        sliced_data = self._slice_data_by_range(time_range)
        if not sliced_data:
            return 0, None, None

        dates = sorted(sliced_data.keys())
        max_drawdown = 0
        peak_value = sliced_data[dates[0]]
        start_date = end_date = peak_date = dates[0]

        for current_date in dates:
            current_value = sliced_data[current_date]
            if current_value > peak_value:
                peak_value = current_value
                peak_date = current_date
            drawdown = (peak_value - current_value) / peak_value
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                start_date = peak_date
                end_date = current_date
        if max_drawdown == 0:
            return 0, None, None
        self._metrics['calc_max_drawdown'] = {
            'name': '最大回撤', 
            'value': max_drawdown,
            'start': start_date,
            'end': end_date,
            'order': 21,
            'desc': '历史最大亏损幅度'
        }
        return max_drawdown, start_date, end_date

    def calc_var(self, confidence: float = 0.95, time_range: TimeRange = None) -> float:
        """
        计算风险价值 (Value at Risk, VaR)
        
        VaR 表示在给定置信水平下的最大可能损失，是常用的风险度量指标
        
        计算方法：历史模拟法，取日收益率分布的分位数
        
        Args:
            confidence: 置信水平，默认 0.95（95%）
                       表示 95% 的情况下损失不会超过 VaR 值
            time_range: TimeRange 对象，指定统计区间
            
        Returns:
            float: VaR 值（正数，表示最大可能损失的比例）
                  数据不足时返回 None
            
        Example:
            >>> analyzer.calc_var(confidence=0.95)  # 95% 置信度
        """
        sliced_data = self._slice_data_by_range(time_range)
        daily_returns = self._calculate_daily_returns(sliced_data)

        if len(daily_returns) < 2:
            return None

        sorted_returns = sorted(daily_returns)
        index = int((1 - confidence) * len(sorted_returns))
        if index < 0:
            index = 0

        var = -sorted_returns[index]
        self._metrics['calc_var'] = {'name': 'VaR(95%)', 'value': var, 'order': 22, 'desc': '95% 置信度下的最大可能损失'}
        return var

    def calc_cvar(self, confidence: float = 0.95, time_range: TimeRange = None) -> float:
        """
        计算条件风险价值 (Conditional VaR, CVaR)
        
        CVaR 是超过 VaR 阈值的平均损失，比 VaR 更能反映极端风险
        
        计算方法：取收益率分布尾部（最差情况）的平均值
        
        Args:
            confidence: 置信水平，默认 0.95（95%）
                       计算最差的 5% 情况的平均损失
            time_range: TimeRange 对象，指定统计区间
            
        Returns:
            float: CVaR 值（正数，表示极端情况下的平均损失）
                  数据不足时返回 None
            
        Example:
            >>> analyzer.calc_cvar(confidence=0.95)  # 尾部 5% 的平均损失
        """
        sliced_data = self._slice_data_by_range(time_range)
        daily_returns = self._calculate_daily_returns(sliced_data)

        if len(daily_returns) < 2:
            return None

        sorted_returns = sorted(daily_returns)
        index = int((1 - confidence) * len(sorted_returns))
        if index < 1:
            index = 1

        tail_returns = sorted_returns[:index]
        cvar = -sum(tail_returns) / len(tail_returns)
        self._metrics['calc_cvar'] = {'name': 'CVaR(95%)', 'value': cvar, 'order': 23, 'desc': '超过 VaR 阈值的平均损失'}
        return cvar

    def calc_ulcer_index(self, time_range: TimeRange = None) -> float:
        """
        计算溃疡指数 (Ulcer Index)
        
        Ulcer Index 衡量回撤的深度和持续时间，综合反映投资痛苦程度
        相比最大回撤，它考虑了回撤的持续时间
        
        计算方法：计算每个时点相对峰值的回撤百分比的平方平均再开方
        
        Args:
            time_range: TimeRange 对象，指定统计区间
            
        Returns:
            float: Ulcer Index 值（百分比形式，如 15 表示 15%）
                  数据不足时返回 None
            
        Example:
            >>> analyzer.calc_ulcer_index(TimeRange(period='1y'))
        """
        sliced_data = self._slice_data_by_range(time_range)
        dates = sorted(sliced_data.keys())

        if len(dates) < 2:
            return None

        peak = sliced_data[dates[0]]
        squared_drawdowns = []

        for current_date in dates:
            value = sliced_data[current_date]
            if value > peak:
                peak = value
            drawdown_pct = (peak - value) / peak * 100
            squared_drawdowns.append(drawdown_pct ** 2)

        ulcer_index = math.sqrt(sum(squared_drawdowns) / len(squared_drawdowns))
        self._metrics['calc_ulcer_index'] = {'name': 'Ulcer Index', 'value': ulcer_index, 'order': 24, 'desc': '衡量回撤深度和持续时间的综合指标'}
        return ulcer_index

    # ------------------------------------------------------------------------
    # 风险调整收益指标
    # ------------------------------------------------------------------------

    def calc_sharpe_ratio(self, risk_free_rate: float = 0.02, time_range: TimeRange = None) -> float:
        """
        计算夏普比率 (Sharpe Ratio)
        
        夏普比率衡量每承担一单位风险所获得的超额收益，是最经典的风险调整收益指标
        
        计算公式：(年化收益率 - 无风险利率) / 年化波动率
        
        Args:
            risk_free_rate: 无风险利率，默认 0.02（2%）
                           通常使用国债收益率作为无风险利率
            time_range: TimeRange 对象，指定统计区间
            
        Returns:
            float: 夏普比率
                  数据不足时返回 None
                  比率越高，说明风险调整后的收益越好
            
        Example:
            >>> analyzer.calc_sharpe_ratio(risk_free_rate=0.03)  # 使用 3% 无风险利率
        """
        annualized_return = self.calc_annualized_return(time_range)
        volatility = self.calc_volatility(time_range)

        if annualized_return is None or volatility is None:
            return None

        value = (annualized_return - risk_free_rate) / volatility
        self._metrics['calc_sharpe_ratio'] = {'name': '夏普比率', 'value': value, 'order': 30, 'desc': '每承担一单位风险获得的超额收益'}
        return value

    def calc_sortino_ratio(self, risk_free_rate: float = 0.02, time_range: TimeRange = None) -> float:
        """
        计算索提诺比率 (Sortino Ratio)
        
        索提诺比率是夏普比率的改进版，只考虑下行风险（负收益的波动）
        更适合评估不希望错过上涨机会的投资者
        
        计算公式：(年化收益率 - 无风险利率) / 下行标准差
        
        Args:
            risk_free_rate: 无风险利率，默认 0.02（2%）
            time_range: TimeRange 对象，指定统计区间
            
        Returns:
            float: 索提诺比率
                  数据不足时返回 None
                  如果无负收益，返回无穷大（float('inf')）
                  比率越高，说明下行风险调整后的收益越好
            
        Example:
            >>> analyzer.calc_sortino_ratio()
        """
        annualized_return = self.calc_annualized_return(time_range)
        if annualized_return is None:
            return None

        sliced_data = self._slice_data_by_range(time_range)
        daily_returns = self._calculate_daily_returns(sliced_data)

        if len(daily_returns) < 2:
            return None

        negative_returns = [r for r in daily_returns if r < 0]
        if not negative_returns:
            return float('inf')

        downside_variance = sum(r ** 2 for r in negative_returns) / len(daily_returns)
        downside_deviation = math.sqrt(downside_variance)
        annualized_downside_deviation = downside_deviation * math.sqrt(252)

        if annualized_downside_deviation == 0:
            return float('inf')

        value = (annualized_return - risk_free_rate) / annualized_downside_deviation
        self._metrics['calc_sortino_ratio'] = {'name': '索提诺比率', 'value': value, 'order': 31, 'desc': '只考虑下行风险的夏普比率改进版'}
        return value

    def calc_upi(self, risk_free_rate: float = 0.02, time_range: TimeRange = None) -> float:
        """
        计算 Ulcer Performance Index (UPI)
        
        UPI 使用 Ulcer Index 代替波动率，衡量单位"痛苦"下的超额收益
        比夏普比率更能反映投资者的真实感受
        
        计算公式：(年化收益率 - 无风险利率) / Ulcer Index
        
        Args:
            risk_free_rate: 无风险利率，默认 0.02（2%）
            time_range: TimeRange 对象，指定统计区间
            
        Returns:
            float: UPI 值
                  数据不足或 Ulcer Index 为 0 时返回 None
                  值越高，说明单位痛苦下的收益越好
            
        Example:
            >>> analyzer.calc_upi()
        """
        annualized_return = self.calc_annualized_return(time_range)
        ulcer_index = self.calc_ulcer_index(time_range)

        if annualized_return is None or ulcer_index is None or ulcer_index == 0:
            return None

        value = (annualized_return - risk_free_rate) / (ulcer_index / 100)
        self._metrics['calc_upi'] = {'name': 'UPI', 'value': value, 'order': 32, 'desc': '用溃疡指数调整的风险收益比'}
        return value

    # ------------------------------------------------------------------------
    # 交易分析指标
    # ------------------------------------------------------------------------

    def calc_win_rate(self, time_range: TimeRange = None) -> float:
        """
        计算胜率
        
        胜率是盈利交易次数占总交易次数的比例，反映交易策略的准确性
        
        计算公式：盈利交易次数 / 总交易次数
        
        Args:
            time_range: TimeRange 对象，指定统计区间
                       None 表示使用全部交易记录
            
        Returns:
            float: 胜率（小数形式，如 0.6 表示 60%）
                  无交易记录时返回 None
            
        Example:
            >>> analyzer.calc_win_rate()  # 全部交易
            >>> analyzer.calc_win_rate(TimeRange(period='3m'))  # 最近 3 个月的交易
        """
        if not self._trade_profits:
            return None
        
        # 如果指定了时间区间，需要过滤交易记录
        if time_range is not None:
            sliced_data = self._slice_data_by_range(time_range)
            if not sliced_data:
                return None
            # 过滤出在时间区间内平仓的交易
            start_date = min(sliced_data.keys())
            end_date = max(sliced_data.keys())
            filtered_trades = [
                t for t in self._trade_profits
                if start_date <= t['close_time'].date() <= end_date
            ]
            if not filtered_trades:
                return None
            trades_to_calc = filtered_trades
        else:
            trades_to_calc = self._trade_profits
        
        wins = sum(1 for t in trades_to_calc if t['profit'] > 0)
        value = wins / len(trades_to_calc)
        self._metrics['calc_win_rate'] = {'name': '胜率', 'value': value, 'order': 40, 'desc': '盈利交易次数占总交易次数的比例'}
        return value

    def calc_avg_profit(self, mode: str = 'amount', time_range: TimeRange = None) -> float:
        """
        计算平均盈利
        
        统计所有盈利交易的平均值，可用于计算盈亏比
        
        Args:
            mode: 计算模式
                  - 'amount': 金额模式，计算平均盈利金额
                  - 'percentage': 百分比模式，计算平均盈利占本金的比例
            time_range: TimeRange 对象，指定统计区间
                       None 表示使用全部交易记录
            
        Returns:
            float: 平均盈利
                  无盈利交易时返回 None
            
        Example:
            >>> analyzer.calc_avg_profit(mode='amount')  # 平均盈利金额
            >>> analyzer.calc_avg_profit(mode='percentage')  # 平均盈利百分比
            >>> analyzer.calc_avg_profit(time_range=TimeRange(period='3m'))  # 最近 3 个月
        """
        profitable_trades = [t for t in self._trade_profits if t['profit'] > 0]
        if not profitable_trades:
            return None

        # 如果指定了时间区间，需要过滤交易记录
        if time_range is not None:
            sliced_data = self._slice_data_by_range(time_range)
            if not sliced_data:
                return None
            start_date = min(sliced_data.keys())
            end_date = max(sliced_data.keys())
            profitable_trades = [
                t for t in profitable_trades
                if start_date <= t['close_time'].date() <= end_date
            ]
            if not profitable_trades:
                return None

        if mode == 'amount':
            profits = [t['profit'] for t in profitable_trades]
        elif mode == 'percentage':
            profits = [
                t['profit'] / (abs(t['volume']) * t['open_price'])
                for t in profitable_trades
            ]
        else:
            raise ValueError("mode 必须是 'amount' 或 'percentage'")

        return sum(profits) / len(profits)

    def calc_avg_loss(self, mode: str = 'amount', time_range: TimeRange = None) -> float:
        """
        计算平均亏损
        
        统计所有亏损交易的平均值，可用于计算盈亏比
        
        Args:
            mode: 计算模式
                  - 'amount': 金额模式，计算平均亏损金额
                  - 'percentage': 百分比模式，计算平均亏损占本金的比例
            time_range: TimeRange 对象，指定统计区间
                       None 表示使用全部交易记录
            
        Returns:
            float: 平均亏损（负数）
                  无亏损交易时返回 None
            
        Example:
            >>> analyzer.calc_avg_loss(mode='amount')  # 平均亏损金额
            >>> analyzer.calc_avg_loss(time_range=TimeRange(period='6m'))  # 最近 6 个月
        """
        loss_trades = [t for t in self._trade_profits if t['profit'] < 0]
        if not loss_trades:
            return None

        # 如果指定了时间区间，需要过滤交易记录
        if time_range is not None:
            sliced_data = self._slice_data_by_range(time_range)
            if not sliced_data:
                return None
            start_date = min(sliced_data.keys())
            end_date = max(sliced_data.keys())
            loss_trades = [
                t for t in loss_trades
                if start_date <= t['close_time'].date() <= end_date
            ]
            if not loss_trades:
                return None

        if mode == 'amount':
            losses = [t['profit'] for t in loss_trades]
        elif mode == 'percentage':
            losses = [
                t['profit'] / (abs(t['volume']) * t['open_price'])
                for t in loss_trades
            ]
        else:
            raise ValueError("mode 必须是 'amount' 或 'percentage'")

        return sum(losses) / len(losses)

    def calc_avg_profit_loss_ratio(self, mode: str = 'amount', time_range: TimeRange = None) -> float:
        """
        计算平均盈亏比
        
        盈亏比是平均盈利与平均亏损的比值，反映策略的盈利能力
        比值大于 1 表示盈利时赚的钱多于亏损时赔的钱
        
        计算公式：|平均盈利 / 平均亏损|
        
        Args:
            mode: 计算模式
                  - 'amount': 金额模式
                  - 'percentage': 百分比模式
            time_range: TimeRange 对象，指定统计区间
                       None 表示使用全部交易记录
            
        Returns:
            float: 平均盈亏比
                  数据不足时返回 None
            
        Example:
            >>> analyzer.calc_avg_profit_loss_ratio()  # 通常使用金额模式
            >>> analyzer.calc_avg_profit_loss_ratio(time_range=TimeRange(period='1y'))  # 最近 1 年
        """
        avg_profit = self.calc_avg_profit(mode, time_range)
        avg_loss = self.calc_avg_loss(mode, time_range)

        if avg_profit is None or avg_loss is None:
            return None

        value = abs(avg_profit / avg_loss)
        self._metrics['calc_avg_profit_loss_ratio'] = {'name': '平均盈亏比', 'value': value, 'order': 41, 'desc': '平均盈利与平均亏损的比值'}
        return value

    def calc_avg_holding_period(self, time_range: TimeRange = None) -> float:
        """
        计算平均持仓时间
        
        统计所有交易的平均持仓天数，反映策略的交易频率
        
        计算公式：总持仓天数 / 交易次数
        
        Args:
            time_range: TimeRange 对象，指定统计区间
                       None 表示使用全部交易记录
            
        Returns:
            float: 平均持仓天数
                  无交易记录时返回 None
            
        Example:
            >>> analyzer.calc_avg_holding_period()  # 全部交易
            >>> analyzer.calc_avg_holding_period(TimeRange(period='6m'))  # 最近 6 个月
        """
        if not self._trade_profits:
            return None
        
        # 如果指定了时间区间，需要过滤交易记录
        if time_range is not None:
            sliced_data = self._slice_data_by_range(time_range)
            if not sliced_data:
                return None
            start_date = min(sliced_data.keys())
            end_date = max(sliced_data.keys())
            filtered_trades = [
                t for t in self._trade_profits
                if start_date <= t['close_time'].date() <= end_date
            ]
            if not filtered_trades:
                return None
            trades_to_calc = filtered_trades
        else:
            trades_to_calc = self._trade_profits
        
        total_days = sum((t['close_time'] - t['open_time']).days for t in trades_to_calc)
        value = total_days / len(trades_to_calc)
        self._metrics['calc_avg_holding_period'] = {'name': '平均持仓时间', 'value': value, 'order': 42}
        return value

    def calc_kelly_criterion(self, time_range: TimeRange = None) -> float:
        """
        计算凯利公式最优仓位
        
        凯利公式根据胜率和盈亏比计算最优仓位比例，最大化长期复利收益
        
        计算公式：Kelly = WinRate - (1 - WinRate) / ProfitLossRatio
        
        Args:
            time_range: TimeRange 对象（暂未使用，保留用于接口统一）
            
        Returns:
            float: 凯利最优仓位比例（小数形式，如 0.3 表示 30% 仓位）
                  数据不足时返回 None
                  负值表示不应参与该策略
            
        Example:
            >>> analyzer.calc_kelly_criterion()
            >>> # 结果解释：0.3 表示最优仓位为 30%
        """
        if not self._trade_profits:
            return None

        win_rate = self.calc_win_rate()
        if win_rate is None:
            return None

        avg_profit = self.calc_avg_profit(mode='amount')
        avg_loss = self.calc_avg_loss(mode='amount')

        if avg_profit is None or avg_loss is None or avg_loss == 0:
            return None

        profit_loss_ratio = abs(avg_profit / avg_loss)

        kelly = win_rate - (1 - win_rate) / profit_loss_ratio
        self._metrics['calc_kelly_criterion'] = {'name': '凯利公式最优仓位', 'value': kelly, 'order': 50, 'desc': '根据胜率和盈亏比计算的最优仓位比例'}
        return kelly

    def calc_kelly_fraction(self, fraction: float = 0.5, time_range: TimeRange = None) -> float:
        """
        计算凯利分数仓位
        
        由于全凯利仓位波动较大，实践中常使用分数凯利（如半凯利）
        在保留大部分收益的同时显著降低波动
        
        计算公式：仓位 = Kelly × fraction
        
        Args:
            fraction: 凯利分数，默认 0.5（半凯利）
                     常用值：0.5（半凯利）、0.25（四分之一凯利）
            time_range: TimeRange 对象（暂未使用，保留用于接口统一）
            
        Returns:
            float: 凯利分数仓位比例
                  数据不足时返回 None
            
        Example:
            >>> analyzer.calc_kelly_fraction(fraction=0.5)  # 半凯利仓位
            >>> analyzer.calc_kelly_fraction(fraction=0.25)  # 四分之一凯利
        """
        kelly = self.calc_kelly_criterion(time_range)
        if kelly is None:
            return None
        value = kelly * fraction
        self._metrics['calc_kelly_fraction'] = {'name': '半凯利仓位', 'value': value, 'order': 51}
        return value

    # ------------------------------------------------------------------------
    # 查询方法
    # ------------------------------------------------------------------------

    def get_daily_total_assets(self) -> Dict:
        """
        获取每日资产净值
        
        返回聚合后的每日资产数据，可用于绘制净值曲线
        
        Returns:
            Dict[date, float]: {日期：资产净值} 字典
                              日期为 date 对象，净值为 float
            
        Example:
            >>> assets = analyzer.get_daily_total_assets()
            >>> for date, value in sorted(assets.items()):
            ...     print(f"{date}: {value}")
        """
        return self._daily_assets

    def get_largest_profit_trades(self, n: int) -> List:
        """
        获取盈利最大的 N 笔交易
        
        按盈利金额降序排序，返回前 N 笔交易记录
        
        Args:
            n: 返回的交易数量
            
        Returns:
            List[Dict]: 交易记录列表，每笔交易包含：
                       - symbol: 标的代码
                       - profit: 盈亏金额
                       - open_time, close_time: 开平仓时间
                       - open_price, close_price: 开平仓价格
                       - volume: 交易数量
                       按盈利降序排序
            
        Example:
            >>> top5 = analyzer.get_largest_profit_trades(5)
            >>> for trade in top5:
            ...     print(f"{trade['symbol']}: 盈利 {trade['profit']}")
        """
        if not self._trade_profits or n <= 0:
            return []
        return sorted(self._trade_profits, key=lambda t: t['profit'], reverse=True)[:n]

    def get_largest_loss_trades(self, n: int) -> List:
        """
        获取亏损最大的 N 笔交易
        
        按亏损金额升序排序（亏损最多的在前），返回前 N 笔交易记录
        用于分析策略的失败案例，找出需要改进的地方
        
        Args:
            n: 返回的交易数量
            
        Returns:
            List[Dict]: 交易记录列表，按亏损升序排序
                       （亏损最多的交易在最前面）
            
        Example:
            >>> worst5 = analyzer.get_largest_loss_trades(5)
            >>> for trade in worst5:
            ...     print(f"{trade['symbol']}: 亏损 {abs(trade['profit'])}")
        """
        if not self._trade_profits or n <= 0:
            return []
        return sorted(self._trade_profits, key=lambda t: t['profit'])[:n]

    # ------------------------------------------------------------------------
    # 导出方法
    # ------------------------------------------------------------------------

    def export_html(self, report_name: str = "回测报告", output_dir: str = ".", time_range: TimeRange = None):
        """
        导出 HTML 回测报告
        
        生成包含所有指标、每日资产曲线、交易记录的 HTML 报告
        自动调用所有 calc_ 方法计算指标，并按 order 排序
        
        Args:
            report_name: 报告名称，用于生成文件名
                        格式：{report_name}_{YYYYMMDD_HHMM}.html
            output_dir: 输出目录（相对路径，基于调用者所在目录）
                       默认为 "." 表示调用者当前目录
            time_range: TimeRange 对象，指定统计区间
                       None 表示使用全部数据
            
        Output:
            生成 HTML 文件，包含：
            - 基础信息：开始日期、结束日期、初始资金、最终资产
            - 收益指标：累计收益率、年化收益率
            - 风险指标：波动率、最大回撤、VaR、CVaR、Ulcer Index
            - 风险调整收益：夏普比率、索提诺比率、UPI
            - 交易分析：胜率、平均盈亏比、平均持仓时间、凯利仓位
            - 每日资产曲线数据
            - 全部交易记录
            - 盈利最大和亏损最大的前 20 笔交易
            
        Example:
            >>> # 导出全部区间的报告
            >>> analyzer.export_html("策略回测")
            >>> 
            >>> # 导出最近 6 个月的报告
            >>> analyzer.export_html("近 6 月表现", time_range=TimeRange(period='6m'))
            >>> 
            >>> # 导出到指定目录
            >>> analyzer.export_html("年度报告", output_dir="reports/2024")
        """
        for name in dir(self):
            if name.startswith('calc_'):
                method = getattr(self, name)
                if callable(method):
                    try:
                        method(time_range=time_range)
                    except Exception:
                        pass

        initial_cash = self.account.snapshots[0].cash if self.account.snapshots else 0
        final_assets = self.account.snapshots[-1].nav if self.account.snapshots else 0

        dates = sorted(self._daily_assets.keys())
        start_date = dates[1] if len(dates) > 1 else None
        end_date = dates[-1] if dates else None

        metrics = [
            {"name": "开始日期", "value": start_date.strftime('%Y-%m-%d') if start_date else 'N/A', "order": 1, "desc": "回测起始日期，前一交易日收盘作为基准"},
            {"name": "结束日期", "value": end_date.strftime('%Y-%m-%d') if end_date else 'N/A', "order": 2, "desc": "回测结束日期"},
            {"name": "初始资金", "value": initial_cash, "order": 3, "desc": "回测开始时投入的资金"},
            {"name": "最终资产", "value": final_assets, "order": 4, "desc": "回测结束时的总资产"},
        ]
        for method_name, data in self._metrics.items():
            metrics.append({
                "name": data['name'], 
                "value": data['value'],
                "order": data.get('order', 99),
                "desc": data.get('desc', '')
            })
        
        metrics.sort(key=lambda x: x['order'])

        data = {
            'title': report_name,
            'createdAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'metrics': metrics,
            'dailyAssets': [
                {'date': d.strftime('%Y-%m-%d'), 'assets': v} 
                for d, v in self._daily_assets.items()
            ],
            'trades': [self._to_dict(t) for t in self.account._trade_records],
            'topProfits': [self._to_dict(t, exclude='original_trade') for t in self.get_largest_profit_trades(20)],
            'topLosses': [self._to_dict(t, exclude='original_trade') for t in self.get_largest_loss_trades(20)],
        }

        current_file_path = Path(__file__).resolve()
        template_dir = current_file_path.parent.parent / "template"

        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("analyzer.html")

        html_content = template.render(data=json.dumps(data, ensure_ascii=False, default=str))

        current_datetime = datetime.now().strftime("%Y%m%d_%H%M")
        output_path = Path(self.base_dir) / output_dir / f"{report_name}_{current_datetime}.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"报告已生成至: {output_path}")

    # ------------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------------

    @staticmethod
    def _to_dict(obj, exclude: str = None) -> dict:
        """
        将对象转换为可 JSON 序列化的字典
        
        支持普通对象、字典、以及嵌套对象的转换
        用于序列化交易记录等对象以便 JSON 导出
        
        Args:
            obj: 要转换的对象或字典
            exclude: 要排除的字段名（可选）
                    用于过滤不需要序列化的字段，如 'original_trade'
            
        Returns:
            dict: 转换后的字典，可直接用于 JSON 序列化
            
        Example:
            >>> obj = TradeRecord(...)
            >>> d = analyzer._to_dict(obj)
            >>> d_no_original = analyzer._to_dict(obj, exclude='original_trade')
        """
        if hasattr(obj, '__dict__'):
            d = obj.__dict__
        elif isinstance(obj, dict):
            d = obj
        else:
            return obj
        
        if exclude:
            return {k: v for k, v in d.items() if k != exclude}
        return dict(d)

    @staticmethod
    def _aggregate_daily_assets(snapshots: List) -> Dict:
        """
        聚合账户快照为日数据（每日取最后一个快照）
        
        账户类每次交易都会生成快照，一天内可能有多次交易
        此方法将日内多个快照聚合为每日一个数据点，取最后一个快照的资产值
        
        Args:
            snapshots: AccountSnapshot 对象列表
                      每个快照包含 created_at（datetime）和 nav（资产净值）
            
        Returns:
            Dict[date, float]: {日期：资产净值} 字典
                              日期为 date 对象，资产净值为 float
            
        Example:
            >>> daily = AccountAnalyzer._aggregate_daily_assets(account.snapshots)
            >>> # 结果：{date(2024, 1, 1): 100000, date(2024, 1, 2): 101500, ...}
        """
        daily_snapshots = defaultdict(list)
        for snapshot in snapshots:
            snapshot_date = snapshot.created_at.date()
            daily_snapshots[snapshot_date].append(snapshot)

        return {
            snapshot_date: snaps[-1].nav
            for snapshot_date, snaps in daily_snapshots.items()
        }

    def _slice_data_by_range(self, time_range: TimeRange = None) -> Dict[date, float]:
        """
        根据时间区间截取数据
        
        核心功能：
        1. 支持三种方式指定区间：直接设置 start/end、使用预设 period、使用全部数据
        2. 处理基准日逻辑：如果开始日早于第一个交易日，使用 date[1] 作为开始日
        3. 返回截取后的资产数据字典，供其他 calc_ 方法使用
        
        Args:
            time_range: TimeRange 对象，包含以下配置：
                       - start: 开始日期，None 表示使用数据起始日
                       - end: 结束日期，None 表示使用数据结束日
                       - period: 时间周期标识，可选值：
                                '1m', '3m', '6m', '1y', '2y', '3y', '5y', 'all'
            
        Returns:
            Dict[date, float]: 截取后的资产数据 {日期：资产净值}
            
        基准日逻辑说明：
            - 回测开始日的前一交易日作为基准日（即 date[0]）
            - 如果 time_range.start 早于基准日的下一交易日（date[1]），
              使用 date[1] 作为实际开始日
            - 这样可以确保有足够的历史数据计算收益率
            
        Example:
            >>> # 使用预设周期
            >>> data = analyzer._slice_data_by_range(TimeRange(period='3m'))
            >>> 
            >>> # 使用自定义日期范围
            >>> data = analyzer._slice_data_by_range(
            ...     TimeRange(start=date(2024,1,1), end=date(2024,3,31))
            ... )
        """
        if not self._daily_assets:
            return {}
        
        dates = sorted(self._daily_assets.keys())
        if len(dates) < 2:
            return self._daily_assets.copy()
        
        benchmark_date = dates[0]
        first_trading_date = dates[1]
        
        if time_range is None:
            start_date = first_trading_date
            end_date = dates[-1]
        elif time_range.period:
            periods = {
                '1m': relativedelta(months=1),
                '3m': relativedelta(months=3),
                '6m': relativedelta(months=6),
                '1y': relativedelta(years=1),
                '2y': relativedelta(years=2),
                '3y': relativedelta(years=3),
                '5y': relativedelta(years=5),
                'all': None
            }
            
            if time_range.period == 'all':
                start_date = first_trading_date
                end_date = dates[-1]
            else:
                delta = periods.get(time_range.period)
                if delta is None:
                    start_date = first_trading_date
                    end_date = dates[-1]
                else:
                    calculated_start = dates[-1] - delta
                    start_date = max(d for d in dates if d <= calculated_start) if any(d <= calculated_start for d in dates) else first_trading_date
                    end_date = dates[-1]
        else:
            start_date = time_range.start if time_range.start else first_trading_date
            end_date = time_range.end if time_range.end else dates[-1]
        
        if start_date < first_trading_date:
            start_date = first_trading_date
        
        sliced_data = {
            d: v for d, v in self._daily_assets.items()
            if start_date <= d <= end_date
        }
        
        return sliced_data

    def _calculate_daily_returns(self, daily_assets: Dict) -> List:
        """
        计算日收益率序列
        
        根据每日资产数据计算相邻交易日之间的收益率
        用于计算波动率、VaR、CVaR 等风险指标
        
        计算公式：(今日资产 - 昨日资产) / 昨日资产
        
        Args:
            daily_assets: 每日资产字典 {date: nav}
            
        Returns:
            List[float]: 日收益率列表（小数形式）
                        长度为 N-1（N 为数据点数量）
            
        Example:
            >>> assets = {date(2024,1,1): 100000, date(2024,1,2): 101000}
            >>> returns = analyzer._calculate_daily_returns(assets)
            >>> # 结果：[0.01] 表示 1% 的日收益率
        """
        dates = sorted(daily_assets.keys())
        returns = []
        for i in range(1, len(dates)):
            prev = daily_assets[dates[i - 1]]
            curr = daily_assets[dates[i]]
            returns.append((curr - prev) / prev)
        return returns



    def _calculate_profit(self, trade_records: List) -> List:
        """
        计算每笔交易的盈亏
        
        使用 FIFO（先进先出）原则匹配开平仓交易：
        - 买入：累积持仓，记录平均开仓价格和手续费
        - 卖出：按持仓比例计算成本和盈亏，平仓后重置持仓信息
        
        盈亏计算公式：
        盈亏 = 卖出金额 - 成本 - 手续费
        成本 = (卖出数量 / 持仓数量) × 总成本
        
        Args:
            trade_records: 成交记录列表
                         每条记录包含：symbol, volume, price, side, fee, created_at
            
        Returns:
            List[Dict]: 盈亏记录列表，每条记录包含：
                       - symbol: 标的代码
                       - profit: 盈亏金额（正为盈利，负为亏损）
                       - open_time, close_time: 开平仓时间
                       - open_price, close_price: 开平仓价格
                       - volume: 交易数量（负数表示卖出）
                       - open_fee, close_fee: 开平仓手续费
                       - original_trade: 原始交易记录对象
            
        Example:
            >>> profits = analyzer._calculate_profit(trade_records)
            >>> for trade in profits:
            ...     print(f"{trade['symbol']}: 盈亏 {trade['profit']}")
        """
        positions = defaultdict(lambda: {'volume': 0, 'cost': 0, 'open_time': None, 'open_price': 0, 'open_fee': 0})
        processed_trades = []

        for trade in trade_records:
            if trade.volume == 0 or math.isnan(trade.price):
                continue
            symbol = trade.symbol
            volume = trade.volume
            abs_volume = abs(volume)
            price = trade.price
            side = trade.side
            created_at = trade.created_at
            fee = trade.fee

            if side == 'buy':
                positions[symbol]['volume'] += abs_volume
                positions[symbol]['cost'] += abs_volume * price + fee
                if positions[symbol]['open_time'] is None:
                    positions[symbol]['open_time'] = created_at
                    positions[symbol]['open_price'] = price
                    positions[symbol]['open_fee'] += fee
            elif side == 'sell':
                if positions[symbol]['volume'] == 0:
                    continue

                sell_amount = abs_volume * price
                cost = (abs_volume / positions[symbol]['volume']) * positions[symbol]['cost']
                profit = sell_amount - cost - fee

                open_fee_portion = (abs_volume / positions[symbol]['volume']) * positions[symbol]['open_fee']

                processed_trades.append({
                    'symbol': symbol,
                    'profit': profit,
                    'open_time': positions[symbol]['open_time'],
                    'close_time': created_at,
                    'open_price': positions[symbol]['open_price'],
                    'open_fee': open_fee_portion,
                    'close_fee': fee,
                    'close_price': price,
                    'volume': volume,
                    'original_trade': trade
                })

                positions[symbol]['volume'] -= abs_volume
                positions[symbol]['cost'] -= cost
                positions[symbol]['open_fee'] -= open_fee_portion

                if positions[symbol]['volume'] == 0:
                    positions[symbol]['open_time'] = None
                    positions[symbol]['open_price'] = 0
                    positions[symbol]['open_fee'] = 0

        return processed_trades

    def _get_caller_dir(self) -> str:
        """
        获取调用者所在目录
        
        使用 inspect 模块获取调用当前方法的代码所在的目录
        用于确定 HTML 报告的输出路径基准
        
        Returns:
            str: 调用者脚本的绝对目录路径
            
        Example:
            # 如果在 d:\\project\\backtest\\main.py 中调用
            # analyzer._get_caller_dir() 返回 "d:\\project\\backtest"
        """
        frame = inspect.currentframe()
        try:
            caller_frame = None
            for frame_info in inspect.stack():
                if frame_info.filename != __file__:
                    caller_frame = frame_info
                    break

            if caller_frame:
                return os.path.dirname(os.path.abspath(caller_frame.filename))
            else:
                return os.path.dirname(os.path.abspath(__file__))
        finally:
            del frame
