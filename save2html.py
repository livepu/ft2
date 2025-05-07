from jinja2 import Environment, FileSystemLoader
import os
import json
from datetime import datetime
def format_assets_snapshot(snapshots):
    """
    将 AccountSnapshot 列表转换为 HTML 需要的净值数据格式。
    
    :param snapshot: list of AccountSnapshot 对象
    :return: 列表格式 [{"date": "YYYY-MM-DD", "assets": float}]
    """
    result = []
    for item in snapshots: #这里不是字典，而是对象
        # 提取时间与总资产
        date = item.created_at
        assets = item.total_assets

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

def account_to_html(account,\
    metrics,report_name=None,template_dir='template', template_name='nav_tradelog.html', output_dir='.'):
    """
    生成账户净值和交易记录的 HTML 报告。
    :param account: Account 对象
    :param metrics: 关键指标数据，列表包含字典
    :param template_dir: 模板所在目录，默认为 'template'
    :param template_name: 模板文件名，默认为 'nav_tradelog.html'
    :param output_dir: 生成的 HTML 文件所在目录，默认为当前目录
    """
    net_value_data = format_assets_snapshot(account.snapshots)
    transaction_data = format_transaction_log(account.trade_log)
    generate_backtest_report(net_value_data, transaction_data, metrics,\
        report_name=report_name, template_dir=template_dir, template_name=template_name, output_dir=output_dir)




def generate_backtest_report(net_value_data, transaction_data, metrics,\
    report_name=None, template_dir='template', template_name='nav_tradelog.html', output_dir='.'):
    """
    生成回测报告 HTML 文件。

    :param net_value_data: 净值数据，列表包含字典
    :param transaction_data: 交易数据，列表包含字典
    :param metrics: 关键指标数据，列表包含字典
    :param template_dir: 模板所在目录，默认为 'template'
    :param template_name: 模板文件名，默认为 'nav_tradelog.html'
    :param output_dir: 生成的 HTML 文件所在目录，默认为当前目录
    """
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
        "order_id":"成交单号",
    }

    def translate_keys(data):
        """将字典列表中的英文字段名替换为中文"""
        return [{field_mapping.get(k, k): v for k, v in item.items()} for item in data]

    # 转换字段名
    net_value_data_zh = translate_keys(net_value_data)
    transaction_data_zh = translate_keys(transaction_data)

    # 使用 json.dumps 处理数据
    net_value_data_json = json.dumps(net_value_data_zh, indent=4, ensure_ascii=False)
    transaction_data_json = json.dumps(transaction_data_zh, indent=4, ensure_ascii=False)

    # 动态获取当前脚本所在目录，并构建模板路径
    current_dir = os.path.dirname(os.path.abspath(__file__))  # 获取当前脚本路径
    template_path = os.path.join(current_dir, template_dir)   # 构建模板路径

    # 配置 Jinja2 环境
    env = Environment(loader=FileSystemLoader(template_path))
    template = env.get_template(template_name)

    # 渲染模板并保存为 HTML 文件
    current_time = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = os.path.abspath(os.path.join(current_dir, output_dir)) 

    if report_name:
        filename = f"{report_name}_{current_time}.html"
    else:
        filename = f"backtest_report_{current_time}.html"
        report_name = "回测报告"

    output_path = os.path.join(output_dir, filename)


    html_content = template.render(
        net_value_data=net_value_data_json,
        transaction_data=transaction_data_json,
        metrics=metrics,
        title=f"{report_name}_{current_time}", #修订标题
    )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML 报告已生成：{os.path.abspath(output_path)}")

if __name__ == '__main__':
    # 示例数据
    net_value_data = [
        {"date": "2025-01-01", "value": 1.0, "benchmark": 1.01},
        {"date": "2025-01-02", "value": 1.02, "benchmark": 1.03},
        {"date": "2025-01-03", "value": 1.05, "benchmark": 1.06}
    ]
    transaction_data = [
        {"date": "2025-01-01", "action": "买入", "code": "SH600000", "quantity": 100, "price": 10.0},
        {"date": "2025-01-02", "action": "卖出", "code": "SH600000", "quantity": 50, "price": 10.2}
    ]
    metrics = [
        {"name": "初始资金", "value": "100000"},
        {"name": "最终净值", "value": "1.05"},
        {"name": "累计收益率", "value": "5.00%"},
        {"name": "夏普比率", "value": "1.20"}
    ]

    # 调用函数生成报告
    generate_backtest_report(net_value_data, transaction_data, metrics,report_name="测试",output_dir="../html_report")