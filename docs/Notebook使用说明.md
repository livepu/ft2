# Notebook 使用说明

> 快速构建专业数据分析报告的 Python 工具\
> 支持表格、图表、指标卡片、章节组织等多种组件

***

## 目录

1. [快速开始](#一快速开始)
2. [核心概念](#二核心概念)
3. [基础组件](#三基础组件)
4. [图表组件](#四图表组件)
5. [章节与布局](#五章节与布局)
6. [高级功能](#六高级功能)
7. [完整示例](#七完整示例)
8. [最佳实践](#八最佳实践)

***

## 一、快速开始

### 1.1 安装与导入

```python
from notebook import Notebook

# 创建 Notebook 实例
nb = Notebook("策略分析报告")
```

### 1.2 第一个报告

```python
from notebook import Notebook

# 创建报告
nb = Notebook("我的第一个报告")

# 添加标题
nb.title("数据分析结果", level=1)

# 添加文本
nb.text("这是报告的正文内容，支持普通、强调、警告等多种样式。")

# 添加指标卡片
nb.metrics([
    {"name": "总收益", "value": "15.3%", "desc": "今年以来"},
    {"name": "最大回撤", "value": "-5.2%", "desc": "风险控制良好"},
    {"name": "夏普比率", "value": "1.85", "desc": "风险调整后收益"},
])

# 导出 HTML
output = nb.export_html("my_first_report")
print(f"报告已生成: {output}")
```

**输出效果**：

- 一个包含标题、文本、三个指标卡片的 HTML 报告
- 自动应用配色方案和响应式布局
- 支持截图和目录导航

***

## 二、核心概念

### 2.1 Notebook 工作流程

```
创建 Notebook → 添加组件 → 组织章节 → 导出 HTML
     ↑              ↑           ↑            ↓
   设置标题      表格/图表    层级结构    可视化报告
   配置选项      指标/文本    折叠展开    交互式分析
```

### 2.2 组件类型概览

| 组件           | 方法           | 用途                                           |
| ------------ | ------------ | -------------------------------------------- |
| ⭐ **章节**       | `section()`  | 内容分组，支持折叠                                    |
| ⭐ **标题**       | `title()`    | 章节标题，支持层级                                    |
| ⭐ **Markdown** | `markdown()` | Markdown 格式文本（推荐）                          |
| **文本**       | `text()`     | 说明文字，支持颜色设置                                |
| **代码**       | `code()`     | 代码块                                          |
| **HTML**     | `html()`     | 原始 HTML                                      |
| **分隔线**      | `divider()`  | 视觉分隔                                         |
| ⭐ **指标**       | `metrics()`  | 关键指标卡片                                       |
| ⭐ **表格**       | `table()`    | 数据表格，支持冻结列                                   |
| ⭐ **图表**       | `chart()`    | 单图表（line/bar/area/pie/heatmap/kline/scatter） |
| **网格图**      | `chartg()`   | 多图表垂直组合                                      |

### 2.3 链式调用

所有添加方法都支持链式调用：

```python
nb = Notebook("链式调用示例")
nb.title("报告标题").text("说明文字").metrics([...]).export_html("output")
```

***

## 三、基础组件

### 3.1 标题（Title）

```python
# 一级标题（最大）
nb.title("策略分析报告", level=1)

# 二级标题
nb.title("收益分析", level=2)

# 三级标题（最小）
nb.title("月度详情", level=3)
```

### 3.2 Markdown 文本（推荐）

```python
# 基础 Markdown
nb.markdown("""
**加粗文本** 和 *斜体文本*

- 列表项1
- 列表项2
- 列表项3

`行内代码` 和代码块：
```python
print("Hello World")
```
""")

# 带标题的 Markdown
nb.markdown("""
### 分析结论

1. **收益表现**：策略年化收益 **15.3%**，跑赢基准
2. **风险控制**：最大回撤控制在 **-5.2%** 以内
3. **夏普比率**：达到 **1.85**，风险调整后收益优秀

> 注：以上数据基于2020-2024年回测结果
""")
```

### 3.3 普通文本（Text）

```python
# 简单文本（默认颜色）
nb.text("这是普通文本内容")

# 带颜色的文本
nb.text("错误信息", color="red")
nb.text("操作成功", color="green")
nb.text("提示信息", color="blue")
```

### 3.4 表格（Table）

```python
import pandas as pd

# 准备数据
data = pd.DataFrame({
    "股票代码": ["000001.SZ", "000002.SZ", "000858.SZ"],
    "股票名称": ["平安银行", "万科A", "五粮液"],
    "收益率": ["15.3%", "-5.2%", "28.7%"],
    "持仓权重": ["30%", "25%", "45%"],
})

# 基础表格
nb.table(data, title="持仓明细")

# 冻结列（前2列固定）
nb.table(data, title="持仓明细（冻结列）", freeze={"left": 2})

# 指定列配置
columns = [
    {"field": "股票代码", "title": "代码", "width": 120},
    {"field": "股票名称", "title": "名称", "width": 100},
    {"field": "收益率", "title": "收益", "width": 80},
    {"field": "持仓权重", "title": "权重", "width": 80},
]
nb.table(data, title="自定义列", columns=columns)
```

### 3.5 指标卡片（Metrics）

```python
# 基础指标
nb.metrics([
    {"name": "总收益", "value": "15.3%"},
    {"name": "年化收益", "value": "18.2%"},
    {"name": "最大回撤", "value": "-5.2%"},
])

# 带描述的指标
nb.metrics([
    {"name": "总收益", "value": "15.3%", "desc": "今年以来"},
    {"name": "最大回撤", "value": "-5.2%", "desc": "风险控制良好"},
    {"name": "夏普比率", "value": "1.85", "desc": "风险调整后收益"},
], title="核心指标", columns=3)

# 自动着色（正值绿色，负值红色）
nb.metrics([
    {"name": "今日收益", "value": "+2.5%"},   # 自动绿色
    {"name": "昨日收益", "value": "-1.2%"},   # 自动红色
])
```

### 3.6 分隔线（Divider）

```python
nb.text("第一部分内容").divider().text("第二部分内容")
```

***

## 四、图表组件

### chart() 方法参数规范

```python
nb.chart(chart_type, data, title=None, height='400px', **kwargs)
```

**参数说明：**

| 参数           | 类型             | 必填 | 说明                                                               |
| ------------ | -------------- | -- | ---------------------------------------------------------------- |
| `chart_type` | str            | 是  | 图表类型：`line`, `bar`, `area`, `pie`, `heatmap`, `kline`, `scatter` |
| `data`       | dict/DataFrame | 是  | 图表数据，格式因类型而异                                                     |
| `title`      | str            | 否  | 图表标题                                                             |
| `height`     | str            | 否  | 容器高度，默认 `'400px'`                                                |
| `width`      | str            | 否  | 容器宽度，默认 `'100%'`（通过 kwargs 传入）                                   |

**kwargs 可选参数：**

| 参数               | 说明                   |
| ---------------- | -------------------- |
| `series_opts`    | 系列配置，统一应用到所有系列       |
| `title_opts`     | 标题配置（pyecharts 规范）   |
| `legend_opts`    | 图例配置（pyecharts 规范）   |
| `tooltip_opts`   | 提示框配置（pyecharts 规范）  |
| `xaxis_opts`     | X轴配置（pyecharts 规范）   |
| `yaxis_opts`     | Y轴配置（pyecharts 规范）   |
| `datazoom_opts`  | 数据缩放配置（pyecharts 规范） |
| `visualmap_opts` | 视觉映射配置（pyecharts 规范） |
| `grid_opts`      | 网格配置（pyecharts 规范）   |

**数据格式规范：**

| 图表类型 | 标准格式 | DataFrame 格式 | 转换规则 |
| ------------ | ---------------------------------------------------------------- | ------------------- | ------------------------------------------------------------ |
| `line/bar/area` | `{'xAxis': [...], 'series': [...]}` | ✅ 支持 | **第一列→X轴，其余列→series** |
| `scatter` | `{'xAxis': [...], 'series': [...]}` | ❌ **不支持** | - |
| `kline` | `{'xAxis': [...], 'series': [...]}` | ✅ 支持 | 第一列→X轴（日期），open/close/low/high 字段 → K线 |
| `pie` | `[{'name': '', 'value': 0}, ...]` | ✅ 支持 | 第一列→name，第二列→value |
| `heatmap` | 嵌套字典 `{y: {x: value}}` | ✅ 支持 | **第一列→X轴，其余列→Y轴** |

**核心设计理念**：DataFrame 格式与 `print(df)` / `nb.table()` 保持一致性。第一列在表格中是可见的第一列，在图表中是 X 轴，自然对应。

### 4.1 折线图（Line）

```python
# 数据定义
x_data = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]
strategy_data = [1.0, 1.05, 1.12, 1.08, 1.15]
benchmark_data = [1.0, 1.02, 1.04, 1.06, 1.08]

# 字典格式
nb.chart('line', {
    'xAxis': x_data,
    'series': [
        {"name": "策略", "data": strategy_data},
        {"name": "基准", "data": benchmark_data}
    ]
}, title="净值曲线（字典格式）")

# DataFrame 格式（与字典完全对应）
df = pd.DataFrame({
    "月份": x_data,              # = xAxis
    "策略": strategy_data,        # = series[0]["data"]
    "基准": benchmark_data        # = series[1]["data"]
})
nb.chart("line", df, title="净值曲线（DataFrame格式）")
# DataFrame 转换规则：第一列（月份）→ xAxis，其余列 → series
```

**前端交互**：

- 悬停显示 tooltip
- 点击 legend 切换显示/隐藏
- 支持配色方案切换

### 4.2 柱状图（Bar）

```python
# 普通柱状图
data = {
    "xAxis": ["1月", "2月", "3月", "4月", "5月"],
    "series": [{"name": "收益", "data": [5, 3, 8, 6, 9]}]
}

nb.chart("bar", data, title="月度收益", height="350px")

# 堆叠柱状图（通过 series_opts 设置）
data_stack = {
    "xAxis": ["Q1", "Q2", "Q3", "Q4"],
    "series": [
        {"name": "股票", "data": [30, 45, 35, 50]},
        {"name": "债券", "data": [70, 55, 65, 50]},
    ]
}

nb.chart("bar", data_stack, title="资产配置", height="350px",
         series_opts={"stack": "total"})
```

**前端交互**：

- 支持显示数值标签
- 支持百分比/原始数据切换

### 4.3 面积图（Area）

```python
data = {
    "xAxis": dates,
    "series": [
        {"name": "累计收益", "data": [0, 5, 8, 12, 15]},
    ]
}

nb.chart("area", data, title="累计收益走势", height="400px")
```

### 4.4 饼图（Pie）

```python
import pandas as pd
df = pd.DataFrame({
    "资产类型": ["股票", "债券", "现金", "其他"],
    "占比": [45, 30, 15, 10],
})
print(df)
#   资产类型  占比
# 0   股票  45
# 1   债券  30
# 2   现金  15
# 3   其他  10

nb.chart("pie", df, title="资产配置", height="400px")
# DataFrame 转换规则：第1列（资产类型）→ name，第2列（占比）→ value
```

**前端交互**：

- 显示选项：原始数据 / 百分比 / 同时显示
- 悬停高亮
- 点击图例切换

### 4.5 热力图（Heatmap）

```python
import numpy as np
import pandas as pd

# 方式1：使用字典（直接格式）
data_dict = {
    "2023": {"01": 0.02, "02": -0.01, "03": 0.03, "04": 0.01, "05": -0.02, "06": 0.04},
    "2024": {"01": 0.05, "02": -0.02, "03": 0.08, "04": 0.03, "05": 0.06, "06": -0.01}
}
# Y轴=年份，X轴=月份
nb.chart("heatmap", data_dict, title="月度收益热力图（字典格式）")

# 方式2：使用 DataFrame（推荐，与 table 一致）
month_labels = ["01", "02", "03", "04", "05", "06"]
y2023 = [0.02, -0.01, 0.03, 0.01, -0.02, 0.04]
y2024 = [0.05, -0.02, 0.08, 0.03, 0.06, -0.01]

df_heatmap = pd.DataFrame({
    "月份": month_labels,   # ← 第一列 = X 轴
    "2023": y2023,           # ← 其余列 = Y 轴
    "2024": y2024
})
nb.chart("heatmap", df_heatmap, title="月度收益热力图（DataFrame格式）")
# DataFrame 转换规则：第一列（月份）→ X轴，其余列名（2023/2024）→ Y轴
```

**前端交互**：

- visualMap 显示数值范围
- 悬停显示具体数值
- 数据缩放控件（×1/×10/×100）

### 4.6 网格图（Grid Chart）

用于将多个图表垂直排列，共享 x 轴：

```python
# 准备数据
dates = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]

# 净值数据
nav_data = {
    "xAxis": dates,
    "series": [{"name": "净值", "data": [1.0, 1.05, 1.08, 1.12, 1.15]}]
}

# 收益数据
return_data = {
    "xAxis": dates,
    "series": [{"name": "月收益", "data": [5, 3, 4, 3, 3]}]
}

# 回撤数据
drawdown_data = {
    "xAxis": dates,
    "series": [{"name": "回撤", "data": [0, -2, -1, -3, -2]}]
}

# 使用 chartg 添加网格图（height 为数值，单位 px）
nb.chartg("line", nav_data, height=300)
nb.chartg("bar", return_data, height=200)
nb.chartg("line", drawdown_data, height=150)

# 注意：chartg 会自动组合，不需要显式结束
```

**特点**：

- 多个图表垂直排列
- 适合 K线+成交量+指标 的组合
- 简化处理，不支持复杂交互

### 4.7 K线图（Kline）

```python
# 方式1：标准格式
# K线数据格式: [开盘, 收盘, 最低, 最高]
kline_data = [
    [2320.26, 2302.6, 2287.3, 2362.94],
    [2300, 2291.3, 2288.26, 2308.38],
    [2295.35, 2346.5, 2295.35, 2346.92],
    [2347.22, 2358.98, 2337.35, 2363.8],
    [2360.75, 2382.48, 2347.89, 2383.76],
]

dates = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]

data = {
    "xAxis": dates,
    "series": [{"name": "日K", "data": kline_data}]
}

nb.chart("kline", data, title="K线图", height="400px")

# 方式2：DataFrame（自动识别字段）
import pandas as pd

df = pd.DataFrame({
    "date": pd.date_range("2024-01-01", periods=5),
    "open": [2320.26, 2300, 2295.35, 2347.22, 2360.75],
    "close": [2302.6, 2291.3, 2346.5, 2358.98, 2382.48],
    "low": [2287.3, 2288.26, 2295.35, 2337.35, 2347.89],
    "high": [2362.94, 2308.38, 2346.92, 2363.8, 2383.76],
})
print(df)
#         date    open   close     low    high
# 0 2024-01-01 2320.26 2302.60 2287.30 2362.94
# 1 2024-01-02 2300.00 2291.30 2288.26 2308.38
# ...

nb.chart("kline", df, title="K线图", height="400px")
# DataFrame 转换规则：第1列 → xAxis，open/close/low/high 字段 → K线数据
```

**支持的字段名：**

- 开盘：`open`, `开盘`, `Open`, `OPEN`, `o`, `O`
- 收盘：`close`, `收盘`, `Close`, `CLOSE`, `c`, `C`
- 最低：`low`, `最低`, `Low`, `LOW`, `l`, `L`
- 最高：`high`, `最高`, `High`, `HIGH`, `h`, `H`

### 4.8 散点图（Scatter）

**注意：散点图不支持 DataFrame 自动转换，请使用标准格式**

```python
# 类目散点图（X轴为类目）
data = {
    "xAxis": ["1月", "2月", "3月", "4月", "5月"],
    "series": [
        {"name": "策略A", "data": [10, 15, 8, 20, 12]},
        {"name": "策略B", "data": [8, 12, 15, 10, 18]},
    ]
}

nb.chart("scatter", data, title="类目散点图", height="400px")

# 数值散点图（XY坐标对）
data = {
    "xAxis": [],  # 数值轴不需要类目
    "series": [{
        "name": "散点",
        "data": [[1, 10], [2, 20], [3, 30], [4, 40]]  # [x, y] 坐标对
    }]
}

nb.chart("scatter", data, title="数值散点图", height="400px")
```

**数据格式说明：**

- 类目散点图：`data` 为数值数组，X轴使用 `xAxis` 类目
- 数值散点图：`data` 为 `[[x, y], ...]` 坐标对数组，`xAxis` 为空列表

***

## 五、章节与布局

### 5.1 基础章节

```python
# 创建章节
with nb.section("收益分析"):
    nb.text("本章节分析策略的收益表现")
    nb.chart("line", data, title="净值曲线")
    nb.metrics([...])
```

### 5.2 可折叠章节

```python
# 默认可折叠（收起状态）
with nb.section("详细数据", collapsed=True):
    nb.table(data, title="完整数据")
    nb.text("更多详细信息...")

# 默认展开
with nb.section("核心指标", collapsed=False):
    nb.metrics([...])
```

### 5.3 章节层级

章节层级根据嵌套深度自动计算，无需手动指定：

```python
# 一级章节（最外层）
with nb.section("第一部分：策略概述"):
    nb.text("策略基本信息...")
    
    # 二级章节（嵌套在一级章节内）
    with nb.section("1.1 策略逻辑"):
        nb.text("策略的核心逻辑...")
        
    with nb.section("1.2 参数设置"):
        nb.text("策略参数说明...")

# 另一个一级章节
with nb.section("第二部分：回测结果"):
    nb.chart("line", data, title="净值曲线")
```

### 5.4 章节嵌套

```python
with nb.section("策略分析"):
    nb.text("整体分析...")
    
    with nb.section("收益分析"):
        nb.chart("line", nav_data)
        
        with nb.section("月度收益"):
            nb.chart("bar", monthly_data)
    
    with nb.section("风险分析"):
        nb.metrics([...])
```

***

## 六、高级功能

### 6.1 配色方案切换

前端支持动态切换配色方案：

```python
# 导出后，在浏览器中点击右下角 🎨 按钮
# 支持：暖冷渐变系、高对比度系、大红大紫系、ECharts默认
```

### 6.2 选择性截图

```python
# 导出后，在浏览器中：
# 1. 点击目录中的复选框选择要截图的部分
# 2. 点击"截图选中"按钮
# 3. 自动复制到剪贴板
```

### 6.3 响应式布局

- 桌面端：显示目录面板
- 平板/手机：目录自动收起为图标
- 所有图表自动适应容器大小

### 6.4 自定义 HTML

```python
# 插入自定义 HTML
nb.html("<div style='color: red;'>自定义内容</div>")
```

### 6.5 Markdown 文本

```python
# 支持 Markdown 格式
nb.markdown("""
**加粗文本**
*斜体文本*
`代码片段`

多行文本支持
""")
```

***

## 七、完整示例

### 7.1 策略分析报告

```python
from notebook import Notebook
import pandas as pd
import numpy as np

# 创建报告
nb = Notebook("量化策略分析报告")

# ========== 报告标题 ==========
nb.title("双均线策略分析报告", level=1)
nb.text("报告生成时间：2024年6月", color="blue")
nb.divider()

# ========== 策略概述 ==========
with nb.section("一、策略概述"):
    nb.text("""
    本策略采用双均线交叉作为交易信号：
    - 短期均线（5日）上穿长期均线（20日）时买入
    - 短期均线下穿长期均线时卖出
    """)
    
    nb.metrics([
        {"name": "策略名称", "value": "双均线策略"},
        {"name": "回测区间", "value": "2020-2024"},
        {"name": "交易标的", "value": "沪深300"},
    ], columns=3)

# ========== 收益分析 ==========
with nb.section("二、收益分析"):
    
    # 生成模拟数据
    dates = pd.date_range("2020-01-01", "2024-05-31", freq="M").strftime("%Y-%m").tolist()
    nav = np.cumsum(np.random.normal(0.01, 0.05, len(dates))) + 1
    
    nav_data = {
        "xAxis": dates,
        "series": [
            {"name": "策略净值", "data": nav.tolist()},
            {"name": "基准净值", "data": [1 + i*0.005 for i in range(len(dates))]},
        ]
    }
    
    nb.chart("line", nav_data, title="策略 vs 基准", height="450px")
    
    # 核心指标
    nb.metrics([
        {"name": "总收益", "value": "+85.3%", "desc": "4年累计"},
        {"name": "年化收益", "value": "+16.8%", "desc": "复利计算"},
        {"name": "最大回撤", "value": "-12.5%", "desc": "2022年3月"},
        {"name": "夏普比率", "value": "1.35", "desc": "风险调整后收益"},
        {"name": "胜率", "value": "58.3%", "desc": "交易胜率"},
        {"name": "盈亏比", "value": "1.8", "desc": "平均盈利/亏损"},
    ], title="核心绩效指标", columns=3)

# ========== 月度收益 ==========
with nb.section("三、月度收益分析"):
    
    months = ["1月", "2月", "3月", "4月", "5月", "6月", 
              "7月", "8月", "9月", "10月", "11月", "12月"]
    monthly_returns = [3.2, -1.5, 5.8, 2.1, -0.5, 4.3, 
                       1.8, -2.2, 3.5, 0.8, 2.9, 1.5]
    
    bar_data = {
        "xAxis": months,
        "series": [{"name": "月收益", "data": monthly_returns}]
    }
    
    nb.chart("bar", bar_data, title="2024年月度收益", height="350px")

# ========== 资产配置 ==========
with nb.section("四、资产配置"):
    
    pie_data = [
        {"name": "股票", "value": 60},
        {"name": "债券", "value": 25},
        {"name": "现金", "value": 10},
        {"name": "商品", "value": 5},
    ]
    
    nb.chart("pie", pie_data, title="当前资产配置", height="400px")

# ========== 详细数据（可折叠） ==========
with nb.section("五、详细交易记录", collapsed=True):
    
    trades = pd.DataFrame({
        "日期": ["2024-01-15", "2024-02-20", "2024-03-10", "2024-04-05"],
        "操作": ["买入", "卖出", "买入", "卖出"],
        "价格": [12.5, 13.8, 13.2, 14.5],
        "数量": [1000, 1000, 1000, 1000],
        "盈亏": ["-", "+1300", "-", "+1300"],
    })
    
    nb.table(trades, title="交易明细", freeze={"left": 1})

# 导出报告
output = nb.export_html("strategy_report")
print(f"报告已生成: {output}")
```

### 7.2 数据监控看板

```python
from notebook import Notebook

nb = Notebook("实时数据监控")

# 关键指标
nb.metrics([
    {"name": "当前净值", "value": "1.1523", "desc": "实时"},
    {"name": "今日收益", "value": "+1.25%", "desc": "日内"},
    {"name": "持仓数量", "value": "15", "desc": "只股票"},
    {"name": "可用资金", "value": "￥125,000", "desc": "现金"},
], title="实时监控", columns=4)

# 使用 grid 展示多个图表
nb.chartg("line", nav_data, height=250)
nb.chartg("bar", volume_data, height=150)
nb.chartg("line", drawdown_data, height=150)

output = nb.export_html("dashboard")
```

***

## 八、最佳实践

### 8.1 报告结构建议

```
报告标题
├── 执行摘要（关键指标）
├── 详细分析
│   ├── 收益分析
│   ├── 风险分析
│   └── 归因分析
├── 数据详情（可折叠）
└── 结论与建议
```

### 8.2 性能优化

- **大数据表格**：使用分页或虚拟滚动
- **大量图表**：考虑使用 `chartg` 组合，减少 DOM 节点
- **截图功能**：选中区域不宜过多（建议不超过 5 个）

### 8.3 配色建议

| 场景   | 推荐配色      |
| ---- | --------- |
| 正式报告 | 暖冷渐变系     |
| 数据对比 | 高对比度系     |
| 演示展示 | 大红大紫系     |
| 默认兼容 | ECharts默认 |

### 8.4 常见问题

**Q: 表格列宽如何调整？**

```python
columns = [
    {"field": "name", "title": "名称", "width": 150},
    # ...
]
nb.table(data, columns=columns)
```

**Q: 图表高度如何设置？**

```python
nb.chart("line", data, height="500px")  # 默认 "400px"
```

**Q: 如何添加多个表格？**

```python
with nb.section("表格对比"):
    nb.table(data1, title="表1")
    nb.table(data2, title="表2")
```

**Q: 导出后如何查看？**

```python
output = nb.export_html("report")
# 使用浏览器打开 output 文件
```

***

## 附录

### A. 版本记录

| 版本   | 日期         | 变更               |
| ---- | ---------- | ---------------- |
| V1.0 | 2024-03-22 | 初始版本，包含完整使用说明和示例 |

### B. 相关文档

- [Notebook 设计方案](./Notebook设计方案.md) - 架构设计文档
- [API 参考](./API参考.md) - 详细 API 文档（如有）

### C. 反馈与支持

如有问题或建议，请通过以下方式反馈：

- 提交 Issue
- 联系开发团队

***

**Happy Analyzing! 📊**
