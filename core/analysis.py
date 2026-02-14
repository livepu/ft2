#通过account的快照，分析结果
from collections import defaultdict
from dateutil.relativedelta import relativedelta
import math
from datetime import datetime
import json
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import inspect


class AccountAnalyzer:
    def __init__(self, account=None, external_daily_total_assets=None):
        self.account = account
        if account:
            self._daily_total_assets = self._compute_daily_total_assets(account.snapshots)
            self._trade_profits = self._calculate_profit(account.trade_log) 
        elif external_daily_total_assets:
            self._daily_total_assets = external_daily_total_assets
            self._trade_profits = []
        else:
            self._daily_total_assets = {}
            self._trade_profits = []
    @property
    def daily_total_assets(self):
        return self._daily_total_assets.copy()

    @property
    def trade_profits(self):
        return self._trade_profits.copy()
    def _compute_daily_total_assets(self, snapshots):
        daily_snapshots = defaultdict(list)
        for snapshot in snapshots:
            date = snapshot.created_at.date()
            daily_snapshots[date].append(snapshot)

        return {
            date: snaps[-1].nav
            for date, snaps in daily_snapshots.items()
        }
    
    def get_daily_total_assets(self):
        return self._daily_total_assets
    

    def calculate_max_drawdown(self):
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
    def calculate_return_rate(self, time_interval=None):
        start_date, end_date = self._get_start_end_date(time_interval)
        if not start_date or not end_date:
            return None

        start_value = self._daily_total_assets[start_date]
        end_value = self._daily_total_assets[end_date]
        if start_value == 0:
            raise ValueError("初始资产不能为零")
        return (end_value - start_value) / start_value
    

    def calculate_annualized_return(self, time_interval=None):
        interval_return = self.calculate_return_rate(time_interval)
        if interval_return is None:
            return None

        start_date, end_date = self._get_start_end_date(time_interval)
        days = (end_date - start_date).days
        if days == 0:
            return 0
        if interval_return <= -1:
            raise ValueError("亏损超过100%，无法计算年化收益率")
        return ((1 + interval_return) ** (365 / days)) - 1
    

    def calculate_volatility(self, time_interval=None):
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
    
    def calculate_sharpe_ratio(self, risk_free_rate=0.02, time_interval=None):
        annualized_return = self.calculate_annualized_return(time_interval)
        volatility = self.calculate_volatility(time_interval)

        if annualized_return is None or volatility is None:
            return None

        return (annualized_return - risk_free_rate) / volatility

    def calculate_sortino_ratio(self, risk_free_rate=0.02, time_interval=None):
        annualized_return = self.calculate_annualized_return(time_interval)
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

    def calculate_var(self, confidence=0.95, time_interval=None):
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

    def calculate_cvar(self, confidence=0.95, time_interval=None):
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

    def calculate_ulcer_index(self, time_interval=None):
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

    def calculate_upi(self, risk_free_rate=0.02, time_interval=None):
        annualized_return = self.calculate_annualized_return(time_interval)
        ulcer_index = self.calculate_ulcer_index(time_interval)

        if annualized_return is None or ulcer_index is None or ulcer_index == 0:
            return None

        return (annualized_return - risk_free_rate) / (ulcer_index / 100)

    def calculate_kelly_criterion(self, time_interval=None):
        if not self._trade_profits:
            return None

        win_rate = self.calculate_win_rate()
        if win_rate is None:
            return None

        avg_profit = self.calculate_avg_profit(mode='amount')
        avg_loss = self.calculate_avg_loss(mode='amount')

        if avg_profit is None or avg_loss is None or avg_loss == 0:
            return None

        profit_loss_ratio = abs(avg_profit / avg_loss)

        kelly = win_rate - (1 - win_rate) / profit_loss_ratio

        return kelly

    def calculate_kelly_fraction(self, fraction=0.5, time_interval=None):
        kelly = self.calculate_kelly_criterion(time_interval)
        if kelly is None:
            return None
        return kelly * fraction


    def _calculate_daily_returns(self, daily_assets):
        dates = sorted(daily_assets.keys())
        returns = []
        for i in range(1, len(dates)):
            prev = daily_assets[dates[i - 1]]
            curr = daily_assets[dates[i]]
            returns.append((curr - prev) / prev)
        return returns


    def _get_start_end_date(self, time_interval):
        if not self._daily_total_assets:
            return None, None

        dates = sorted(self._daily_total_assets.keys())
        end_date = dates[-1]

        interval_mapping = {
            '1m': relativedelta(months=1),
            '3m': relativedelta(months=3),
            '6m': relativedelta(months=6),
            '1y': relativedelta(years=1),
            '2y': relativedelta(years=2),
            '3y': relativedelta(years=3),
            '5y': relativedelta(years=5)
        }

        if time_interval is None or time_interval == 'all':
            start_date = dates[0]
        elif time_interval in interval_mapping:
            start_date = end_date - interval_mapping[time_interval]
            if start_date < dates[0]:
                return None, None
            closest_start_date = max((d for d in dates if d < start_date), default=None)
            if closest_start_date is None:
                return None, None
            start_date = closest_start_date
        else:
            return None, None

        return start_date, end_date

    def _calculate_profit(self, trade_log):
        positions = defaultdict(lambda: {'volume': 0, 'cost': 0, 'open_time': None, 'open_price': 0, 'open_fee': 0})
        processed_trades = []

        for trade in trade_log:
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
    
    def get_largest_profit_trades(self, n):
        if not self._trade_profits or n <= 0:
            return []
        return sorted(self._trade_profits, key=lambda t: t['profit'], reverse=True)[:n]

    def get_largest_loss_trades(self, n):
        if not self._trade_profits or n <= 0:
            return []
        return sorted(self._trade_profits, key=lambda t: t['profit'])[:n]

    def calculate_average_holding_period(self):
        if not self._trade_profits:
            return None
        total_days = sum((t['close_time'] - t['open_time']).days for t in self._trade_profits)
        return total_days / len(self._trade_profits)

    def calculate_win_rate(self):
        if not self._trade_profits:
            return None
        wins = sum(1 for t in self._trade_profits if t['profit'] > 0)
        return wins / len(self._trade_profits)

    def calculate_avg_profit(self, mode='amount') -> float:
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

    def calculate_avg_loss(self, mode='amount') -> float:
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

    def calculate_avg_profit_loss_ratio(self, mode='amount') -> float:
        avg_profit = self.calculate_avg_profit(mode)
        avg_loss = self.calculate_avg_loss(mode)
        
        if avg_profit is None or avg_loss is None:
            return None
        
        return abs(avg_profit / avg_loss)

    @staticmethod
    def translate_keys(data):
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
    
    @staticmethod
    def format_transaction_log(transaction_records):
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
    def format_trade(trade):
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

    def format_daily_assets(self):
        result = []
        for date,assets in self._daily_total_assets.items():
            if hasattr(date, 'strftime'):
                date_str = date.strftime("%Y-%m-%d")
            else:
                date_str = str(date)

            result.append({
                "date": date_str,
                "assets": round(float(assets), 2)
            })
        return result


    def to_html_report(self, report_name="回测报告", output_dir="."):
        initial_cash = self.account.snapshots[0].cash if self.account.snapshots else 0
        final_assets = self.account.snapshots[-1].nav if self.account.snapshots else 0
        return_rate = self.calculate_return_rate() * 100
        an_return_rate = self.calculate_annualized_return()*100
        sharpe_ratio = self.calculate_sharpe_ratio()
        max_drawdown, max_drawdown_start_date, max_drawdown_end_date = self.calculate_max_drawdown()
        avg_profit = self.calculate_avg_profit()
        avg_loss = self.calculate_avg_loss()

        avg_profit_loss_ratio = self.calculate_avg_profit_loss_ratio()
        avg_holding_period = self.calculate_average_holding_period()
        
        sortino_ratio = self.calculate_sortino_ratio()
        var_95 = self.calculate_var(confidence=0.95)
        cvar_95 = self.calculate_cvar(confidence=0.95)
        ulcer_index = self.calculate_ulcer_index()
        upi = self.calculate_upi()
        kelly = self.calculate_kelly_criterion()
        half_kelly = self.calculate_kelly_fraction(fraction=0.5)

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
            {"name":"年化波动率", "value": f"{self.calculate_volatility()*100:.2f}%"},
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
            {"name": "胜率", "value": f"{self.calculate_win_rate()*100:.2f}%" if self.calculate_win_rate() is not None else "N/A"},
            {"name": "凯利公式最优仓位", "value": f"{kelly*100:.2f}%" if kelly is not None and kelly > 0 else f"不建议投资（{kelly*100:.2f}%）" if kelly is not None else "N/A"},
            {"name": "半凯利仓位", "value": f"{half_kelly*100:.2f}%" if half_kelly is not None and half_kelly > 0 else "N/A"},
            {"name": "平均持仓时间（天）", "value": f"{avg_holding_period:.2f}" if avg_holding_period is not None else "N/A"},
        ]

        assets_data = self.format_daily_assets()
        largest_profit_trades = self.get_largest_profit_trades(5)
        largest_loss_trades = self.get_largest_loss_trades(5)

        formatted_transaction_log=self.format_transaction_log(self.account.trade_log)
        formatted_profit_trades = [self.format_trade(trade) for trade in largest_profit_trades]
        formatted_loss_trades = [self.format_trade(trade) for trade in largest_loss_trades]
        assets_data_zh=self.translate_keys(assets_data)
        formatted_transaction_log_zh=self.translate_keys(formatted_transaction_log)

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

        frame = inspect.currentframe().f_back
        caller_file = frame.f_code.co_filename
        caller_dir = Path(caller_file).resolve().parent

        current_datetime = datetime.now().strftime("%Y%m%d_%H%M")

        output_path = caller_dir / output_dir / f"{report_name}_{current_datetime}.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"报告已生成至: {output_path}")
