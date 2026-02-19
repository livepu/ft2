"""
Notebook 内置输出模块综合测试
演示 Section 容器 + Cell 内嵌 title 的完整用法
"""

import sys
sys.path.insert(0, 'd:/01-Doc/程序化/ft2')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pyecharts import options as opts
from pyecharts.charts import Kline, Line, Bar, Pie, Grid

from notebook import Notebook


def generate_sample_data():
    """生成测试数据"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    
    close = 100 * np.cumprod(1 + np.random.normal(0.001, 0.02, 100))
    open_price = close * (1 + np.random.normal(0, 0.005, 100))
    high = np.maximum(close, open_price) * (1 + np.abs(np.random.normal(0, 0.01, 100)))
    low = np.minimum(close, open_price) * (1 - np.abs(np.random.normal(0, 0.01, 100)))
    volume = np.random.randint(1000000, 5000000, 100)
    
    df = pd.DataFrame({
        'date': dates,
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })
    
    returns = df['close'].pct_change().dropna()
    cum_returns = (1 + returns).cumprod()
    drawdown = (cum_returns - cum_returns.cummax()) / cum_returns
    
    monthly_returns = {}
    for year in ['2024']:
        monthly_returns[year] = {}
        for month in range(1, 13):
            monthly_returns[year][f'{month:02d}'] = np.random.uniform(-0.05, 0.08)
    
    return df, dates, close, volume, returns, cum_returns, drawdown, monthly_returns


def create_pyecharts_kline(df):
    """创建 pyecharts K线图"""
    dates = df['date'].astype(str).tolist()
    kline_data = df[['open', 'close', 'low', 'high']].values.tolist()
    
    ma5 = df['close'].rolling(5).mean().tolist()
    ma10 = df['close'].rolling(10).mean().tolist()
    ma20 = df['close'].rolling(20).mean().tolist()
    
    kline = (
        Kline()
        .add_xaxis(dates)
        .add_yaxis(
            "K线",
            kline_data,
            itemstyle_opts=opts.ItemStyleOpts(
                color="#ef232a",
                color0="#14b143",
                border_color="#ef232a",
                border_color0="#14b143"
            )
        )
        .set_global_opts(
            yaxis_opts=opts.AxisOpts(is_scale=True),
            xaxis_opts=opts.AxisOpts(is_scale=True),
            datazoom_opts=[
                opts.DataZoomOpts(type_="inside"),
                opts.DataZoomOpts(type_="slider")
            ],
            tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
            legend_opts=opts.LegendOpts(pos_top="3%"),
        )
    )
    
    line_ma5 = Line().add_xaxis(dates).add_yaxis(
        "MA5", ma5, symbol="none", 
        linestyle_opts=opts.LineStyleOpts(width=1, color="#f5a623")
    )
    line_ma10 = Line().add_xaxis(dates).add_yaxis(
        "MA10", ma10, symbol="none",
        linestyle_opts=opts.LineStyleOpts(width=1, color="#4a90d9")
    )
    line_ma20 = Line().add_xaxis(dates).add_yaxis(
        "MA20", ma20, symbol="none",
        linestyle_opts=opts.LineStyleOpts(width=1, color="#9013fe")
    )
    
    kline.overlap(line_ma5).overlap(line_ma10).overlap(line_ma20)
    return kline


def main():
    print("=" * 60)
    print("Notebook 综合测试：Section + 基础输出模块")
    print("=" * 60)
    
    df, dates, close, volume, returns, cum_returns, drawdown, monthly_returns = generate_sample_data()
    date_list = dates.strftime('%Y-%m-%d').tolist()[:50]
    
    nb = Notebook("策略回测分析报告")
    
    # ==================== 报告头部 ====================
    print("\n[1] 报告头部...")
    nb.add_title("策略回测分析报告", level=1)
    nb.add_text("本报告展示了策略的回测结果，包括收益分析、风险指标等内容。")
    nb.add_markdown("""
