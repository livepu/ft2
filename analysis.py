#通过account的快照，分析结果
from collections import defaultdict

from dateutil.relativedelta import relativedelta
import math

def get_daily_total_assets(snapshots):
    """
    从账户快照列表中提取每日最后一个快照的总资产。

    :param snapshots: 账户快照列表，每个元素为 AccountSnapshot 实例
    :return: 一个字典，键为日期（datetime.date 对象），值为该日最后一个快照的总资产
    """
    daily_snapshots = defaultdict(list)
    # 按日期分组快照
    for snapshot in snapshots:
        date = snapshot.created_at.date()
        daily_snapshots[date].append(snapshot)

    daily_total_assets = {}
    # 遍历每个日期，取该日最后一个快照的总资产
    for date, snapshots_on_date in daily_snapshots.items():
        last_snapshot = snapshots_on_date[-1]
        daily_total_assets[date] = last_snapshot.total_assets

    return daily_total_assets

def calculate_max_drawdown(daily_total_assets):
    """
    计算每日总资产数据的最大回撤。

    :param daily_total_assets: 一个字典，键为日期（datetime.date 对象），值为该日的总资产
    :return: 最大回撤比例（小数形式），最大回撤开始日期，最大回撤结束日期
    """
    if not daily_total_assets:
        return 0, None, None

    dates = sorted(daily_total_assets.keys())
    max_drawdown = 0
    peak_value = daily_total_assets[dates[0]]
    start_date = end_date = peak_date = None

    for date in dates:
        current_value = daily_total_assets[date]
        if current_value > peak_value:
            peak_value = current_value
            peak_date = date #峰值和日期
        drawdown = (peak_value - current_value) / peak_value
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            start_date = peak_date
            end_date = date

    return max_drawdown, start_date, end_date

def get_start_end_date(daily_total_assets, time_interval):
    """
    计算不同时间间隔对应的起始日期和结束日期。

    :param daily_total_assets: 一个字典，键为日期（datetime.date 对象），值为该日的总资产
    :param time_interval: 时间间隔，可选值为 'all', '1m', '3m', '6m', '1y', '2y', '3y', '5y'
    :return: 起始日期和结束日期元组，若时间跨度不满足要求则返回 (None, None)
    """
    if not daily_total_assets:
        return None, None
    
    dates = sorted(daily_total_assets.keys())
    end_date = dates[-1]

    # 定义 time_interval 到 relativedelta 参数的映射
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
        # 检查时间跨度是否满足要求
        if start_date < dates[0]:
            return None, None
        # 找到小于start_date的最大值 。区间前一交易日作为基准
        closest_start_date = max((d for d in dates if d < start_date), default=None)
        if closest_start_date is None:
            return None, None
        start_date = closest_start_date
    else:
        return None, None

    return start_date, end_date

def calculate_return_rate(daily_total_assets, time_interval=None):
    """
    计算不同时间间隔的收益率。

    :param daily_total_assets: 一个字典，键为日期（datetime.date 对象），值为该日的总资产
    :param time_interval: 时间间隔，可选值为 'all', '1m', '3m', '6m', '1y', '2y', '3y', '5y'，默认为 'all'
    :return: 对应时间间隔的收益率（小数形式），若时间跨度不满足要求则返回 None
    """
    start_date, end_date = get_start_end_date(daily_total_assets, time_interval)
    if start_date is None or end_date is None:
        return None


    start_value = daily_total_assets[start_date]
    end_value = daily_total_assets[end_date]

    return (end_value - start_value) / start_value

def calculate_annualized_return(daily_total_assets, time_interval=None):
    """
    计算不同时间间隔的年化收益率。

    :param daily_total_assets: 一个字典，键为日期（datetime.date 对象），值为该日的总资产
    :param time_interval: 时间间隔，可选值为 'all', '1m', '3m', '6m', '1y', '2y', '3y', '5y'，默认为 'all'
    :return: 对应时间间隔的年化收益率（小数形式），若时间跨度不满足要求则返回 None
    """
    # 先计算区间收益率
    interval_return = calculate_return_rate(daily_total_assets, time_interval)
    if interval_return is None:
        return None

    start_date, end_date = get_start_end_date(daily_total_assets, time_interval)
    if start_date is None or end_date is None:
        return None

    # 计算区间天数
    days = (end_date - start_date).days
    if days == 0:
        return 0

    # 计算年化收益率
    annualized_return = ((1 + interval_return) ** (365 / days)) - 1
    return annualized_return

def calculate_daily_returns(daily_total_assets):
    """
    计算每日收益率。

    :param daily_total_assets: 一个字典，键为日期（datetime.date 对象），值为该日的总资产
    :return: 每日收益率列表
    """
    dates = sorted(daily_total_assets.keys())
    daily_returns = []
    for i in range(1, len(dates)):
        prev_value = daily_total_assets[dates[i - 1]]
        current_value = daily_total_assets[dates[i]]
        daily_return = (current_value - prev_value) / prev_value
        daily_returns.append(daily_return)
    return daily_returns

