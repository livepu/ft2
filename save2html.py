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
    # 使用 json.dumps 处理数据，设置 ensure_ascii=False 保证中文正常显示，indent=4 实现自动换行
    net_value_data_json = json.dumps(net_value_data, indent=4, ensure_ascii=False)
    transaction_data_json = json.dumps(transaction_data, indent=4, ensure_ascii=False)

    # 配置 Jinja2 环境
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)

    # 生成带时间的文件名
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"backtest_report_{current_time}.html")

    # 渲染模板
    html_content = template.render(
        net_value_data=net_value_data_json,
        transaction_data=transaction_data_json,
        metrics=metrics
    )

    # 保存为 HTML 文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML 报告已生成：{os.path.abspath(output_path)}")

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
generate_backtest_report(net_value_data, transaction_data, metrics)