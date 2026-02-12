import datetime
#import collections
from collections import defaultdict, deque
from typing import Dict, List,Union
import pandas as pd
import logging
logger = logging.getLogger(__name__)
#我这个类，不嵌入账户管理
class Context:
    def __init__(self):
        # 数据存储
        self._cache = _Cache()  # 直接使用原版Cache实现
        self._subscribed = {}  # 改为字典存储订阅详情
        self.bar_data_set = set()  # 添加bar数据去重集合
        
        # 状态管理
        self.mode = None  # 'backtest'/'live'
        self._current_time = None
  

    def is_backtest_model(self):
        return self.mode == 'backtest'

    @property 
    def now(self):
        return self._current_time if self.mode == 'backtest' else datetime.datetime.now()
    
    def subscribe(self, symbols: Union[str, List[str]], freq='1d', count=100, fields=None,format='df'):
        """记录订阅参数"""
        if isinstance(symbols, str):
            symbols = [symbols]
            
        for symbol in symbols:
            self._subscribed[(symbol, freq)] = {
                'fields': fields,
                'count': count,
                'format': format
            }
            # 注意：这里不调用_init_cache

    def get_subscribe_params(self, symbol: str, freq: str) -> dict:
        """获取订阅参数"""
        return self._subscribed.get((symbol, freq))

    def unsubscribe(self, symbols: Union[str, List[str]], freq='1d'):
        """取消订阅"""
        if isinstance(symbols, str):
            symbols = [symbols]
            
        for symbol in symbols:
            if (symbol, freq) in self._subscribed:
                del self._subscribed[(symbol, freq)]
                self._rm_cache(symbol, freq)
    @property  
    def symbols(self, freq=None):
        """获取已订阅的品种列表"""
        if freq:
            return {s[0] for s in self._subscribed if s[1] == freq}
        return {s[0] for s in self._subscribed}
    
    def _add_bar2bar_data_cache(self, bar):
        # type: (Text, Dict[Text, Any]) -> None
        kk = (bar["symbol"], bar["frequency"], bar["eob"])
        if kk in self.bar_data_set:
            logger.debug("bar data %s 已存在, 跳过不加入", kk)
        else:
            context._add_data_to_cache(bar["symbol"], bar["frequency"], bar)
            self.bar_data_set.add(kk)

    #这里和掘金的不同，返回dict。可以自行转换
    def data(self, symbol: str, frequency: str, count: int = 1,fields: Union[str, List[str]] = None):
        """
        获取数据滑窗（与掘金API兼容）
        :param symbol: 标的代码
        :param frequency: 频率
        :param count: 获取条数
        :param fields: 需要返回的字段，可以是字符串或列表
        :param format: 返回格式 'row'/'col'/'pd'
        :return: 字典列表或DataFrame
        """
        if not frequency:
            frequency = "1d"
        
        if count < 1:
            count = 1
            
        # 获取原始数据
        raw_data = self._cache.get_data(symbol, frequency, count, fields)
                
        return raw_data

    
    def _init_cache(self, symbol, freq, format, fields, count):
        self._cache.init_cache(symbol, freq, format, fields, count)

    def _has_cache(self, symbol, freq):
        return self._cache.has_cache(symbol, freq)

    def _rm_cache(self, symbol, freq):
        self._cache.rm_cache(symbol, freq)

    def _add_data_to_cache(self, symbol, freq, data):
        if data is None:
            return
        self._cache.add_data(symbol, freq, data)

# 以下是原版Cache类的实现，保持不变。管理的是字典数据
class _Cache:
    def __init__(self):
        self._col_cache = {} # type: Dict[str, _ColQuote]
        self._row_cache = {} # type: Dict[str, _RowQuote]
        self._initialized = set()
        self._data_loader = None  # 新增数据加载器

    def set_data_loader(self, loader):
        """设置自定义数据加载器"""
        self._data_loader = loader
    def init_cache(self, symbol, freq, format, fields, count):
        key = (symbol, freq)
        if format == "col":
            self._col_cache[key] = _ColQuote(symbol, freq, format, fields, count)
        else:
            self._row_cache[key] = _RowQuote(symbol, freq, format, fields, count)

        if key in self._initialized:
            self._initialized.remove(key)

    def rm_cache(self, symbol, freq):
        key = (symbol, freq)
        if key in self._col_cache:
            del self._col_cache[key]
        if key in self._row_cache:
            del self._row_cache[key]
        if key in self._initialized:
            self._initialized.remove(key)

    def has_cache(self, symbol, freq):
        key = (symbol, freq)
        if key in self._col_cache:
            return True
        if key in self._row_cache:
            return True
        return False

    def add_data(self, symbol, freq, data: Dict):
        key = (symbol, freq)
        if key in self._col_cache:
            self._col_cache[key].add_data(data)
        if key in self._row_cache:
            self._row_cache[key].add_data(data)

    def get_data(self, symbol, freq, count, fields):
        key = (symbol, freq)
        # 优先查找列缓存，否则查找行缓存
        if key in self._col_cache:
            q = self._col_cache[key]
        elif key in self._row_cache:
            q = self._row_cache[key]
        else:
            raise ValueError(f"请先订阅{symbol}的{freq}周期数据")

        if key not in self._initialized:
            miss_count = q.miss_count(count)
            if miss_count != 0 and self._data_loader:  # 使用数据加载器
                data = self._data_loader.load_history(
                    symbol=symbol,
                    frequency=freq,
                    count=miss_count+1,
                    end_time=q.earliest_time() or datetime.datetime.now()
                )
                if freq == "1d":
                    for item in data[::-1]:
                        if 'eob' in item:  # 确保包含时间字段
                            item["eob"] = item["eob"].replace(hour=15, minute=15, second=1)
                            if context.now < item["eob"]:
                                continue
                        q.add_data(item, left=True)
                else:
                    for item in data[::-1]:
                        q.add_data(item, left=True)
            self._initialized.add(key)

        return q.get_data(fields, count)


