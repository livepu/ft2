import sys
import os

# 获取 ft2 包所在的目录路径。改造ft2包后，内部调用需要绝对路径
ft2_parent_package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 将该目录添加到 sys.path 中
sys.path.insert(0, ft2_parent_package_dir)
'''
from ft2.storage import context
from ft2.account import account
from ft2.engine import Engine
'''
from ft2 import context, account, engine
import pytz
from gm.api import *
set_serv_addr('192.168.88.100:7001') #设置本地服务器测试ok
set_token('c3ec405e3ebcfc3e0830483200ecbdeedffb3024')

import datetime
import pandas as pd



class 动量策略:
    def __init__(self):
        context.mode='backtest' #回测模式，自动调整context.now
        context.list_index=['SZSE.399317','SHSE.000300']
        context.subscribe(symbols=context.list_index,freq='1d',count=200)
        # 直接使用GM Quant API加载数据
        for symbol in context.list_index:
        
            df = history(symbol=symbol,frequency='1d',start_time='2019-01-01', end_time='2024-12-31', fields='open,high,low,close,eob',adjust=ADJUST_NONE,df=True)
            
            if df is not None:
                #print(df)
                #print(f"Type of eob: {type(df['eob'][0])}")
                engine.add_data(symbol, '1d', df)


    def on_bar(self,context, bars):
        #print("bars内容：",bars)
        data=context.data('SHSE.000300','1d',count=1)
        df=pd.DataFrame(data)
        print("df内容：",df)
        print("now:",context.now)
        latest_close = data[-1]['close']
        
        account.order_volume('SHSE.000300', 1, latest_close)
        print("account.get_account()",account.get_account())
        print("account.get_positions()",account.get_positions())

# 获取东八区时区
tz = pytz.timezone('Asia/Shanghai')
# 将 start_time 和 end_time 转换为有时区信息的对象
start_time = datetime.datetime(2023, 1, 1).replace(tzinfo=tz)
end_time = datetime.datetime(2023, 1, 10).replace(tzinfo=tz)



engine.run(动量策略,start_time=start_time, end_time=end_time)  

print("account.snapshots",account.snapshots)#好了，这里基本快照完成了。挺好的效果
print("account.get_orders()",account.get_orders())#获取历史成交