def calculate_volatility(daily_total_assets, time_interval=None):
    """
    计算不同时间间隔的波动率。

    :param daily_total_assets: 一个字典，键为日期（datetime.date 对象），值为该日的总资产
    :param time_interval: 时间间隔，可选值为 'all', '1m', '3m', '6m', '1y', '2y', '3y', '5y'，默认为 'all'
    :return: 对应时间间隔的波动率（小数形式），若时间跨度不满足要求则返回 None
    """
    start_date, end_date = get_start_end_date(daily_total_assets, time_interval)
    if start_date is None or end_date is None:
        return None

    # 筛选对应时间区间的资产数据
    interval_assets = {date: value for date, value in daily_total_assets.items() if date >= start_date}
    daily_returns = calculate_daily_returns(interval_assets)

    if not daily_returns:
        return None

    # 计算平均收益率
    mean_return = sum(daily_returns) / len(daily_returns)
    # 计算方差
    variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
    # 计算标准差，即波动率
    volatility = math.sqrt(variance)
    return volatility


def calculate_sharpe_ratio(daily_total_assets, risk_free_rate=0.02, time_interval=None):
    """
    计算不同时间间隔的夏普比率。

    :param daily_total_assets: 一个字典，键为日期（datetime.date 对象），值为该日的总资产
    :param risk_free_rate: 无风险利率，默认为 0.02
    :param time_interval: 时间间隔，可选值为 'all', '1m', '3m', '6m', '1y', '2y', '3y', '5y'，默认为 'all'
    :return: 对应时间间隔的夏普比率（小数形式），若时间跨度不满足要求则返回 None
    """
    # 计算区间年化收益率
    annualized_return = calculate_annualized_return(daily_total_assets, time_interval)
    if annualized_return is None:
        return None

    # 计算区间年化波动率
    volatility = calculate_volatility(daily_total_assets, time_interval)
    if volatility is None:
        return None

    # 计算夏普比率
    sharpe_ratio = (annualized_return - risk_free_rate) / volatility
    return sharpe_ratio

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

    def calculate_return_rate(self, time_interval=None):
        start_date, end_date = self._get_start_end_date(time_interval)
        if not start_date or not end_date:
            return None

        start_value = self.daily_total_assets[start_date]
        end_value = self.daily_total_assets[end_date]
        return (end_value - start_value) / start_value

    def calculate_annualized_return(self, time_interval=None):
        interval_return = self.calculate_return_rate(time_interval)
        if interval_return is None:
            return None

        start_date, end_date = self._get_start_end_date(time_interval)
        days = (end_date - start_date).days
        if days == 0:
            return 0

        return ((1 + interval_return) ** (365 / days)) - 1

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
        volatility = math.sqrt(variance)
        return volatility

    def calculate_sharpe_ratio(self, risk_free_rate=0.02, time_interval=None):
        annualized_return = self.calculate_annualized_return(time_interval)
        volatility = self.calculate_volatility(time_interval)

        if annualized_return is None or volatility is None:
            return None

        return (annualized_return - risk_free_rate) / volatility

    def _calculate_daily_returns(self, daily_assets):
        dates = sorted(daily_assets.keys())
        returns = []
        for i in range(1, len(dates)):
            prev = daily_assets[dates[i - 1]]
            curr = daily_assets[dates[i]]
            returns.append((curr - prev) / prev)
        return returns

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
    def _calculate_profit(self, trade_log):
        """
        计算每笔交易的盈亏
        :param trade_log: 原始交易记录列表
        :return: 包含盈亏信息的交易记录列表
        """
        positions = defaultdict(lambda: {'volume': 0, 'cost': 0, 'open_time': None})
        processed_trades = []

        for trade in trade_log:
            symbol = trade.symbol
            volume = trade.volume
            price = trade.price
            side = trade.side
            created_at = trade.created_at
            fee = trade.fee

            if side == 'buy':
                # 买入操作，更新持仓信息，成本加上手续费
                positions[symbol]['volume'] += volume
                # 买入成本加上手续费
                positions[symbol]['cost'] += volume * price + fee
                if positions[symbol]['open_time'] is None:
                    positions[symbol]['open_time'] = created_at
            elif side == 'sell':
                # 卖出操作，计算盈亏
                if positions[symbol]['volume'] == 0:
                    continue  # 无持仓，跳过

                sell_amount = volume * price
                # 按比例计算卖出部分的成本
                cost = (volume / positions[symbol]['volume']) * positions[symbol]['cost']
                profit = sell_amount - cost - fee

                processed_trades.append({
                    'symbol': symbol,
                    'profit': profit,
                    'open_time': positions[symbol]['open_time'],
                    'close_time': created_at,
                    'original_trade': trade
                })

                # 更新持仓信息
                positions[symbol]['volume'] -= volume
                positions[symbol]['cost'] -= cost

                if positions[symbol]['volume'] == 0:
                    positions[symbol]['open_time'] = None

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