class _RowQuote:
    def __init__(self, symbol, freq, format, fields, count):
        self._symbol = symbol
        self._freq = freq
        self._format = format
        self._fields = fields
        self._earliest_time = None
        self._data = deque(maxlen=count) #collections.deque

    def add_data(self, data: Dict, left=False):
        if left and self.full():
            return
        if left and self._earliest_time is not None:
            if (self._freq == "tick") and (data["created_at"] >= self._earliest_time):
                return
            if (self._freq != "tick") and (data["eob"] >= self._earliest_time):
                return
        if self._earliest_time is None:
            if self._freq == "tick":
                self._earliest_time = data["created_at"]
            else:
                self._earliest_time = data["eob"]
        newdata = {}
        for field in self._fields:
            newdata[field] = data.get(field)
        if left:
            self._data.appendleft(newdata)
            return
        self._data.append(newdata)

    def get_data(self, fields, count):
        data_len = len(self._data)
        start = data_len - count
        if start < 0:
            start = 0
        result = []
        for i in range(start, data_len):
            if not fields:
                result.append(self._data[i])
            else:
                result.append({k: v for k, v in self._data[i].items() if k in fields})
        if self._format == "df":
            return pd.DataFrame(result)
        return result

    def miss_count(self, count):
        if count <= len(self._data):
            return 0
        return self._data.maxlen - len(self._data)

    def earliest_time(self):
        return self._earliest_time

    def full(self):
        return len(self._data) == self._data.maxlen


class _ColQuote:
    def __init__(self, symbol, freq, format, fields, count):
        self._symbol = symbol
        self._freq = freq
        self._format = format
        self._fields = fields
        self._earliest_time = None
        self._data = {} # type: Dict[str, collections.deque]
        for field in fields:
            if field == "symbol":
                continue
            self._data[field] = deque(maxlen=count) #collections.deque

    def add_data(self, data: Dict, left=False):
        if left and self.full():
            return
        if left and self._earliest_time is not None:
            if (self._freq == "tick") and (data["created_at"] >= self._earliest_time):
                return
            if (self._freq != "tick") and (data["eob"] >= self._earliest_time):
                return
        if self._earliest_time is None:
            if self._freq == "tick":
                self._earliest_time = data["created_at"]
            else:
                self._earliest_time = data["eob"]
        for field in self._fields:
            if field == "symbol": # 所有的symbol都一样,不需要队列保存
                continue
            if field in ["bid_p", "bid_v", "ask_p", "ask_v"]:
                quotes = data.get("quotes")
                if quotes and len(quotes) != 0:
                    item = quotes[0].get(field)
                else:
                    item = None
            else:
                item = data.get(field)
            if left:
                self._data[field].appendleft(item)
                continue
            self._data[field].append(item)

    def get_data(self, fields, count):
        if not fields:
            fields = self._fields
        result = {}
        for field in self._fields:
            if field not in fields:
                continue
            if field == "symbol" and field in fields:
                result["symbol"] = self._symbol
                continue
            q = self._data[field]
            q_len = len(q)
            start = q_len - count
            if start < 0:
                start = 0
            l = []
            for i in range(start, q_len):
                l.append(q[i])
            result[field] = l
        return result

    def miss_count(self, count):
        for q in self._data.values():
            if count <= len(q):
                return 0
            return q.maxlen - len(q)

    def earliest_time(self):
        return self._earliest_time

    def full(self):
        for q in self._data.values():
            return len(q) == q.maxlen




context=Context() # 全局上下文实例