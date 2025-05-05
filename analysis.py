#通过account的快照，分析结果
from collections import defaultdict

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

