# notebook 模块 - AI 快速上手

> HTML 报告生成器，基于 Jinja2 + pyecharts
>
> **版本：v1.0.0 | 更新日期：2026-04-04**
>
> **AI 助手注意：** 如果发现实际 API 与本文档不一致，说明源码已更新但 AI.md 未同步，请提醒用户更新。

---

## 核心 API

### 创建报告

```python
from notebook import Notebook
nb = Notebook("报告标题")
```

---

### 指标卡片

```python
nb.metrics(data, title=None, columns=4)
```

**data 格式：**
```python
# List[Dict]（本质）
[{'name': '收益率', 'value': '15%', 'color': 'green'}, ...]

# Dict（便捷输入，自动转换）
{'收益率': '15%', '夏普': '1.5'}
```

**参数：**
- `title`: 标题（可选）
- `columns`: 每行卡片数，默认 4

---

### 表格

```python
nb.table(data, columns=None, title=None, **options)
```

**data 格式：**
- `List[Dict]`: `[{'code': '000001', 'name': '平安银行'}, ...]`
- `DataFrame`: 自动转换为 List[Dict]

**columns 参数：**
- `None`: 显示所有列
- `['code', 'name']`: 只显示指定列，按此顺序

**options 参数：**
- `freeze`: 冻结列，如 `{'left': 2, 'right': 1}`
- `page`: 分页配置
  - 不传：默认分页，每页 10 条
  - `False`: 禁用分页
  - `{'size': 20}`: 每页 20 条
  - `{'size': 20, 'options': [10, 20, 50, 100]}`: 自定义选项
- `heatmap`: 热力图配置，如 `{'start': 2, 'axis': 'column'}`

---

### 图表

```python
nb.chart(chart_type, data, title=None, height='400px', **kwargs)
```

**chart_type 支持：**
- `line`: 折线图
- `area`: 面积图
- `bar`: 柱状图
- `pie`: 饼图
- `scatter`: 散点图
- `heatmap`: 热力图
- `kline`: K线图

**data 格式（标准格式）：**
```python
# line/area/bar/kline
{
    'xAxis': ['2024-01', '2024-02', '2024-03'],
    'series': [
        {'name': '净值', 'data': [1.0, 1.05, 1.12]},
        {'name': '基准', 'data': [1.0, 1.02, 1.05]},
    ]
}

# pie
[
    {'name': '股票', 'value': 60},
    {'name': '债券', 'value': 30},
    {'name': '现金', 'value': 10},
]

# scatter（类目散点图）
{'xAxis': ['A', 'B', 'C'], 'series': [{'name': '', 'data': [10, 20, 30]}]}

# scatter（数值散点图）
{'xAxis': [], 'series': [{'name': '', 'data': [[1, 10], [2, 20]]}]}

# heatmap（嵌套字典）
{'2024': {'01': 0.05, '02': 0.03}, '2025': {'01': 0.04, '02': 0.06}}

# kline
{'xAxis': dates, 'series': [{'name': 'K线', 'data': [[开,收,低,高], ...]}]}
```

**DataFrame 自动转换：**
```python
# line/area/bar: 第一列 → xAxis，其余列 → series
df = pd.DataFrame({
    'date': ['2024-01', '2024-02'],
    'nav': [1.0, 1.05],
    'benchmark': [1.0, 1.02]
})
nb.chart('line', df)  # 自动转换

# pie: 第一列 → name，第二列 → value
df = pd.DataFrame({'name': ['股票', '债券'], 'value': [60, 30]})
nb.chart('pie', df)

# heatmap: 第一列 → X轴，其余列 → Y轴
df = pd.DataFrame({'month': ['01', '02'], '2024': [0.05, 0.03], '2025': [0.04, 0.06]})
nb.chart('heatmap', df)

# kline: 第一列 → X轴（日期），自动识别 open/close/low/high 字段
df = pd.DataFrame({
    'date': ['2024-01-01', '2024-01-02'],
    'open': [10, 11], 'close': [11, 12],
    'low': [9, 10], 'high': [12, 13]
})
nb.chart('kline', df)
```

