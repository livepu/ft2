# Notebook - HTML 报告生成器

> 基于 Jinja2 + ECharts 的轻量级报告生成组件

---

## 特性

- 🎨 **美观的 HTML 输出** - 基于 Jinja2 模板，支持自定义样式
- 📊 **丰富的图表类型** - 折线图、柱状图、饼图、散点图、K线图等
- 📋 **智能表格组件** - 支持冻结列、分页、热力图
- 🎯 **指标卡片** - 一键生成核心指标展示
- 📦 **章节容器** - 支持嵌套、折叠的章节结构
- 🔗 **链式调用** - 流畅的 API 设计

---

## 快速开始

### 安装

```bash
# ft2 项目已包含此模块，无需额外安装
# 依赖：pandas, jinja2, pyecharts
```

### 基础示例

```python
from notebook import Notebook

# 创建报告
nb = Notebook("策略回测报告")

# 添加指标卡片
nb.metrics([
    {'name': '总收益率', 'value': '45.2%', 'color': 'green'},
    {'name': '夏普比率', 'value': '1.85'},
    {'name': '最大回撤', 'value': '-12.5%', 'color': 'red'},
])

# 添加表格
nb.table(
    data=[{'code': '000001', 'name': '平安银行', 'return': 0.15}],
    columns=['code', 'name', 'return'],
    title='持仓明细'
)

# 添加图表
nb.chart('line', {
    'x': ['2024-01', '2024-02', '2024-03'],
    'series': [{'name': '净值', 'data': [1.0, 1.05, 1.12]}]
}, title='净值曲线')

# 导出 HTML
nb.export_html("report.html")
```

---

## API 文档

### Notebook 类

#### 构造函数

```python
Notebook(title: str = "Notebook Report")
```

**参数：**
- `title` - 报告标题

---

### 指标卡片

```python
nb.metrics(data, title: str = None, columns: int = 4)
```

**参数：**
- `data` - 指标数据
  - `List[Dict]` 格式：`[{'name': '指标名', 'value': '指标值', 'color': '颜色'}, ...]`
  - `Dict` 格式：`{'指标名': '指标值', ...}`（自动转换）
- `title` - 标题（可选）
- `columns` - 每行显示的卡片数量，默认 4

**示例：**

```python
# List[Dict] 格式（推荐）
nb.metrics([
    {'name': '收益率', 'value': '15%', 'color': 'green'},
    {'name': '夏普', 'value': '1.5'},
])

# Dict 格式（便捷）
nb.metrics({
    '收益率': '15%',
    '夏普': '1.5',
})
```

**颜色支持：**
- `red`, `green`, `blue`, `yellow`, `orange`, `purple`, `gray` 等

---

### 表格

```python
nb.table(data, columns=None, title=None, **options)
```

**参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| `data` | List[Dict] / DataFrame | 表格数据 |
| `columns` | List[str] | 列名列表，指定显示的列及顺序 |
| `title` | str | 标题（可选） |
| `freeze` | Dict | 冻结列配置，如 `{'left': 2, 'right': 1}` |
| `page` | Dict / False | 分页配置，如 `{'size': 20}` 或 `False` 禁用 |
| `heatmap` | Dict | 热力图配置 |

**示例：**

```python
# 基础表格
nb.table(data, columns=['code', 'name', 'return'])

# 冻结列
nb.table(data, freeze={'left': 2})

# 分页配置
nb.table(data, page={'size': 20, 'options': [10, 20, 50, 100]})

# 禁用分页
nb.table(data, page=False)

# 热力图
nb.table(data, heatmap={'start': 2, 'end': 5, 'axis': 'column'})
```

---

### 图表

```python
nb.chart(chart_type, data, title=None)
```

**支持的图表类型：**

| 类型 | 说明 | 数据格式 |
|---|---|---|
| `line` | 折线图 | `{'x': [...], 'series': [...]}` |
| `bar` | 柱状图 | `{'x': [...], 'series': [...]}` |
| `pie` | 饼图 | `{'data': [{'name': ..., 'value': ...}]}` |
| `scatter` | 散点图 | `{'data': [{'x': ..., 'y': ...}]}` |
| `kline` | K线图 | `{'data': [[open, close, low, high], ...]}` |

**示例：**

```python
# 折线图（多系列）
nb.chart('line', {
    'x': ['2024-01', '2024-02', '2024-03'],
    'series': [
        {'name': '净值', 'data': [1.0, 1.05, 1.12]},
        {'name': '基准', 'data': [1.0, 1.02, 1.05]},
    ]
}, title='净值曲线')

# 柱状图
nb.chart('bar', {
    'x': ['股票', '债券', '现金'],
    'series': [{'name': '权重', 'data': [60, 30, 10]}]
}, title='资产配置')

# 饼图
nb.chart('pie', {
    'data': [
        {'name': '股票', 'value': 60},
        {'name': '债券', 'value': 30},
        {'name': '现金', 'value': 10},
    ]
}, title='资产分布')

# 散点图
nb.chart('scatter', {
    'data': [
        {'x': 1, 'y': 2, 'name': 'A'},
        {'x': 3, 'y': 5, 'name': 'B'},
    ]
}, title='风险收益分布')
```

---

### 章节容器

```python
with nb.section(title, collapsed=None):
    # 添加内容
    nb.metrics([...])
    nb.table(data)
```

**参数：**
- `title` - 章节标题
- `collapsed` - 折叠状态
  - `None` - 不可折叠（默认）
  - `True` - 可折叠，默认折叠
  - `False` - 可折叠，默认展开

