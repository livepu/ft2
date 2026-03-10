#通过account的快照，分析结果
from collections import defaultdict
from dateutil.relativedelta import relativedelta
import math
import os
from datetime import datetime, date
from typing import Dict, List, Tuple
import json
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import inspect


# ============================================================================
# 账户分析类
# ============================================================================

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
        return (end_value - start_value) / start_value

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
            return 0
        if interval_return <= -1:
            raise ValueError("亏损超过100%，无法计算年化收益率")
        return ((1 + interval_return) ** (365 / days)) - 1

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
        annualized_volatility = daily_volatility * math.sqrt(252)

        return annualized_volatility

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

        return (annualized_return - risk_free_rate) / volatility

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

        return (annualized_return - risk_free_rate) / annualized_downside_deviation

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

        return (annualized_return - risk_free_rate) / (ulcer_index / 100)

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
        return wins / len(self._trade_profits)

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

        return abs(avg_profit / avg_loss)

    def calc_avg_holding_period(self) -> float:
        """
        计算平均持仓时间
        
        Returns:
            float: 平均持仓天数
        """
        if not self._trade_profits:
            return None
        total_days = sum((t['close_time'] - t['open_time']).days for t in self._trade_profits)
        return total_days / len(self._trade_profits)

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
        return kelly * fraction

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
    # 格式化方法
    # ------------------------------------------------------------------------

    def format_daily_assets(self) -> List:
        """
        格式化每日资产数据
        
        Returns:
            List: 格式化后的资产列表
        """
        result = []
        for date, assets in self._daily_total_assets.items():
            if hasattr(date, 'strftime'):
                date_str = date.strftime("%Y-%m-%d")
            else:
                date_str = str(date)

            result.append({
                "date": date_str,
                "assets": round(float(assets), 2)
            })
        return result

    @staticmethod
    def format_transaction_log(transaction_records: List) -> List:
        """
        格式化交易记录
        
        Args:
            transaction_records: 交易记录列表
            
        Returns:
            List: 格式化后的交易记录
        """
        result = []
        for record in transaction_records:
            if hasattr(record, '__dict__'):
                data = record.__dict__
            else:
                data = record

            formatted = {}
            for key, value in data.items():
                if key == 'volume':
                    formatted[key] = int(value)
                elif key == 'price' or key == 'fee':
                    formatted[key] = round(float(value), 2)
                elif key == 'side':
                    formatted[key] = '买入' if value == 'buy' else '卖出'
                elif key == 'created_at':
                    formatted[key] = value.strftime("%Y-%m-%d")
                else:
                    formatted[key] = value

            result.append(formatted)

        return result

    @staticmethod
    def format_trade(trade: Dict) -> Dict:
        """
        格式化单笔交易盈亏记录
        
        Args:
            trade: 交易盈亏记录
            
        Returns:
            Dict: 格式化后的交易记录
        """
        original_trade = trade['original_trade']
        return {
            'symbol': original_trade.symbol,
            'profit': f"{trade['profit']:.2f}",
            'open_time': trade['open_time'].strftime('%Y-%m-%d'),
            'open_price': f"{trade['open_price']:.2f}",
            'open_fee': f"{trade['open_fee']:.2f}",
            'close_time': trade['close_time'].strftime('%Y-%m-%d'),
            'close_price': f"{trade['close_price']:.2f}",
            'close_fee': f"{trade['close_fee']:.2f}",
            'volume': f"{abs(trade['volume']):d}"
        }

    @staticmethod
    def translate_keys(data: List) -> List:
        """
        将字段名翻译为中文
        
        Args:
            data: 数据列表
            
        Returns:
            List: 翻译后的数据列表
        """
        field_mapping = {
            "date": "日期",
            "value": "净值",
            "benchmark": "基准",
            "action": "操作",
            "code": "代码",
            "quantity": "数量",
            "price": "价格",
            "assets": "资产",
            "symbol": "标的",
            "created_at": "时间",
            "volume": "数量",
            "side": "方向",
            "fee": "手续费",
            "order_id": "成交单号",
        }
        return [{field_mapping.get(k, k): v for k, v in item.items()} for item in data]

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
        initial_cash = self.account.snapshots[0].cash if self.account.snapshots else 0
        final_assets = self.account.snapshots[-1].nav if self.account.snapshots else 0
        return_rate = self.calc_return_rate() * 100
        an_return_rate = self.calc_annualized_return() * 100
        sharpe_ratio = self.calc_sharpe_ratio()
        max_drawdown, max_drawdown_start_date, max_drawdown_end_date = self.calc_max_drawdown()
        avg_profit = self.calc_avg_profit()
        avg_loss = self.calc_avg_loss()

        avg_profit_loss_ratio = self.calc_avg_profit_loss_ratio()
        avg_holding_period = self.calc_avg_holding_period()

        sortino_ratio = self.calc_sortino_ratio()
        var_95 = self.calc_var(confidence=0.95)
        cvar_95 = self.calc_cvar(confidence=0.95)
        ulcer_index = self.calc_ulcer_index()
        upi = self.calc_upi()
        kelly = self.calc_kelly_criterion()
        half_kelly = self.calc_kelly_fraction(fraction=0.5)

        max_drawdown_period = f"{max_drawdown_start_date.strftime('%Y-%m-%d')} 至 {max_drawdown_end_date.strftime('%Y-%m-%d')}" if max_drawdown_start_date and max_drawdown_end_date else "N/A"
        dates = sorted(self._daily_total_assets.keys())
        start_date = dates[1] if dates else None
        end_date = dates[-1] if dates else None

        backtest_period = f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}" if start_date and end_date else "N/A"

        metrics = [
            {"name": "回测区间", "value": backtest_period},
            {"name": "初始资金", "value": f"{initial_cash:.2f}"},
            {"name": "最终资产", "value": f"{final_assets:.2f}"},
            {"name": "累计收益率", "value": f"{return_rate:.2f}%"},
            {"name": "年化收益率", "value": f"{an_return_rate:.2f}%"},
            {"name": "年化波动率", "value": f"{self.calc_volatility()*100:.2f}%"},
            {"name": "夏普比率", "value": f"{sharpe_ratio:.2f}" if sharpe_ratio is not None else "N/A"},
            {"name": "索提诺比率", "value": f"{sortino_ratio:.2f}" if sortino_ratio is not None and sortino_ratio != float('inf') else "N/A"},
            {"name": "最大回撤", "value": f"{max_drawdown * 100:.2f}%，时段：{max_drawdown_period}"},
            {"name": "VaR(95%)", "value": f"{var_95*100:.2f}%" if var_95 is not None else "N/A"},
            {"name": "CVaR(95%)", "value": f"{cvar_95*100:.2f}%" if cvar_95 is not None else "N/A"},
            {"name": "Ulcer Index", "value": f"{ulcer_index:.2f}" if ulcer_index is not None else "N/A"},
            {"name": "UPI", "value": f"{upi:.2f}" if upi is not None else "N/A"},
            {
                "name": "平均盈亏比",
                "value": f"{avg_profit_loss_ratio:.2f}（平均盈利{avg_profit * 100:.2f}%，平均亏损{abs(avg_loss) * 100:.2f}%）"
                        if avg_profit_loss_ratio is not None and avg_profit is not None and avg_loss is not None
                        else "N/A"
            },
            {"name": "胜率", "value": f"{self.calc_win_rate()*100:.2f}%" if self.calc_win_rate() is not None else "N/A"},
            {"name": "凯利公式最优仓位", "value": f"{kelly*100:.2f}%" if kelly is not None and kelly > 0 else f"不建议投资（{kelly*100:.2f}%）" if kelly is not None else "N/A"},
            {"name": "半凯利仓位", "value": f"{half_kelly*100:.2f}%" if half_kelly is not None and half_kelly > 0 else "N/A"},
            {"name": "平均持仓时间（天）", "value": f"{avg_holding_period:.2f}" if avg_holding_period is not None else "N/A"},
        ]

        assets_data = self.format_daily_assets()
        largest_profit_trades = self.get_largest_profit_trades(5)
        largest_loss_trades = self.get_largest_loss_trades(5)

        formatted_transaction_log = self.format_transaction_log(self.account._trade_records)
        formatted_profit_trades = [self.format_trade(trade) for trade in largest_profit_trades]
        formatted_loss_trades = [self.format_trade(trade) for trade in largest_loss_trades]
        assets_data_zh = self.translate_keys(assets_data)
        formatted_transaction_log_zh = self.translate_keys(formatted_transaction_log)

        assets_data_json = json.dumps(assets_data_zh, indent=4, ensure_ascii=False)
        formatted_transaction_log_json = json.dumps(formatted_transaction_log_zh, indent=4, ensure_ascii=False)
        formatted_profit_trades_json = json.dumps(formatted_profit_trades, indent=4, ensure_ascii=False)
        formatted_loss_trades_json = json.dumps(formatted_loss_trades, indent=4, ensure_ascii=False)

        current_file_path = Path(__file__).resolve()
        template_dir = current_file_path.parent.parent / "template"

        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("analyzer.html")

        html_content = template.render(
            report_name=report_name,
            metrics=metrics,
            assets_data=assets_data_json,
            transaction_data=formatted_transaction_log_json,
            largest_profit_trades=formatted_profit_trades_json,
            largest_loss_trades=formatted_loss_trades_json
        )

        current_datetime = datetime.now().strftime("%Y%m%d_%H%M")
        output_path = Path(self.base_dir) / output_dir / f"{report_name}_{current_datetime}.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"报告已生成至: {output_path}")

    # ------------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------------

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
