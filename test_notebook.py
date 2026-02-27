"""
Notebook 模块测试
测试内容：title, text, markdown, html, table, chart 及其嵌套
"""

import sys
sys.path.insert(0, 'd:/01-Doc/程序化/ft2')

import pandas as pd
import numpy as np
from notebook import Notebook


def test_basic_content():
    """测试基础内容：title, text, markdown, html"""
    print("\n[1] 基础内容测试...")
    
    nb = Notebook("基础内容测试")
    
    with nb.section("标题测试"):
        nb.title("一级标题", level=1)
        nb.title("二级标题", level=2)
        nb.title("三级标题", level=3)
    
    with nb.section("文本测试"):
        nb.text("普通文本内容")
        nb.text("标题样式文本", style="heading")
        nb.text("code style text", style="code")
    
    with nb.section("Markdown测试"):
        nb.markdown("""
**粗体文本** 和 *斜体文本*

- 列表项1
- 列表项2
- 列表项3

> 引用文本示例
        """)
    
    with nb.section("HTML测试"):
        nb.html("""
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; padding: 15px; border-radius: 8px;">
    <h4 style="margin: 0 0 8px 0;">自定义HTML块</h4>
    <p style="margin: 0; opacity: 0.9;">支持任意HTML内容</p>
</div>
        """)
    
    nb.export_html("d:/01-Doc/程序化/ft2/test_basic.html")
    print("输出: test_basic.html")


def test_table():
    """测试表格：data, df, 折叠, 嵌套"""
    print("\n[2] 表格测试...")
    
    nb = Notebook("表格测试")
    
    data = [
        {"股票代码": "600000", "股票名称": "浦发银行", "收盘价": 10.5, "涨跌幅": "+2.5%"},
        {"股票代码": "000001", "股票名称": "平安银行", "收盘价": 15.2, "涨跌幅": "-1.2%"},
        {"股票代码": "000002", "股票名称": "万科A", "收盘价": 8.3, "涨跌幅": "+0.8%"},
    ]
    
    with nb.section("列表数据表格"):
        nb.text("使用列表数据创建表格：")
        nb.table(data, title="股票行情")
    
    with nb.section("DataFrame表格"):
        nb.text("使用DataFrame创建表格：")
        df = pd.DataFrame({
            "代码": ["600000", "000001", "000002"],
            "名称": ["浦发银行", "平安银行", "万科A"],
            "价格": [10.5, 15.2, 8.3],
            "涨跌": ["+2.5%", "-1.2%", "+0.8%"]
        })
        nb.table(df, title="持仓明细")
    
    with nb.section("冻结列表格"):
        nb.text("左侧冻结2列，可左右滑动：")
        wide_data = []
        for i in range(20):
            wide_data.append({
                "股票代码": f"60{i:04d}",
                "股票名称": f"股票{i}名称",
                "收盘价": round(10 + i * 0.5, 2),
                "涨跌幅": f"{i-10}%",
                "成交量": 1000000 + i * 100000,
                "成交额": 10000000 + i * 1000000,
                "振幅": f"{i*0.5}%",
                "换手率": f"{i*0.3}%",
                "市盈率": round(20 + i * 0.5, 2),
                "市净率": round(2 + i * 0.1, 2),
                "总市值": 1000000000 + i * 10000000,
                "流通市值": 800000000 + i * 8000000,
            })
        nb.table(
            wide_data,
            columns=["股票代码", "股票名称", "收盘价", "涨跌幅", "成交量", "成交额", "振幅", "换手率", "市盈率", "市净率", "总市值", "流通市值"],
            title="股票行情（冻结左侧2列，共12列）",
            freeze={"left": 2, "right": 0}
        )
    
    with nb.section("折叠表格"):
        nb.text("点击展开查看详细数据：")
        nb.table(
            data * 3,
            columns=["股票代码", "股票名称", "收盘价", "涨跌幅"],
            title="历史交易记录（点击展开）",
            collapsed=True
        )
    
    with nb.section("表格与文本嵌套"):
        nb.text("表格前的说明文字")
        nb.table(data, title="数据表格")
        nb.text("表格后的补充说明")
        nb.markdown("**注意**: 数据仅供参考")
    
    nb.export_html("d:/01-Doc/程序化/ft2/test_table.html")
    print("输出: test_table.html")


