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
        """
        :param account: Account 实例，应包含：
                        - snapshots: AccountSnapshot 列表
                        - trades: Trade 记录列表（需有 symbol, profit, open_time, close_time）
        :param external_daily_total_assets: 外部导入的日度总资产数据，字典类型，键为日期，值为总资产
        """
        self.account = account
        if account:
            # 从 account 实例初始化日度资产
            self.daily_total_assets = self._compute_daily_total_assets(account.snapshots)
            # 从 account 实例初始化交易数据，使用 trade_log 属性
            self.trade_log = self._calculate_profit(account.trade_log)
        elif external_daily_total_assets:
            # 使用外部导入的数据初始化日度资产
            self.daily_total_assets = external_daily_total_assets
            self.trade_log = [] #严格来说，外部记录就不做交易分析
        else:
            # 空白初始化
            self.daily_total_assets = {}
            self.trade_log = []

    def _compute_daily_total_assets(self, snapshots):
        daily_snapshots = defaultdict(list)
        for snapshot in snapshots:
            date = snapshot.created_at.date()
            daily_snapshots[date].append(snapshot)

        return {
            date: snaps[-1].total_assets
            for date, snaps in daily_snapshots.items()
        }

    # ========== 资产相关方法 ==========
    def get_daily_total_assets(self):
        return self.daily_total_assets
    
#计算最大回测
    def calculate_max_drawdown(self):
        if not self.daily_total_assets:
            return 0, None, None

        dates = sorted(self.daily_total_assets.keys())
        max_drawdown = 0
        peak_value = self.daily_total_assets[dates[0]]
        start_date = end_date = peak_date = dates[0]

        for date in dates:
            current_value = self.daily_total_assets[date]
            if current_value > peak_value:
                peak_value = current_value
                peak_date = date
            drawdown = (peak_value - current_value) / peak_value
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                start_date = peak_date
                end_date = date

        return max_drawdown, start_date, end_date
#计算区间收益率
    def calculate_return_rate(self, time_interval=None):
        start_date, end_date = self._get_start_end_date(time_interval)
        if not start_date or not end_date:
            return None

        start_value = self.daily_total_assets[start_date]
        end_value = self.daily_total_assets[end_date]
        return (end_value - start_value) / start_value
#计算年化收益率
    def calculate_annualized_return(self, time_interval=None):
        interval_return = self.calculate_return_rate(time_interval)
        if interval_return is None:
            return None

        start_date, end_date = self._get_start_end_date(time_interval)
        days = (end_date - start_date).days
        if days == 0:
            return 0

        return ((1 + interval_return) ** (365 / days)) - 1
#计算波动率
    def calculate_volatility(self, time_interval=None):
        start_date, end_date = self._get_start_end_date(time_interval)
        if not start_date or not end_date:
            return None

        interval_assets = {d: v for d, v in self.daily_total_assets.items() if start_date <= d <= end_date}
        daily_returns = self._calculate_daily_returns(interval_assets)

        if not daily_returns:
            return None

        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
        daily_volatility = math.sqrt(variance)
        
        # 返回年化波动率
        annualized_volatility = daily_volatility * math.sqrt(252)
        return annualized_volatility
#计算夏普比率
    def calculate_sharpe_ratio(self, risk_free_rate=0.02, time_interval=None):
        annualized_return = self.calculate_annualized_return(time_interval)
        volatility = self.calculate_volatility(time_interval)

        if annualized_return is None or volatility is None:
            return None

        return (annualized_return - risk_free_rate) / volatility
#计算每日收益率
    def _calculate_daily_returns(self, daily_assets):
        dates = sorted(daily_assets.keys())
        returns = []
        for i in range(1, len(dates)):
            prev = daily_assets[dates[i - 1]]
            curr = daily_assets[dates[i]]
            returns.append((curr - prev) / prev)
        return returns
