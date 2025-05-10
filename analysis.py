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
        初始化 AccountAnalyzer 实例。
        
        :param account: Account 实例，应包含：
                        - snapshots: AccountSnapshot 列表（每个快照包含 created_at 和 total_assets）
                        - trade_log: Trade 记录列表（需有 symbol, profit, open_time, close_time 等字段）
        :param external_daily_total_assets: 外部导入的日度总资产数据，字典类型，键为日期，值为总资产
        """
        self.account = account
        if account:
            # 从 account 实例初始化日度资产数据
            self._daily_total_assets = self._compute_daily_total_assets(account.snapshots)
            # 从 account.trade_log 中提取交易记录并计算每笔交易的盈亏，生成 self._trade_profits。整理过的交易记录，分析盈亏用的
            self._trade_profits = self._calculate_profit(account.trade_log) 
        elif external_daily_total_assets:
            # 使用外部提供的日度总资产数据初始化
            self._daily_total_assets = external_daily_total_assets
            self._trade_profits = []  # 若无交易记录，则不分析交易数据
        else:
            # 如果没有传入任何数据，则初始化为空数据结构
            self._daily_total_assets = {}
            self._trade_profits = []
    @property
    def daily_total_assets(self):
        return self._daily_total_assets.copy()  # 返回副本防止被修改

    @property
    def trade_profits(self):
        return self._trade_profits.copy()  # 返回副本防止被修改
    def _compute_daily_total_assets(self, snapshots):
        """
        根据 AccountSnapshot 列表中的 created_at 时间戳，按天聚合获取每日最新的总资产。
        
        :param snapshots: AccountSnapshot 对象列表，每个对象包含 created_at（datetime）和 total_assets（float）
        :return: 字典，键为日期（date），值为该日最后一笔快照的 total_assets 值
        """
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
        return self._daily_total_assets
    

    def calculate_max_drawdown(self):
        """
        计算最大回撤（最大资产从峰值到谷值的跌幅）

        :return: (max_drawdown: float, start_date: date, end_date: date)
                max_drawdown 表示最大回撤比例（0~1）
        :rtype: tuple(float, datetime.date, datetime.date)
        """
        # 如果每日总资产数据为空，则返回默认值
        if not self._daily_total_assets:
            return 0, None, None

        # 对每日总资产的日期进行排序
        dates = sorted(self._daily_total_assets.keys())
        # 初始化最大回撤为0，起始日期和结束日期为第一个日期
        max_drawdown = 0
        peak_value = self._daily_total_assets[dates[0]]
        start_date = end_date = peak_date = dates[0]

        # 遍历所有日期计算最大回撤
        for date in dates:
            current_value = self._daily_total_assets[date]
            # 如果当前值大于峰值，则更新峰值及其日期
            if current_value > peak_value:
                peak_value = current_value
                peak_date = date
            # 计算当前回撤
            drawdown = (peak_value - current_value) / peak_value
            # 如果当前回撤大于已知的最大回撤，则更新最大回撤及其起始和结束日期
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                start_date = peak_date
                end_date = date
        if max_drawdown == 0:
            return 0, None, None  # 明确无回撤情况
        # 返回最大回撤及其起始和结束日期
        return max_drawdown, start_date, end_date
    def calculate_return_rate(self, time_interval=None):
        """
        计算指定时间区间的收益率（结束资产 / 开始资产 - 1）。

        :param time_interval: 可选的时间区间字符串，如 '1y'、'3m'，或 'all' 表示全周期
        :return: 收益率（float），若数据不足则返回 None
        """
        start_date, end_date = self._get_start_end_date(time_interval)
        if not start_date or not end_date:
            return None

        start_value = self._daily_total_assets[start_date]
        end_value = self._daily_total_assets[end_date]
        if start_value == 0:
            raise ValueError("初始资产不能为零")
        return (end_value - start_value) / start_value
    

    def calculate_annualized_return(self, time_interval=None):
        """
        计算年化收益率：(1 + 区间收益率) ^ (365 / 天数) - 1

        :param time_interval: 可选的时间区间字符串
        :return: 年化收益率（float），若数据不足则返回 None
        """
        interval_return = self.calculate_return_rate(time_interval)
        if interval_return is None:
            return None

        start_date, end_date = self._get_start_end_date(time_interval)
        days = (end_date - start_date).days
        if days == 0:
            return 0
        if interval_return <= -1:  # 亏损超过100%，年化无意义
            raise ValueError("亏损超过100%，无法计算年化收益率")
        return ((1 + interval_return) ** (365 / days)) - 1
    

    def calculate_volatility(self, time_interval=None):
        """
        计算给定时间区间内的年化波动率。
        
        参数:
        time_interval (str, 可选): 时间区间，如"1Y"代表一年。默认为None，使用整个数据集。
        
        返回:
        float: 年化波动率。如果数据不足或计算错误，返回None。
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

        return annualized_volatility#计算夏普比率
    
    def calculate_sharpe_ratio(self, risk_free_rate=0.02, time_interval=None):
        """
        计算夏普比率：(年化收益率 - 无风险利率) / 波动率

        :param risk_free_rate: 无风险利率，默认为 0.02（即 2%）
        :param time_interval: 可选的时间区间字符串
        :return: 夏普比率（float），若数据不足则返回 None
        """
        annualized_return = self.calculate_annualized_return(time_interval)
        volatility = self.calculate_volatility(time_interval)

        if annualized_return is None or volatility is None:
            return None

        return (annualized_return - risk_free_rate) / volatility


    def _calculate_daily_returns(self, daily_assets):
        """
        根据每日总资产数据，计算每日收益率（当前值 / 上一日值 - 1）

        :param daily_assets: 字典，键为日期，值为总资产
        :return: 列表，包含每日收益率
        """
        dates = sorted(daily_assets.keys())
        returns = []
        for i in range(1, len(dates)):
            prev = daily_assets[dates[i - 1]]
            curr = daily_assets[dates[i]]
            returns.append((curr - prev) / prev)
        return returns


    def _get_start_end_date(self, time_interval):
        """
        根据时间区间字符串，计算起止日期。

        :param time_interval: 时间区间字符串，如 '1y', '3m'
        :return: (start_date, end_date)，若无效则返回 (None, None)
        """
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

    # ========== 交易相关方法 ==========
    #注意在初始化调用
    def _calculate_profit(self, trade_log):
        """
        计算每笔交易的盈亏，并返回格式化的交易记录。

        :param trade_log: 原始交易记录列表，每个元素为一个 Trade 对象
        :return: 包含盈亏信息的交易记录列表，每个元素是一个字典，包含：
                - symbol: 交易标的
                - profit: 盈亏金额
                - open_time: 开仓时间
                - close_time: 平仓时间
                - volume: 交易数量（绝对值）
                - original_trade: 原始交易对象
        """
        positions = defaultdict(lambda: {'volume': 0, 'cost': 0, 'open_time': None, 'open_price': 0, 'open_fee': 0})
        processed_trades = []

        for trade in trade_log:
            if trade.volume == 0 or math.isnan(trade.price):
                continue  # 跳过无效交易
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
        """获取盈利最大的 N 个交易"""
        if not self._trade_profits or n <= 0:
            return []
        # 按盈利从大到小排序并取前 N 个
        return sorted(self._trade_profits, key=lambda t: t['profit'], reverse=True)[:n]

    def get_largest_loss_trades(self, n):
        """获取亏损最大的 N 个交易"""
        if not self._trade_profits or n <= 0:
            return []
        # 按盈利从小到大排序并取前 N 个
        return sorted(self._trade_profits, key=lambda t: t['profit'])[:n]

    def calculate_average_holding_period(self):
        """计算平均持仓周期（天数）"""
        if not self._trade_profits:
            return None
        total_days = sum((t['close_time'] - t['open_time']).days for t in self._trade_profits)
        return total_days / len(self._trade_profits)

    def calculate_win_rate(self):
        """胜率：盈利交易占比"""
        if not self._trade_profits:
            return None
        wins = sum(1 for t in self._trade_profits if t['profit'] > 0)
        return wins / len(self._trade_profits)

    def calculate_avg_profit(self) -> float:
        """
        计算所有盈利交易的平均盈利（绝对金额）
        :return: 平均盈利，若无盈利交易则返回 None
        """
        profits = [t['profit'] for t in self._trade_profits if t['profit'] > 0]
        return sum(profits) / len(profits) if profits else None

    def calculate_avg_loss(self) -> float:
        """
        计算所有亏损交易的平均亏损（绝对金额）
        :return: 平均亏损，若无亏损交易则返回 None
        """
        losses = [t['profit'] for t in self._trade_profits if t['profit'] < 0]
        return sum(losses) / len(losses) if losses else None
    def calculate_avg_profit_loss_ratio(self) -> float:
        """
        计算平均盈亏比（平均盈利 / 平均亏损的绝对值）
        :return: 盈亏比，若无盈利或亏损则返回 None
        """
        avg_profit = self.calculate_avg_profit()
        avg_loss = self.calculate_avg_loss()
        if avg_profit is None or avg_loss is None:
            return None
        return avg_profit / abs(avg_loss)  # 保证比值为正
    
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
        #print(self._daily_total_assets)
        for date,assets in self._daily_total_assets.items(): #这里不是字典，而是对象
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
        """
        将回测结果生成HTML报告。

        参数:
        - report_name: str, 报告的名称，默认为"回测报告"。
        - output_dir: str, 报告输出的目录，默认为当前目录"."。

        返回值:
        无直接返回值，但会生成HTML报告并保存到指定路径。
        """
        # 获取初始资金和最终资产值
        initial_cash = self.account.snapshots[0].cash if self.account.snapshots else 0
        final_assets = self.account.snapshots[-1].total_assets if self.account.snapshots else 0
        # 计算累计收益率
        return_rate = self.calculate_return_rate() * 100
        # 年化收益
        an_return_rate = self.calculate_annualized_return()*100
        # 计算夏普比率
        sharpe_ratio = self.calculate_sharpe_ratio()
        # 计算最大回撤及其时段
        max_drawdown, max_drawdown_start_date, max_drawdown_end_date = self.calculate_max_drawdown()
        # 计算平均盈利和平均亏损
        avg_profit = self.calculate_avg_profit()
        avg_loss = self.calculate_avg_loss()

        # 计算平均盈亏比
        avg_profit_loss_ratio = self.calculate_avg_profit_loss_ratio()
        # 计算平均持仓时间
        avg_holding_period = self.calculate_average_holding_period()

        # 格式化最大回撤时段
        max_drawdown_period = f"{max_drawdown_start_date.strftime('%Y-%m-%d')} 至 {max_drawdown_end_date.strftime('%Y-%m-%d')}" if max_drawdown_start_date and max_drawdown_end_date else "N/A"
        # 获取回测的日期范围
        dates = sorted(self._daily_total_assets.keys())
        start_date = dates[1] if dates else None
        end_date = dates[-1] if dates else None

        # 格式化回测区间
        backtest_period = f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}" if start_date and end_date else "N/A"

        # 准备业绩指标数据
        metrics = [
            {"name": "回测区间", "value": backtest_period},  # 新增的回测区间指标
            {"name": "初始资金", "value": f"{initial_cash:.2f}"},
            {"name": "最终资产", "value": f"{final_assets:.2f}"},
            {"name": "累计收益率", "value": f"{return_rate:.2f}%"},
            {"name": "年化收益率", "value": f"{an_return_rate:.2f}%"},
            {"name":"年化波动率", "value": f"{self.calculate_volatility()*100:.2f}%"},
            {"name": "夏普比率", "value": f"{sharpe_ratio:.2f}"},
            {"name": "最大回撤", "value": f"{max_drawdown * 100:.2f}%，时段：{max_drawdown_period}"},
            {
                "name": "平均盈亏比",
                "value": f"{avg_profit_loss_ratio:.2f}（平均盈利{avg_profit * 100:.2f}%，平均亏损{abs(avg_loss) * 100:.2f}%）" 
                        if avg_profit_loss_ratio is not None and avg_profit is not None and avg_loss is not None 
                        else "N/A"
            },
            {"name": "平均持仓时间（天）", "value": f"{avg_holding_period:.2f}" if avg_holding_period is not None else "N/A"},
        ]

        # 准备净值数据、最大盈利和亏损交易
        net_value_data = self.format_daily_assets()
        largest_profit_trades = self.get_largest_profit_trades(5)
        largest_loss_trades = self.get_largest_loss_trades(5)

        # 格式化交易日志和盈亏交易
        formatted_transaction_log=self.format_transaction_log(self.account.trade_log)
        formatted_profit_trades = [self.format_trade(trade) for trade in largest_profit_trades]
        formatted_loss_trades = [self.format_trade(trade) for trade in largest_loss_trades]
        # 中文化翻译
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

        # 写入HTML报告
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"报告已生成至: {output_path}")