def test_chart():
    """测试图表：不同类型，嵌套"""
    print("\n[3] 图表测试...")
    
    nb = Notebook("图表测试")
    
    dates = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]
    
    with nb.section("折线图"):
        nb.text("净值曲线展示：")
        nb.chart('line', {
            'dates': dates,
            'series': [
                {"name": "策略净值", "data": [1.0, 1.05, 1.12, 1.08, 1.15]},
                {"name": "基准净值", "data": [1.0, 1.02, 1.04, 1.06, 1.08]}
            ]
        }, title="净值曲线", height=300)
    
    with nb.section("柱状图"):
        nb.text("月度收益对比：")
        nb.chart('bar', {
            'categories': ["1月", "2月", "3月", "4月", "5月"],
            'series': [
                {"name": "策略收益%", "data": [5.2, -2.1, 8.5, 3.2, 6.1]},
                {"name": "基准收益%", "data": [2.0, 1.5, 2.2, 1.8, 2.5]}
            ]
        }, title="月度收益", height=300)
    
    with nb.section("面积图"):
        nb.text("回撤曲线展示：")
        nb.chart('area', {
            'dates': dates,
            'series': [{"name": "回撤%", "data": [0, -2, -5, -3, -1]}]
        }, title="回撤曲线", height=250)
    
    with nb.section("饼图"):
        nb.text("资产配置比例：")
        nb.chart('pie', [
            {"name": "股票", "value": 60},
            {"name": "债券", "value": 25},
            {"name": "现金", "value": 15}
        ], title="资产配置", height=300)
    
    with nb.section("热力图"):
        nb.text("月度收益热力图：")
        heatmap_data = {
            "2023": {"01": 0.02, "02": -0.01, "03": 0.03, "04": 0.01, "05": -0.02, "06": 0.04},
            "2024": {"01": 0.05, "02": -0.02, "03": 0.08, "04": 0.03, "05": 0.06, "06": -0.01}
        }
        nb.chart('heatmap', heatmap_data, title="月度收益热力图")
    
    with nb.section("图表与文本嵌套"):
        nb.markdown("### 综合分析")
        nb.text("以下是策略表现的综合展示：")
        
        nb.chart('line', {
            'dates': dates,
            'series': [{"name": "净值", "data": [1.0, 1.05, 1.12, 1.08, 1.15]}]
        }, title="净值走势")
        
        nb.text("从上图可以看出策略整体表现良好。")
        nb.chart('bar', {
            'categories': ["1月", "2月", "3月", "4月", "5月"],
            'series': [{"name": "收益%", "data": [5, -2, 8, 3, 6]}]
        }, title="月度收益")
        nb.markdown("**结论**: 策略收益稳定，回撤可控。")
    
    nb.export_html("d:/01-Doc/程序化/ft2/test_chart.html")
    print("输出: test_chart.html")


def test_nested_section():
    """测试嵌套Section"""
    print("\n[4] 嵌套Section测试...")
    
    nb = Notebook("嵌套Section测试")
    
    with nb.section("一级Section"):
        nb.text("一级Section内容")
        
        with nb.section("二级Section-A"):
            nb.text("二级Section-A内容")
            nb.table([
                {"指标": "收益率", "值": "25%"},
                {"指标": "夏普", "值": "1.5"}
            ], title="核心指标")
            
            with nb.section("三级Section"):
                nb.text("三级Section内容")
                nb.chart('line', {
                    'dates': ["1", "2", "3"],
                    'series': [{"name": "净值", "data": [1.0, 1.1, 1.2]}]
                }, title="净值曲线")
        
        with nb.section("二级Section-B"):
            nb.text("二级Section-B内容")
            nb.chart('bar', {
                'categories': ["A", "B", "C"],
                'series': [{"name": "收益", "data": [10, 20, 15]}]
            }, title="分类收益")
    
    nb.export_html("d:/01-Doc/程序化/ft2/test_nested.html")
    print("输出: test_nested.html")


