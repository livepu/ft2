#通过account的快照，分析结果
from collections import defaultdict
from datetime import date, timedelta #添加时间间隔
from dateutil.relativedelta import relativedelta

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

def calculate_return_rate(daily_total_assets, time_interval=None):
    """
    计算不同时间间隔的收益率。

    :param daily_total_assets: 一个字典，键为日期（datetime.date 对象），值为该日的总资产
    :param time_interval: 时间间隔，可选值为 'all', '1m', '3m', '6m', '1y', '2y', '3y', '5y'，默认为 'all'
    :return: 对应时间间隔的收益率（小数形式），若时间跨度不满足要求则返回 None
    """
    if not daily_total_assets:
        return None

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
        closest_start_date = start_date  # 全区间时，直接使用第一个日期
    elif time_interval in interval_mapping:
        start_date = end_date - interval_mapping[time_interval]
        # 检查时间跨度是否满足要求
        if start_date < dates[0]:
            return None
        # 找到最接近 start_date 且小于它的日期，即区间前一交易日作为基准
        closest_start_date = max((d for d in dates if d < start_date), default=None)
        if closest_start_date is None:
            return None
    else:
        return None

    start_value = daily_total_assets[closest_start_date]
    end_value = daily_total_assets[end_date]

    return (end_value - start_value) / start_value