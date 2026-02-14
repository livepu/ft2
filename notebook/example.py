"""
Notebook模块使用示例

演示如何使用Notebook类创建模块化HTML报告
"""
import sys
import os
ft2_parent_package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ft2_parent_package_dir)

from ft2.notebook import Notebook
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def example_basic():
    """基础示例：创建简单的报告"""
    nb = Notebook("策略回测报告")
    
    # 添加标题
    nb.add_title("回测结果概览", level=2)
    
    # 添加文本
    nb.add_text("本报告展示了策略的回测结果，包含关键绩效指标和权益曲线。")
    
    # 添加指标卡片
    metrics = [
        {'name': '累计收益率', 'value': '25.32%', 'desc': '回测期间总收益'},
        {'name': '年化收益率', 'value': '8.45%', 'desc': '年化收益'},
        {'name': '夏普比率', 'value': '1.23', 'desc': '风险调整收益'},
        {'name': '最大回撤', 'value': '-5.67%', 'desc': '最大亏损幅度'},
    ]
    nb.add_metrics(metrics, title="关键绩效指标")
    
    # 添加分隔线
    nb.add_divider()
    
    # 添加权益曲线
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    values = (1 + np.random.randn(100).cumsum() * 0.01).tolist()
    nb.add_equity_curve(dates.tolist(), values, title="权益曲线")
    
    # 导出HTML
    output_path = os.path.join(os.path.dirname(__file__), 'example_basic.html')
    nb.export_html(output_path)
    print(f"报告已生成: {output_path}")


def example_full():
    """完整示例：包含多种单元格类型"""
    nb = Notebook("完整策略分析报告")
    
    # ========== 标题和说明 ==========
    nb.add_title("沪深300指数策略回测", level=1)
    nb.add_text("回测区间：2020-01-01 至 2023-12-31", style='normal')
    nb.add_divider()
    
    # ========== 关键指标 ==========
    nb.add_title("一、关键绩效指标", level=2)
    
    metrics = [
        {'name': '累计收益率', 'value': '45.32%'},
        {'name': '年化收益率', 'value': '12.45%'},
        {'name': '夏普比率', 'value': '1.56'},
        {'name': '索提诺比率', 'value': '1.85'},
        {'name': '最大回撤', 'value': '-8.67%'},
        {'name': 'VaR(95%)', 'value': '2.35%'},
        {'name': 'CVaR(95%)', 'value': '3.12%'},
        {'name': '凯利仓位', 'value': '25.00%'},
    ]
    nb.add_metrics(metrics, title="绩效指标", columns=4)
    
    # ========== 权益曲线 ==========
    nb.add_title("二、权益曲线", level=2)
    
    dates = pd.date_range('2020-01-01', periods=500, freq='D')
    np.random.seed(42)
    returns = np.random.randn(500) * 0.01 + 0.0003
    values = (1000000 * (1 + returns).cumprod()).tolist()
    
    # 基准收益
    benchmark_values = (1000000 * (1 + np.random.randn(500) * 0.01).cumprod()).tolist()
    
    nb.add_equity_curve(dates.tolist(), values, title="策略净值曲线", benchmark_values=benchmark_values)
    
    # ========== 回撤曲线 ==========
    nb.add_title("三、回撤分析", level=2)
    
    # 计算回撤
    peak = np.maximum.accumulate(values)
    drawdowns = ((np.array(values) - peak) / peak * 100).tolist()
    
    nb.add_drawdown_chart(dates.tolist(), drawdowns, title="回撤曲线")
    
    # ========== 月度收益热力图 ==========
    nb.add_title("四、月度收益热力图", level=2)
    
    monthly_returns = {}
    for year in [2020, 2021, 2022, 2023]:
        monthly_returns[str(year)] = {}
        for month in range(1, 13):
            monthly_returns[str(year)][f'{month:02d}'] = np.random.randn() * 0.03
    
    nb.add_monthly_returns_heatmap(monthly_returns, title="月度收益率热力图")
    
    # ========== 交易记录 ==========
    nb.add_title("五、交易记录", level=2)
    
    trades = [
        {'时间': '2020-01-15', '标的': 'SHSE.000300', '方向': '买入', '数量': 1000, '价格': 3950.25, '手续费': 11.85},
        {'时间': '2020-02-20', '标的': 'SHSE.000300', '方向': '卖出', '数量': 1000, '价格': 4025.50, '手续费': 12.08},
        {'时间': '2020-03-10', '标的': 'SHSE.000300', '方向': '买入', '数量': 1200, '价格': 3880.00, '手续费': 13.97},
        {'时间': '2020-04-15', '标的': 'SHSE.000300', '方向': '卖出', '数量': 1200, '价格': 3920.75, '手续费': 14.11},
    ]
    
    nb.add_collapsible_table("交易记录详情", trades, collapsed=True)
    
    # ========== 分析结论 ==========
    nb.add_divider()
    nb.add_title("六、分析结论", level=2)
    nb.add_text("""
    策略在回测期间表现良好，年化收益率达到12.45%，夏普比率为1.56。
    最大回撤控制在8.67%以内，风险可控。
    建议：可以考虑将策略应用于实盘交易，但需注意市场环境变化。
    """)
    
    # 导出HTML
    output_path = os.path.join(os.path.dirname(__file__), 'example_full.html')
    nb.export_html(output_path)
    print(f"完整报告已生成: {output_path}")


def example_with_account_analyzer():
    """与AccountAnalyzer结合使用"""
    from ft2.notebook import Notebook
    # 假设已有account和analyzer
    # from ft2.analysis import AccountAnalyzer
    # analyzer = AccountAnalyzer(account)
    
    nb = Notebook("策略分析报告")
    
    # 添加标题
    nb.add_title("策略回测分析", level=1)
    
    # 添加指标（从analyzer获取）
    # metrics = analyzer.get_metrics()
    # nb.add_metrics(metrics, title="关键指标")
    
    # 添加权益曲线
    # dates = list(analyzer._daily_total_assets.keys())
    # values = list(analyzer._daily_total_assets.values())
    # nb.add_equity_curve(dates, values)
    
    # 导出
    # nb.export_html("report.html")
    
    print("此示例需要实际的account数据，请参考example_full()")


if __name__ == "__main__":
    print("=" * 50)
    print("Notebook模块使用示例")
    print("=" * 50)
    
    print("\n1. 基础示例...")
    example_basic()
    
    print("\n2. 完整示例...")
    example_full()
    
    print("\n示例完成！")