def test_comprehensive():
    """综合测试：合并所有功能"""
    print("\n[综合测试]...")
    
    nb = Notebook("综合测试报告")
    
    # ==================== 报告概述 ====================
    with nb.section("报告概述"):
        nb.title("策略回测报告", level=1)
        nb.markdown("""
**策略类型**: 趋势跟踪 | **回测区间**: 2024-01 至 2024-05 | **初始资金**: 1,000,000
        """)
        nb.metrics([
            {"name": "总收益", "value": "45.6%", "desc": "累计收益"},
            {"name": "夏普", "value": "1.85", "desc": "风险调整"},
            {"name": "最大回撤", "value": "-12.3%", "desc": "2024-03"},
            {"name": "胜率", "value": "58%", "desc": "盈利占比"},
        ], title="核心指标")
    
    # ==================== 收益分析（图表） ====================
    dates = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]
    
    with nb.section("收益分析"):
        nb.text("净值曲线与基准对比：")
        nb.chart('line', {
            'dates': dates,
            'series': [
                {"name": "策略", "data": [1.0, 1.05, 1.12, 1.08, 1.15]},
                {"name": "基准", "data": [1.0, 1.02, 1.04, 1.06, 1.08]}
            ]
        }, title="净值曲线", height=300)
        
        with nb.section("月度分析"):
            nb.chart('bar', {
                'categories': ["1月", "2月", "3月", "4月", "5月"],
                'series': [{"name": "月收益%", "data": [5, -2, 8, 3, 6]}]
            }, title="月度收益")
            
            nb.chart('pie', [
                {"name": "股票", "value": 60},
                {"name": "债券", "value": 25},
                {"name": "现金", "value": 15}
            ], title="资产配置", height=250)
    
    # ==================== 风险分析 ====================
    with nb.section("风险分析"):
        nb.chart('area', {
            'dates': dates,
            'series': [{"name": "回撤%", "data": [0, -2, -5, -3, -1]}]
        }, title="回撤曲线", height=250)
        
        heatmap_data = {
            "2023": {"01": 0.02, "02": -0.01, "03": 0.03, "04": 0.01, "05": -0.02, "06": 0.04},
            "2024": {"01": 0.05, "02": -0.02, "03": 0.08, "04": 0.03, "05": 0.06, "06": -0.01}
        }
        nb.chart('heatmap', heatmap_data, title="月度收益热力图")
    
    # ==================== 持仓明细（表格） ====================
    with nb.section("持仓明细"):
        nb.text("当前持仓情况：")
        df = pd.DataFrame({
            "代码": ["600000", "000001", "000002"],
            "名称": ["浦发银行", "平安银行", "万科A"],
            "数量": [10000, 5000, 8000],
            "成本": [10.5, 15.2, 8.3],
            "现价": [11.2, 16.8, 7.5],
            "盈亏": ["+6.7%", "+10.5%", "-9.6%"]
        })
        nb.table(df, title="持仓列表")
    
    # ==================== 行情数据（冻结列表格） ====================
    with nb.section("股票行情"):
        nb.text("多列表格，冻结左侧2列：")
        wide_data = []
        for i in range(20):
            wide_data.append({
                "股票代码": f"60{i:04d}",
                "股票名称": f"股票{i}名称",
                "收盘价": round(10 + i * 0.5, 2),
                "涨跌幅": f"{i-10}%",
                "成交量": 1000000 + i * 100000,
                "成交额": 10000000 + i * 1000000,
                "振幅": f"{i*0.5}%",
                "换手率": f"{i*0.3}%",
                "市盈率": round(20 + i * 0.5, 2),
                "市净率": round(2 + i * 0.1, 2),
                "总市值": 1000000000 + i * 10000000,
                "流通市值": 800000000 + i * 8000000,
            })
        nb.table(
            wide_data,
            columns=["股票代码", "股票名称", "收盘价", "涨跌幅", "成交量", "成交额", "振幅", "换手率", "市盈率", "市净率", "总市值", "流通市值"],
            title="股票行情（冻结左侧2列，共12列）",
            freeze={"left": 2, "right": 0}
        )
    
    # ==================== 历史记录（折叠表格） ====================
    with nb.section("历史记录"):
        nb.table(
            [
                {"日期": "2024-01-05", "方向": "买入", "代码": "600000", "价格": 10.5, "数量": 1000},
                {"日期": "2024-02-10", "方向": "卖出", "代码": "600000", "价格": 11.2, "数量": 1000},
                {"日期": "2024-02-15", "方向": "买入", "代码": "000001", "价格": 15.0, "数量": 500},
                {"日期": "2024-03-20", "方向": "卖出", "代码": "000001", "价格": 16.8, "数量": 500},
            ],
            title="历史交易（点击展开）",
            collapsed=True
        )
    
    # ==================== 策略代码 ====================
    with nb.section("策略代码"):
        nb.code(
            code="""# 策略核心逻辑
def on_bar(bar):
    if bar.close > ma20:
        buy(symbol=bar.symbol, quantity=100)
    elif bar.close < ma20:
        sell(symbol=bar.symbol, quantity=100)
""",
            language="python",
            output="策略初始化完成\n回测结束"
        )
    
    # ==================== 风险提示（HTML） ====================
    with nb.section("风险提示"):
        nb.html("""
<div style="background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 6px;">
    <strong>⚠️ 风险提示</strong>
    <p style="margin: 8px 0 0 0; color: #856404;">
        本报告仅供参考，不构成投资建议。历史业绩不代表未来表现。
    </p>
</div>
        """)
    
    nb.export_html("d:/01-Doc/程序化/ft2/test_comprehensive.html")
    print("输出: test_comprehensive.html")


if __name__ == '__main__':
    print("=" * 60)
    print("Notebook 模块测试")
    print("=" * 60)
    
    test_basic_content()
    test_table()
    test_chart()
    test_nested_section()
    test_comprehensive()
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)
    print("\n输出文件:")
    print("  - test_basic.html      基础内容测试")
    print("  - test_table.html      表格测试")
    print("  - test_chart.html      图表测试")
    print("  - test_nested.html     嵌套Section测试")
    print("  - test_comprehensive.html  综合测试")