#获取区间开始和结束日期
    def _get_start_end_date(self, time_interval):
        if not self.daily_total_assets:
            return None, None

        dates = sorted(self.daily_total_assets.keys())
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
            closest_start_date = max((d for d in dates if d < start_date), default=None) #区间的前一日作为基准
            if closest_start_date is None:
                return None, None
            start_date = closest_start_date
        else:
            return None, None

        return start_date, end_date

    # ========== 交易相关方法 ==========
    #注意在初始化调用
    def _calculate_profit(self, trade_log):
        """
        计算每笔交易的盈亏
        :param trade_log: 原始交易记录列表
        :return: 包含盈亏信息的交易记录列表
        """
        positions = defaultdict(lambda: {'volume': 0, 'cost': 0, 'open_time': None, 'open_price': 0, 'open_fee': 0})
        processed_trades = []

        for trade in trade_log:
            symbol = trade.symbol
            volume = trade.volume
            abs_volume = abs(volume)  # 新增：计算 volume 的绝对值
            price = trade.price
            side = trade.side
            created_at = trade.created_at
            fee = trade.fee
            if side == 'buy':
                # 买入操作，更新持仓信息，成本加上手续费
                positions[symbol]['volume'] += abs_volume  # 使用绝对值更新持仓量
                # 买入成本加上手续费
                positions[symbol]['cost'] += abs_volume * price + fee
                if positions[symbol]['open_time'] is None:
                    positions[symbol]['open_time'] = created_at
                    positions[symbol]['open_price'] = price
                    positions[symbol]['open_fee'] += fee  # 累加开仓手续费，确保为正数
            elif side == 'sell':
                # 卖出操作，计算盈亏
                if positions[symbol]['volume'] == 0:
                    continue  # 无持仓，跳过

                sell_amount = abs_volume * price  # 使用绝对值计算卖出金额
                # 按比例计算卖出部分的成本
                cost = (abs_volume / positions[symbol]['volume']) * positions[symbol]['cost']
                profit = sell_amount - cost - fee

                # 按比例计算卖出部分对应的开仓手续费，确保为正数
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

                # 更新持仓信息
                positions[symbol]['volume'] -= abs_volume  # 使用绝对值减少持仓量
                positions[symbol]['cost'] -= cost
                positions[symbol]['open_fee'] -= open_fee_portion

                if positions[symbol]['volume'] == 0:
                    positions[symbol]['open_time'] = None
                    positions[symbol]['open_price'] = 0
                    positions[symbol]['open_fee'] = 0

        return processed_trades
    
    def get_largest_profit_trades(self, n):
        """获取盈利最大的 N 个交易"""
        if not self.trade_log or n <= 0:
            return []
        # 按盈利从大到小排序并取前 N 个
        return sorted(self.trade_log, key=lambda t: t['profit'], reverse=True)[:n]

    def get_largest_loss_trades(self, n):
        """获取亏损最大的 N 个交易"""
        if not self.trade_log or n <= 0:
            return []
        # 按盈利从小到大排序并取前 N 个
        return sorted(self.trade_log, key=lambda t: t['profit'])[:n]

    def calculate_average_holding_period(self):
        """计算平均持仓周期（天数）"""
        if not self.trade_log:
            return None
        total_days = sum((t['close_time'] - t['open_time']).days for t in self.trade_log)
        return total_days / len(self.trade_log)

    def calculate_win_rate(self):
        """胜率：盈利交易占比"""
        if not self.trade_log:
            return None
        wins = sum(1 for t in self.trade_log if t['profit'] > 0)
        return wins / len(self.trade_log)

    def calculate_avg_profit_loss_ratio(self):
        """平均盈亏比"""
        profits = [t['profit'] for t in self.trade_log if t['profit'] > 0]
        losses = [-t['profit'] for t in self.trade_log if t['profit'] < 0]

        if not profits or not losses:
            return None

        avg_profit = sum(profits) / len(profits)
        avg_loss = sum(losses) / len(losses)
        return avg_profit / avg_loss
    
    # ========== 新增类方法 ==========
    @staticmethod
    def translate_keys(data):
        """将字典列表中的英文字段名替换为中文"""
        # 字段映射表（英文 -> 中文）
        field_mapping = {
            "date": "日期",
            "value": "净值",
            "benchmark": "基准",
            "action": "操作",
            "code": "代码",
            "quantity": "数量",
            ##对应account的key
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
        """
        将 TradeRecord 对象列表转换为字典列表，保持字段名不变。

        :param transaction_records: 列表，元素为 TradeRecord 对象或字典
        :return: 格式化后的字典列表（字段名不变）
        """
        result = []
        for record in transaction_records:
            # 支持对象和字典两种格式
            if hasattr(record, '__dict__'):
                data = record.__dict__
            else:
                data = record

            formatted = {}
            for key, value in data.items():
                # 特殊字段值处理
                if key == 'volume':
                    formatted[key] = int(value)
                elif key == 'price' or key == 'fee':
                    formatted[key] = round(float(value), 2)
                elif key == 'side':
                    formatted[key] = '买入' if value == 'buy' else '卖出'
                elif key == 'created_at':
                    # 处理 pandas.Timestamp 并格式化时间
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
            'profit': f"{trade['profit']:.2f}",  # 盈亏，不转换绝对值
            'open_time': trade['open_time'].strftime('%Y-%m-%d'),
            'open_price': f"{trade['open_price']:.2f}",  # 开仓价格
            'open_fee': f"{trade['open_fee']:.2f}",  # 开仓费用
            'close_time': trade['close_time'].strftime('%Y-%m-%d'),
            'close_price': f"{trade['close_price']:.2f}",  # 平仓价格
            'close_fee': f"{trade['close_fee']:.2f}",  # 平仓费用
            'volume': f"{abs(trade['volume']):d}"  # 将 volume 转换为绝对值并格式化输出
        }
    # ========== 输出结果 相关方法 ==========

    def format_daily_assets(self):

        result = []
        #print(self.daily_total_assets)
        for date,assets in self.daily_total_assets.items(): #这里不是字典，而是对象
              # 时间格式化（如果是 pandas.Timestamp）
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
        final_assets = self.account.snapshots[-1].total_assets if self.account.snapshots else 0
        return_rate = self.calculate_return_rate() * 100
        #年化收益
        an_return_rate = self.calculate_annualized_return()*100
        sharpe_ratio = self.calculate_sharpe_ratio()
        max_drawdown, max_drawdown_start_date, max_drawdown_end_date = self.calculate_max_drawdown()
        avg_profit_loss_ratio = self.calculate_avg_profit_loss_ratio()
        avg_holding_period = self.calculate_average_holding_period()

        # 格式化最大回撤时段
        max_drawdown_period = f"{max_drawdown_start_date.strftime('%Y-%m-%d')} 至 {max_drawdown_end_date.strftime('%Y-%m-%d')}" if max_drawdown_start_date and max_drawdown_end_date else "N/A"

        metrics = [
            {"name": "初始资金", "value": f"{initial_cash:.2f}"},
            {"name": "最终资产", "value": f"{final_assets:.2f}"},
            {"name": "累计收益率", "value": f"{return_rate:.2f}%"},
            {"name": "年化收益率", "value": f"{an_return_rate:.2f}%"},
            {"name":"波动率", "value": f"{self.calculate_volatility():.2f}"},
            {"name": "夏普比率", "value": f"{sharpe_ratio:.2f}"},
            {"name": "最大回撤", "value": f"{max_drawdown * 100:.2f}%，时段：{max_drawdown_period}"},
            {"name": "平均盈亏比", "value": f"{avg_profit_loss_ratio:.2f}" if avg_profit_loss_ratio is not None else "N/A"},
            {"name": "平均持仓时间（天）", "value": f"{avg_holding_period:.2f}" if avg_holding_period is not None else "N/A"},
        ]


        net_value_data = self.format_daily_assets()
        largest_profit_trades = self.get_largest_profit_trades(5)
        largest_loss_trades = self.get_largest_loss_trades(5)

    
        formatted_transaction_log=self.format_transaction_log(self.account.trade_log)
        formatted_profit_trades = [self.format_trade(trade) for trade in largest_profit_trades]
        formatted_loss_trades = [self.format_trade(trade) for trade in largest_loss_trades]
        net_value_data_zh=self.translate_keys(net_value_data)
        formatted_transaction_log_zh=self.translate_keys(formatted_transaction_log)

        # 使用 json.dumps 处理数据，自动换行
        net_value_data_json = json.dumps(net_value_data_zh, indent=4, ensure_ascii=False)
        formatted_transaction_log_json = json.dumps(formatted_transaction_log_zh, indent=4, ensure_ascii=False)
        formatted_profit_trades_json = json.dumps(formatted_profit_trades, indent=4, ensure_ascii=False)
        formatted_loss_trades_json = json.dumps(formatted_loss_trades, indent=4, ensure_ascii=False)

        # 获取分析类所在文件的绝对路径，计算模板目录的绝对路径
        current_file_path = Path(__file__).resolve()
        template_dir = current_file_path.parent / "template"

        # 输出部分
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("nav_tradelog.html")

        html_content = template.render(
            report_name=report_name,
            metrics=metrics,
            net_value_data=net_value_data_json,
            transaction_data=formatted_transaction_log_json,
            largest_profit_trades=formatted_profit_trades_json,
            largest_loss_trades=formatted_loss_trades_json
        )

        # 获取调用该方法的文件所在目录
        frame = inspect.currentframe().f_back
        caller_file = frame.f_code.co_filename
        caller_dir = Path(caller_file).resolve().parent

        # 获取当前日期和时间（精确到分钟）
        current_datetime = datetime.now().strftime("%Y%m%d_%H%M")

        # 计算输出文件的路径，基于调用文件的目录，添加日期和时间到文件名
        output_path = caller_dir / output_dir / f"{report_name}_{current_datetime}.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"报告已生成至: {output_path}")