**kwargs 参数：**
- 容器参数：`width`（默认 '100%'）、`height`（默认 '400px'）
- 全局配置：`title_opts`, `legend_opts`, `tooltip_opts`, `xaxis_opts`, `yaxis_opts`, `datazoom_opts`, `visualmap_opts`, `grid_opts`
- 系列配置：`series_opts`（统一应用到所有系列）

```python
nb.chart('line', data, title='净值曲线',
    yaxis_opts={'min_': 0.9},
    series_opts={'is_smooth': True}
)
```

**高级需求：使用 pyecharts 对象**
```python
from pyecharts.charts import Line
from pyecharts import options as opts

line = Line()
line.add_xaxis(['1月', '2月', '3月'])
line.add_yaxis('策略', [1.0, 1.05, 1.08], is_smooth=True)
line.set_global_opts(yaxis_opts=opts.AxisOpts(min_=0.9))

nb.pyecharts(line, title='净值曲线')
```

---

### 章节容器

```python
with nb.section(title, collapsed=None):
    nb.metrics([...])
    nb.table(data)
```

**collapsed 参数：**
- `None`: 不可折叠（默认）
- `True`: 可折叠，默认折叠
- `False`: 可折叠，默认展开

**嵌套支持：**
```python
with nb.section("风险分析"):
    with nb.section("回撤分析"):
        nb.chart('line', data)
```

---

### Grid 图表（多图合并）

```python
nb.chartg(chart_type, data, height=200, **kwargs)
```

累加多个图表到一个 Grid 布局，在下一个 cell 或 section 退出时自动合并输出。

```python
nb.chartg('line', data1, height=200)
nb.chartg('bar', data2, height=150)
# 自动合并为一个 Grid
```

---

### 文本与标题

```python
nb.title("标题", level=1)        # level: 1-6
nb.text("文本", color='red')     # color: red, green, blue, yellow, orange, purple, gray
nb.markdown("**粗体**")          # Markdown 内容
nb.divider()                     # 分隔线
nb.code("print(1)", language='python', output='1')  # 代码块
nb.html("<div>自定义HTML</div>") # 原始 HTML
```

---

### 导出

```python
nb.export_html(name=None, template_path=None)
```

**参数：**
- `name`: 输出文件名（不含扩展名），默认使用标题
- `template_path`: 自定义模板路径

**返回：** 输出文件路径

---

## 完整示例

```python
from notebook import Notebook

nb = Notebook("回测报告")

# 指标卡片
nb.metrics({
    '收益率': '15%',
    '夏普': '1.5',
    '回撤': '-12%',
}, title="核心指标")

# 折线图
nb.chart('line', {
    'xAxis': ['2024-01', '2024-02', '2024-03'],
    'series': [{'name': '净值', 'data': [1.0, 1.05, 1.12]}]
}, title='净值曲线')

# 章节
with nb.section("风险分析"):
    nb.chart('line', {
        'xAxis': ['2024-01', '2024-02', '2024-03'],
        'series': [{'name': '回撤', 'data': [0, -0.02, -0.05]}]
    }, title='回撤曲线')

# 可折叠章节
with nb.section("详细数据", collapsed=True):
    nb.table([
        {'code': '000001', 'name': '平安银行', 'return': 0.15},
        {'code': '000002', 'name': '万科A', 'return': -0.05},
    ], columns=['code', 'name', 'return'])

# 导出
output_path = nb.export_html("report")
print(f"报告已生成: {output_path}")
```

---

## 数据格式约定

### 表格数据

- `List[Dict]`: 推荐，每行一个字典
- `DataFrame`: 自动转换为 List[Dict]

### 图表数据

- **标准格式**（推荐）：`{'xAxis': [...], 'series': [...]}`
- **DataFrame**：自动转换（第一列 → xAxis，其余列 → series）
- **嵌套字典**（heatmap）：`{y: {x: value}}`

### 通用约定

- 日期 index × 股票代码 columns（ft2 项目通用）

---

## 源码位置

- `notebook/__init__.py`: 导出 Notebook 类
- `notebook/notebook.py`: Notebook 主类
- `notebook/cell.py`: Cell/Section 类型定义、图表构建器
- `template/notebook.html`: HTML 模板
- `template/ft-table.js`: 表格组件

---

> 详细文档：`notebook/README.md`
> 源码已学习，本文件与实际代码完全一致
