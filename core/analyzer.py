#通过account的快照，分析结果
from collections import defaultdict
from dateutil.relativedelta import relativedelta
import math
import os
from datetime import datetime, date
from typing import Dict, List, Tuple, Any, Optional
import json
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import inspect


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

    TIME_INTERVALS = {
        '1m': relativedelta(months=1),
        '3m': relativedelta(months=3),
        '6m': relativedelta(months=6),
        '1y': relativedelta(years=1),
        '2y': relativedelta(years=2),
        '3y': relativedelta(years=3),
        '5y': relativedelta(years=5)
    }

    def __init__(self, account=None, external_daily_total_assets=None):
        """
        初始化账户分析器
        
        Args:
            account: AccountManager实例
            external_daily_total_assets: 外部每日资产数据，格式为{date: nav}
        """
        self.account = account
        self._metrics = {}
        if account:
            self._daily_total_assets = self._compute_daily_total_assets(account.snapshots)
            self._trade_profits = self._calculate_profit(account._trade_records)
        elif external_daily_total_assets:
            self._daily_total_assets = external_daily_total_assets
            self._trade_profits = []
        else:
            self._daily_total_assets = {}
            self._trade_profits = []

        self.base_dir = self._get_caller_dir()

    @property
    def daily_total_assets(self) -> Dict:
        """每日资产净值的副本"""
        return self._daily_total_assets.copy()

    @property
    def trade_profits(self) -> List:
        """交易盈亏记录的副本"""
        return self._trade_profits.copy()

    # ------------------------------------------------------------------------
    # 统一指标获取方法
    # ------------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Dict]:
        """
        获取所有已计算的指标
        
        Returns:
            Dict: {方法名: {'name': 中文名, 'value': 原始值}}
        """
        return self._metrics.copy()

    # ------------------------------------------------------------------------
    # 收益指标
    # ------------------------------------------------------------------------

    def calc_return_rate(self, time_interval=None) -> float:
        """
        计算收益率
        
        Args:
            time_interval: 时间区间，可选值：'1m', '3m', '6m', '1y', '2y', '3y', '5y', 'all'
            
        Returns:
            float: 收益率，无数据时返回None
        """
        start_date, end_date = self._get_start_end_date(time_interval)
        if not start_date or not end_date:
            return None

        start_value = self._daily_total_assets[start_date]
        end_value = self._daily_total_assets[end_date]
        if start_value == 0:
            raise ValueError("初始资产不能为零")
        value = (end_value - start_value) / start_value
        self._metrics['calc_return_rate'] = {'name': '累计收益率', 'value': value, 'order': 10}
        return value

    def calc_annualized_return(self, time_interval=None) -> float:
        """
        计算年化收益率
        
        Args:
            time_interval: 时间区间
            
        Returns:
            float: 年化收益率
        """
        interval_return = self.calc_return_rate(time_interval)
        if interval_return is None:
            return None

        start_date, end_date = self._get_start_end_date(time_interval)
        days = (end_date - start_date).days
        if days == 0:
            value = 0
        elif interval_return <= -1:
            raise ValueError("亏损超过100%，无法计算年化收益率")
        else:
            value = ((1 + interval_return) ** (365 / days)) - 1
        self._metrics['calc_annualized_return'] = {'name': '年化收益率', 'value': value, 'order': 11}
        return value

    # ------------------------------------------------------------------------
    # 风险指标
    # ------------------------------------------------------------------------

    def calc_volatility(self, time_interval=None) -> float:
        """
        计算年化波动率
        
        Args:
            time_interval: 时间区间
            
        Returns:
            float: 年化波动率
        """
        start_date, end_date = self._get_start_end_date(time_interval)
        if not start_date or not end_date:
            return None

        interval_assets = {d: v for d, v in self._daily_total_assets.items() if start_date <= d <= end_date}
        daily_returns = self._calculate_daily_returns(interval_assets)

        if len(daily_returns) < 2:
            raise ValueError("至少需要2个数据点计算波动率")
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
        daily_volatility = math.sqrt(variance)
        value = daily_volatility * math.sqrt(252)
        self._metrics['calc_volatility'] = {'name': '年化波动率', 'value': value, 'order': 20}
        return value

    def calc_max_drawdown(self) -> Tuple[float, date, date]:
        """
        计算最大回撤
        
        Returns:
            Tuple[float, date, date]: (最大回撤比例, 回撤开始日期, 回撤结束日期)
        """
        if not self._daily_total_assets:
            return 0, None, None

        dates = sorted(self._daily_total_assets.keys())
        max_drawdown = 0
        peak_value = self._daily_total_assets[dates[0]]
        start_date = end_date = peak_date = dates[0]

        for date in dates:
            current_value = self._daily_total_assets[date]
            if current_value > peak_value:
                peak_value = current_value
                peak_date = date
            drawdown = (peak_value - current_value) / peak_value
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                start_date = peak_date
                end_date = date
        if max_drawdown == 0:
            return 0, None, None
        self._metrics['calc_max_drawdown'] = {
            'name': '最大回撤', 
            'value': max_drawdown,
            'start': start_date,
            'end': end_date,
            'order': 21
        }
        return max_drawdown, start_date, end_date

    def calc_var(self, confidence: float = 0.95, time_interval=None) -> float:
        """
        计算风险价值(VaR)
        
        Args:
            confidence: 置信水平，默认0.95
            time_interval: 时间区间
            
        Returns:
            float: VaR值
        """
        start_date, end_date = self._get_start_end_date(time_interval)
        if not start_date or not end_date:
            return None

        interval_assets = {d: v for d, v in self._daily_total_assets.items() if start_date <= d <= end_date}
        daily_returns = self._calculate_daily_returns(interval_assets)

        if len(daily_returns) < 2:
            return None

        sorted_returns = sorted(daily_returns)
        index = int((1 - confidence) * len(sorted_returns))
        if index < 0:
            index = 0

        var = -sorted_returns[index]
        self._metrics['calc_var'] = {'name': 'VaR(95%)', 'value': var}
        return var

    def calc_cvar(self, confidence: float = 0.95, time_interval=None) -> float:
        """
        计算条件风险价值(CVaR)
        
        Args:
            confidence: 置信水平，默认0.95
            time_interval: 时间区间
            
        Returns:
            float: CVaR值
        """
        start_date, end_date = self._get_start_end_date(time_interval)
        if not start_date or not end_date:
            return None

        interval_assets = {d: v for d, v in self._daily_total_assets.items() if start_date <= d <= end_date}
        daily_returns = self._calculate_daily_returns(interval_assets)

        if len(daily_returns) < 2:
            return None

        sorted_returns = sorted(daily_returns)
        index = int((1 - confidence) * len(sorted_returns))
        if index < 1:
            index = 1

        tail_returns = sorted_returns[:index]
        cvar = -sum(tail_returns) / len(tail_returns)
        self._metrics['calc_cvar'] = {'name': 'CVaR(95%)', 'value': cvar, 'order': 23}
        return cvar

    def calc_ulcer_index(self, time_interval=None) -> float:
        """
        计算溃疡指数(Ulcer Index)
        
        Args:
            time_interval: 时间区间
            
        Returns:
            float: Ulcer Index值
        """
        start_date, end_date = self._get_start_end_date(time_interval)
        if not start_date or not end_date:
            return None

        dates = sorted(self._daily_total_assets.keys())
        interval_dates = [d for d in dates if start_date <= d <= end_date]

        if len(interval_dates) < 2:
            return None

        peak = self._daily_total_assets[interval_dates[0]]
        squared_drawdowns = []

        for date in interval_dates:
            value = self._daily_total_assets[date]
            if value > peak:
                peak = value
            drawdown_pct = (peak - value) / peak * 100
            squared_drawdowns.append(drawdown_pct ** 2)

        ulcer_index = math.sqrt(sum(squared_drawdowns) / len(squared_drawdowns))
        self._metrics['calc_ulcer_index'] = {'name': 'Ulcer Index', 'value': ulcer_index}
        return ulcer_index

    # ------------------------------------------------------------------------
    # 风险调整收益指标
    # ------------------------------------------------------------------------

    def calc_sharpe_ratio(self, risk_free_rate: float = 0.02, time_interval=None) -> float:
        """
        计算夏普比率
        
        Args:
            risk_free_rate: 无风险利率，默认0.02
            time_interval: 时间区间
            
        Returns:
            float: 夏普比率
        """
        annualized_return = self.calc_annualized_return(time_interval)
        volatility = self.calc_volatility(time_interval)

        if annualized_return is None or volatility is None:
            return None

        value = (annualized_return - risk_free_rate) / volatility
        self._metrics['calc_sharpe_ratio'] = {'name': '夏普比率', 'value': value, 'order': 30}
        return value

    def calc_sortino_ratio(self, risk_free_rate: float = 0.02, time_interval=None) -> float:
        """
        计算索提诺比率
        
        Args:
            risk_free_rate: 无风险利率，默认0.02
            time_interval: 时间区间
            
        Returns:
            float: 索提诺比率
        """
        annualized_return = self.calc_annualized_return(time_interval)
        if annualized_return is None:
            return None

        start_date, end_date = self._get_start_end_date(time_interval)
        if not start_date or not end_date:
            return None

        interval_assets = {d: v for d, v in self._daily_total_assets.items() if start_date <= d <= end_date}
        daily_returns = self._calculate_daily_returns(interval_assets)

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
        self._metrics['calc_sortino_ratio'] = {'name': '索提诺比率', 'value': value, 'order': 31}
        return value

    def calc_upi(self, risk_free_rate: float = 0.02, time_interval=None) -> float:
        """
        计算Ulcer Performance Index (UPI)
        
        Args:
            risk_free_rate: 无风险利率，默认0.02
            time_interval: 时间区间
            
        Returns:
            float: UPI值
        """
        annualized_return = self.calc_annualized_return(time_interval)
        ulcer_index = self.calc_ulcer_index(time_interval)

        if annualized_return is None or ulcer_index is None or ulcer_index == 0:
            return None

        value = (annualized_return - risk_free_rate) / (ulcer_index / 100)
        self._metrics['calc_upi'] = {'name': 'UPI', 'value': value}
        return value

    # ------------------------------------------------------------------------
    # 交易分析指标
    # ------------------------------------------------------------------------

    def calc_win_rate(self) -> float:
        """
        计算胜率
        
        Returns:
            float: 胜率，盈利交易占比
        """
        if not self._trade_profits:
            return None
        wins = sum(1 for t in self._trade_profits if t['profit'] > 0)
        value = wins / len(self._trade_profits)
        self._metrics['calc_win_rate'] = {'name': '胜率', 'value': value, 'order': 40}
        return value

    def calc_avg_profit(self, mode: str = 'amount') -> float:
        """
        计算平均盈利
        
        Args:
            mode: 计算模式，'amount'为金额，'percentage'为百分比
            
        Returns:
            float: 平均盈利
        """
        profitable_trades = [t for t in self._trade_profits if t['profit'] > 0]
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

    def calc_avg_loss(self, mode: str = 'amount') -> float:
        """
        计算平均亏损
        
        Args:
            mode: 计算模式，'amount'为金额，'percentage'为百分比
            
        Returns:
            float: 平均亏损
        """
        loss_trades = [t for t in self._trade_profits if t['profit'] < 0]
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

    def calc_avg_profit_loss_ratio(self, mode: str = 'amount') -> float:
        """
        计算平均盈亏比
        
        Args:
            mode: 计算模式，'amount'为金额，'percentage'为百分比
            
        Returns:
            float: 平均盈亏比
        """
        avg_profit = self.calc_avg_profit(mode)
        avg_loss = self.calc_avg_loss(mode)

        if avg_profit is None or avg_loss is None:
            return None

        value = abs(avg_profit / avg_loss)
        self._metrics['calc_avg_profit_loss_ratio'] = {'name': '平均盈亏比', 'value': value}
        return value

    def calc_avg_holding_period(self) -> float:
        """
        计算平均持仓时间
        
        Returns:
            float: 平均持仓天数
        """
        if not self._trade_profits:
            return None
        total_days = sum((t['close_time'] - t['open_time']).days for t in self._trade_profits)
        value = total_days / len(self._trade_profits)
        self._metrics['calc_avg_holding_period'] = {'name': '平均持仓时间', 'value': value, 'order': 42}
        return value

    def calc_kelly_criterion(self, time_interval=None) -> float:
        """
        计算凯利公式最优仓位
        
        Args:
            time_interval: 时间区间（暂未使用）
            
        Returns:
            float: 凯利最优仓位比例
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
        self._metrics['calc_kelly_criterion'] = {'name': '凯利公式最优仓位', 'value': kelly}
        return kelly

    def calc_kelly_fraction(self, fraction: float = 0.5, time_interval=None) -> float:
        """
        计算凯利分数仓位
        
        Args:
            fraction: 凯利分数，默认0.5（半凯利）
            time_interval: 时间区间（暂未使用）
            
        Returns:
            float: 凯利分数仓位比例
        """
        kelly = self.calc_kelly_criterion(time_interval)
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
        
        Returns:
            Dict: {date: nav} 字典
        """
        return self._daily_total_assets

    def get_largest_profit_trades(self, n: int) -> List:
        """
        获取盈利最大的N笔交易
        
        Args:
            n: 返回数量
            
        Returns:
            List: 交易记录列表
        """
        if not self._trade_profits or n <= 0:
            return []
        return sorted(self._trade_profits, key=lambda t: t['profit'], reverse=True)[:n]

    def get_largest_loss_trades(self, n: int) -> List:
        """
        获取亏损最大的N笔交易
        
        Args:
            n: 返回数量
            
        Returns:
            List: 交易记录列表
        """
        if not self._trade_profits or n <= 0:
            return []
        return sorted(self._trade_profits, key=lambda t: t['profit'])[:n]

    # ------------------------------------------------------------------------
    # 导出方法
    # ------------------------------------------------------------------------

    def export_html(self, report_name: str = "回测报告", output_dir: str = "."):
        """
        导出HTML报告
        
        Args:
            report_name: 报告名称
            output_dir: 输出目录（相对路径，基于实例化时的调用者目录）
        """
        for name in dir(self):
            if name.startswith('calc_'):
                method = getattr(self, name)
                if callable(method):
                    try:
                        method()
                    except Exception:
                        pass

        initial_cash = self.account.snapshots[0].cash if self.account.snapshots else 0
        final_assets = self.account.snapshots[-1].nav if self.account.snapshots else 0

        dates = sorted(self._daily_total_assets.keys())
        start_date = dates[1] if len(dates) > 1 else None
        end_date = dates[-1] if dates else None

        backtest_period = f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}" if start_date and end_date else "N/A"

        metrics = [
            {"name": "回测区间", "value": backtest_period, "order": 1},
            {"name": "初始资金", "value": initial_cash, "order": 2},
            {"name": "最终资产", "value": final_assets, "order": 3},
        ]
        for method_name, data in self._metrics.items():
            metrics.append({
                "name": data['name'], 
                "value": data['value'],
                "order": data.get('order', 99)
            })
        
        metrics.sort(key=lambda x: x['order'])

        data = {
            'title': report_name,
            'createdAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'metrics': metrics,
            'dailyAssets': [
                {'date': d.strftime('%Y-%m-%d'), 'assets': v} 
                for d, v in self._daily_total_assets.items()
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
        将对象转换为可JSON序列化的字典
        
        Args:
            obj: 对象或字典
            exclude: 要排除的字段名
            
        Returns:
            dict: 字典
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

    def _compute_daily_total_assets(self, snapshots: List) -> Dict:
        """
        计算每日资产净值
        
        Args:
            snapshots: 快照列表
            
        Returns:
            Dict: {date: nav} 字典
        """
        daily_snapshots = defaultdict(list)
        for snapshot in snapshots:
            date = snapshot.created_at.date()
            daily_snapshots[date].append(snapshot)

        return {
            date: snaps[-1].nav
            for date, snaps in daily_snapshots.items()
        }

    def _calculate_daily_returns(self, daily_assets: Dict) -> List:
        """
        计算日收益率序列
        
        Args:
            daily_assets: 每日资产字典
            
        Returns:
            List: 日收益率列表
        """
        dates = sorted(daily_assets.keys())
        returns = []
        for i in range(1, len(dates)):
            prev = daily_assets[dates[i - 1]]
            curr = daily_assets[dates[i]]
            returns.append((curr - prev) / prev)
        return returns

    def _get_start_end_date(self, time_interval: str):
        """
        获取时间区间的起止日期
        
        Args:
            time_interval: 时间区间标识
            
        Returns:
            Tuple: (start_date, end_date)
        """
        if not self._daily_total_assets:
            return None, None

        dates = sorted(self._daily_total_assets.keys())
        end_date = dates[-1]

        if time_interval is None or time_interval == 'all':
            start_date = dates[0]
        elif time_interval in self.TIME_INTERVALS:
            start_date = end_date - self.TIME_INTERVALS[time_interval]
            if start_date < dates[0]:
                return None, None
            closest_start_date = max((d for d in dates if d < start_date), default=None)
            if closest_start_date is None:
                return None, None
            start_date = closest_start_date
        else:
            return None, None

        return start_date, end_date

    def _calculate_profit(self, trade_records: List) -> List:
        """
        计算每笔交易的盈亏
        
        Args:
            trade_records: 成交记录列表
            
        Returns:
            List: 盈亏记录列表
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
        
        Returns:
            str: 调用者目录路径
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