**示例：**

```python
# 基础章节
with nb.section("收益分析"):
    nb.metrics([...], title="核心指标")
    nb.chart('line', {...}, title="净值曲线")

# 可折叠章节
with nb.section("详细数据", collapsed=True):
    nb.table(data)

# 嵌套章节
with nb.section("风险分析"):
    with nb.section("回撤分析"):
        nb.chart('line', {...})
```

---

### Grid 图表（多图合并）

```python
nb.chartg(chart_type, data, height=200, **kwargs)
```

将多个图表合并为一个 Grid 布局。

**示例：**

```python
# 累加多个图表到 Grid
nb.chartg('line', data1, height=200)  # 第一个图
nb.chartg('bar', data2, height=150)   # 第二个图
# 在下一个 cell 或 section 退出时自动合并输出
```

---

### 文本与标题

```python
# 标题
nb.title("报告标题", level=1)  # level: 1-6

# 文本
nb.text("普通文本")
nb.text("红色文本", color='red')

# Markdown
nb.markdown("""
## 标题
- 列表项1
- 列表项2
""")

# 分隔线
nb.divider()

# 代码块
nb.code("print('hello')", language='python', output='hello')
```

---

### 导出

```python
nb.export_html(path)
```

**参数：**
- `path` - 输出文件路径

---

## 数据格式

### 表格数据

```python
# List[Dict] 格式（推荐）
data = [
    {'code': '000001', 'name': '平安银行', 'return': 0.15},
    {'code': '000002', 'name': '万科A', 'return': -0.05},
]

# DataFrame 格式（自动转换）
import pandas as pd
df = pd.DataFrame(data)
nb.table(df, columns=['code', 'name', 'return'])
```

### 图表数据

```python
# 折线图/柱状图
{
    'x': ['2024-01', '2024-02', '2024-03'],  # X轴
    'series': [
        {'name': '净值', 'data': [1.0, 1.05, 1.12]},
        {'name': '基准', 'data': [1.0, 1.02, 1.05]},
    ]
}

# 饼图
{
    'data': [
        {'name': '股票', 'value': 60},
        {'name': '债券', 'value': 30},
        {'name': '现金', 'value': 10},
    ]
}

# 散点图
{
    'data': [
        {'x': 1, 'y': 2, 'name': 'A'},
        {'x': 3, 'y': 5, 'name': 'B'},
    ]
}
```

---

## 完整示例

### 回测报告

```python
from notebook import Notebook
from core.analyzer import AccountAnalyzer

def generate_backtest_report(account, output_path):
    """生成回测报告"""
    
    analyzer = AccountAnalyzer(account=account)
    
    nb = Notebook("策略回测报告")
    
    # 核心指标
    nb.metrics({
        '总收益率': f"{analyzer.returns().sum()*100:.2f}%",
        '年化收益': f"{analyzer.annual_return()*100:.2f}%",
        '夏普比率': f"{analyzer.sharpe_ratio():.2f}",
        '最大回撤': f"{analyzer.max_drawdown()*100:.2f}%",
    }, title="核心指标")
    
    # 净值曲线
    nb.chart('line', {
        'x': analyzer.daily_returns.index.tolist(),
        'series': [{'name': '净值', 'data': analyzer.nav().tolist()}]
    }, title="净值曲线")
    
    # 风险分析章节
    with nb.section("风险分析"):
        nb.chart('line', {
            'x': analyzer.daily_returns.index.tolist(),
            'series': [{'name': '回撤', 'data': analyzer.drawdown().tolist()}]
        }, title="回撤曲线")
    
    # 详细数据（可折叠）
    with nb.section("交易明细", collapsed=True):
        nb.table(analyzer.trade_records(), columns=['date', 'code', 'action', 'price'])
    
    nb.export_html(output_path)
    return output_path
```

### 因子分析报告

```python
def generate_factor_report(factor_results, output_path):
    """生成因子分析报告"""
    
    nb = Notebook("因子分析报告")
    
    # IC 统计
    nb.metrics({
        'IC均值': f"{factor_results['ic_mean']:.4f}",
        'IC标准差': f"{factor_results['ic_std']:.4f}",
        'IR': f"{factor_results['ir']:.4f}",
        'IC>0占比': f"{factor_results['ic_positive_ratio']*100:.1f}%",
    }, title="IC统计")
    
    # IC 序列
    nb.chart('bar', {
        'x': factor_results['dates'],
        'series': [{'name': 'IC', 'data': factor_results['ic_series']}]
    }, title="IC序列")
    
    # 分组收益
    with nb.section("分组收益"):
        nb.table(
            factor_results['group_returns'],
            columns=['group', 'return', 'count'],
            heatmap={'start': 1, 'axis': 'column'}
        )
    
    nb.export_html(output_path)
```

---

## 模板定制

### 默认模板路径

```
ft2/template/notebook.html    # HTML 模板
ft2/template/ft-table.js     # 表格组件
```

### 自定义模板

```python
# 在 Notebook 构造函数中指定模板路径
nb = Notebook("报告", template_path="custom_template.html")
```

---

## 依赖

- Python >= 3.8
- pandas
- jinja2
- pyecharts

---

## 许可证

MIT License

---

## 更新日志

### v1.0.0 (2024-01-01)

- 初始版本
- 支持基础图表、表格、指标卡片
- 支持章节容器和折叠

### v1.1.0 (2024-03-01)

- 添加 Grid 图表支持
- 添加热力图支持
- 优化表格分页

---

> 作者：ft2 团队
> 最后更新：2026-04-04
