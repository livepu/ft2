#这个是回测引擎，尽量精简导入的模块
from .storage import context  # 从data模块导入全局context
from .account import account #导入账户
import pandas as pd

#回测的数据驱动引擎
class Engine:
    def __init__(self):
        self.timeline = {} #按照时间轴存放bars
        self.cache_count=100

    #设置缓存长度
    def set_cache_count(self,cache_count):
        self.cache_count=cache_count

    ##在引擎内准备的所有数据按照时间轴，分离出对应的bar数据
    def add_data(self, symbol, freq, data):
        """
        将掘金格式的 bars 数据按照时间轴添加到对应的位置。

        :param symbol: 标的代码
        :param freq: 数据频率
        :param data: 掘金格式的 bars 数据列表或 DataFrame
        """
        if isinstance(data, pd.DataFrame):
            data = data.to_dict('records')

        # 获取订阅参数，针对不同品种，不同的缓存长度是合理的。注意策略初始化的时候先设置订阅参数。不然默认使用引擎参数初始化
        params = context.get_subscribe_params(symbol, freq)
        if params is None:
            # 如果没有订阅参数，使用默认字段和缓存大小
            sample_bar = data[0]
            fields = list(sample_bar.keys()) #提取全部字段
            count = self.cache_count
        else:
            # 使用订阅参数中的字段和缓存大小
            sample_bar = data[0]
            available_fields = set(sample_bar.keys())  # 数据源实际拥有的字段
            requested_fields = params['fields'] or list(available_fields)  # 订阅请求的字段(如果为None则取全部)

            # 取交集，确保只保留数据源存在的字段
            fields = [f for f in requested_fields if f in available_fields]
            count = params.get('count', self.cache_count)
            format=params.get('format')
        # 初始化缓存
        context._init_cache(symbol, freq, format=format, fields=fields, count=count)
        for bar in data:
            bar['symbol'] = symbol
            bar['frequency'] = freq
            eob = bar.get('eob') #掘金的时间带时区的，但这个类不做限制。是否统一时区，应该在策略里面完成。统一的时间格式
            if eob is None:
                continue
            if eob not in self.timeline:
                self.timeline[eob] = []
            # 直接将 bar 字典添加到对应时间的列表中
            self.timeline[eob].append(bar) #一个时间点上，多个品种的数据

    def run(self,strategy_class,start_time, end_time):
        """
        按照时间轴，逐次给context._add_bar2bar_data_cache添加数据，当时间轴运行到start_time和end_time之间时，运行策略。
        """
        strategy = strategy_class()
        sorted_times = sorted(self.timeline.keys())
        begin_snapshot=0
        last_time=None
        for current_time in sorted_times:
            context._current_time = current_time #传入时间点
            bars_at_current_time = self.timeline[current_time]  #找到bars
            for bar in bars_at_current_time:
                context._add_bar2bar_data_cache(bar) #持续添加数据，直到在时间段内执行策略
            if start_time <= current_time <= end_time: #时间段之外，自动补充。保证运行的数据足够长。时间段内，运行策略
                if begin_snapshot==0 and last_time is not None:
                    
                    account.take_snapshot(last_time) #快照需要有插入时间的才行，不然没法按照前一交易日作为基准
                    begin_snapshot=1
                strategy.on_bar(context,bars_at_current_time)
                #on_bar之后，执行账户的快照。后续通过快照分析净值
                account.take_snapshot()
            last_time=current_time

engine=Engine() #全局的引擎实例，供策略调用。