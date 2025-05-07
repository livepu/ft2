from jinja2 import Environment, FileSystemLoader
import os
import json
from datetime import datetime

def generate_backtest_report(net_value_data, transaction_data, metrics, template_dir='template', template_name='nav_tradelog.html', output_dir='.'):
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
        "price": "价格"
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
    output_path = os.path.join(output_dir, f"backtest_report_{current_time}.html")

    html_content = template.render(
        net_value_data=net_value_data_json,
        transaction_data=transaction_data_json,
        metrics=metrics
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
    generate_backtest_report(net_value_data, transaction_data, metrics,output_dir="../html_report")