**策略类型**: 趋势跟踪策略 | **回测区间**: 2024-01-01 至 2024-04-10 | **初始资金**: 1,000,000 元
    """)
    
    # ==================== Section 1: 核心指标概览 ====================
    print("[2] 核心指标概览...")
    with nb.section("核心指标概览"):
        nb.add_metrics([
            {"name": "总收益率", "value": "45.6%", "desc": "策略期间累计"},
            {"name": "年化收益", "value": "18.2%", "desc": "复利计算"},
            {"name": "最大回撤", "value": "-12.3%", "desc": "2024-03-15"},
            {"name": "夏普比率", "value": "1.85", "desc": "风险调整后收益"},
        ], title="收益指标")
        
        nb.add_metrics([
            {"name": "胜率", "value": "58.3%", "desc": "盈利交易占比"},
            {"name": "盈亏比", "value": "1.82", "desc": "平均盈利/平均亏损"},
            {"name": "交易次数", "value": "156", "desc": "总交易次数"},
            {"name": "持仓天数", "value": "45", "desc": "平均持仓天数"},
        ], title="交易指标")
    
    # ==================== Section 2: 收益分析（嵌套） ====================
    print("[3] 收益分析...")
    with nb.section("收益分析"):
        nb.add_line_chart(
            dates=date_list,
            series=[
                {"name": "策略净值", "data": cum_returns.iloc[:50].tolist()},
                {"name": "基准净值", "data": [1 + i*0.002 for i in range(50)]}
            ],
            title="净值曲线对比",
            height=350
        )
        
        # 嵌套 Section
        with nb.section("收益统计"):
            nb.add_bar_chart(
                categories=["1月", "2月", "3月", "4月"],
                series=[{"name": "月收益%", "data": [5.2, -2.1, 8.5, 3.2]}],
                title="月度收益"
            )
            
            nb.add_pie_chart(
                data=[
                    {"name": "股票", "value": 60},
                    {"name": "债券", "value": 20},
                    {"name": "现金", "value": 10},
                    {"name": "商品", "value": 5},
                    {"name": "其他", "value": 5}
                ],
                title="资产配置"
            )
    
    # ==================== Section 3: 风险分析 ====================
    print("[4] 风险分析...")
    with nb.section("风险分析"):
        nb.add_area_chart(
            dates=date_list,
            series=[{"name": "回撤%", "data": [d * 100 for d in drawdown.iloc[:50].tolist()]}],
            title="回撤曲线",
            height=300
        )
        
        nb.add_heatmap(monthly_returns, title="月度收益热力图")
    
    # ==================== Section 4: K线分析（pyecharts） ====================
    print("[5] K线分析...")
    with nb.section("K线分析"):
        kline_chart = create_pyecharts_kline(df)
        nb.add_pyecharts(kline_chart, title="K线图 + 均线", height=500)
    
    # ==================== Section 5: 交易记录 ====================
    print("[6] 交易记录...")
    with nb.section("交易记录"):
        trades = [
            {"日期": "2024-01-05", "方向": "买入", "价格": 102.5, "数量": 1000, "金额": 102500},
            {"日期": "2024-01-12", "方向": "卖出", "价格": 108.3, "数量": 1000, "金额": 108300},
            {"日期": "2024-01-20", "方向": "买入", "价格": 105.2, "数量": 1500, "金额": 157800},
            {"日期": "2024-02-01", "方向": "卖出", "价格": 112.8, "数量": 1500, "金额": 169200},
            {"日期": "2024-02-15", "方向": "买入", "价格": 109.5, "数量": 2000, "金额": 219000},
        ]
        nb.add_table(trades, title="近期交易记录")
        
        position_df = pd.DataFrame({
            "股票代码": ["600000", "000001", "000002"],
            "股票名称": ["浦发银行", "平安银行", "万科A"],
            "持仓数量": [10000, 5000, 8000],
            "成本价": [10.5, 15.2, 8.3],
            "现价": [11.2, 16.8, 7.5],
            "盈亏": [7000, 8000, -6400],
        })
        nb.add_dataframe(position_df, title="当前持仓")
    
    # ==================== Section 6: 策略详情（三层嵌套） ====================
    print("[7] 策略详情...")
    with nb.section("策略详情"):
        nb.add_code(
            code="""# 策略核心逻辑
def on_bar(bar):
    if bar.close > ma20:
        buy(symbol=bar.symbol, quantity=100)
    elif bar.close < ma20:
        sell(symbol=bar.symbol, quantity=100)
""",
            language="python",
            output="策略初始化完成\n开始回测...\n回测结束"
        )
        
        # 二级嵌套
        with nb.section("参数配置"):
            nb.add_table([
                {"参数": "MA周期", "值": "20", "说明": "均线周期"},
                {"参数": "止损比例", "值": "5%", "说明": "单笔止损"},
                {"参数": "止盈比例", "值": "10%", "说明": "单笔止盈"},
            ], title="策略参数")
            
            # 三级嵌套
            with nb.section("优化记录"):
                nb.add_table([
                    {"版本": "v1.0", "收益": "32%", "夏普": "1.2"},
                    {"版本": "v1.1", "收益": "38%", "夏普": "1.5"},
                    {"版本": "v2.0", "收益": "45%", "夏普": "1.85"},
                ], title="版本迭代")
    
    # ==================== 独立内容（不使用 Section） ====================
    print("[8] 独立内容...")
    nb.add_divider()
    nb.add_title("附录", level=2)
    
    # 可折叠区域
    nb.add_collapsible_table(
        title="历史交易明细（点击展开）",
        data=trades * 3,
        columns=["日期", "方向", "价格", "数量", "金额"],
        collapsed=True
    )
    
    # HTML 内容
    nb.add_html("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; padding: 20px; border-radius: 8px; margin: 10px 0;">
        <h3 style="margin: 0 0 10px 0;">风险提示</h3>
        <p style="margin: 0; opacity: 0.9;">
            本报告仅供参考，不构成投资建议。历史业绩不代表未来表现。
        </p>
    </div>
    """)
    
    # ==================== 导出 ====================
    print("[9] 导出 HTML...")
    output_path = nb.export_html("d:/01-Doc/程序化/ft2/test_notebook.html")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print(f"\n输出文件: {output_path}")
    print(f"单元格数量: {len(nb)}")
    print("\n直接双击 HTML 文件查看完整效果")
    print("\n结构说明:")
    print("  - Section 1: 核心指标概览")
    print("  - Section 2: 收益分析（含嵌套）")
    print("  - Section 3: 风险分析")
    print("  - Section 4: K线分析（pyecharts）")
    print("  - Section 5: 交易记录")
    print("  - Section 6: 策略详情（三层嵌套）")
    print("  - 附录: 独立内容")


if __name__ == '__main__':
    main()
