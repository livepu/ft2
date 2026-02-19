# Notebook 可视化设计方案 V2

> 制定时间：2025-02-19
> 目标：构建统一、规范、交互友好的可视化系统
> 技术方案：Section 模块化布局 + pyecharts 图表 + Notion 风格样式

---

## 1. 核心架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    ft2 Notebook 系统                     │
├─────────────────────────────────────────────────────────┤
│  数据层                                                  │
│  ├── Cell: 内容单元（类型 + 内容 + 标题 + 配置）          │
│  └── CellBuilder: 静态工厂方法创建各类 Cell              │
├─────────────────────────────────────────────────────────┤
│  逻辑层                                                  │
│  ├── Notebook: 管理 Cells 集合                          │
│  ├── SectionContext: 上下文管理器实现 Section 嵌套        │
│  └── 栈结构: 支持多层 Section 嵌套                       │
├─────────────────────────────────────────────────────────┤
│  表现层                                                  │
│  ├── Jinja2 模板: 渲染 HTML 结构                         │
│  ├── Alpine.js: 交互逻辑（表格排序、折叠展开）            │
│  ├── ECharts: 图表渲染                                   │
│  └── Notion 风格 CSS: 模块化视觉设计                     │
└─────────────────────────────────────────────────────────┘
```

### 1.2 模块层次关系

```
Notebook (报告)
├── Section (一级模块)
│   ├── Cell (内容块: text/markdown/table/metrics/chart...)
│   └── Section.nested-section (二级模块)
│       ├── Cell
│       └── Section.nested-section (三级模块)
│           └── Cell
```

**设计原则**:
- **Section** 是模块容器，带标题，可嵌套
- **Cell** 是内容块，统一在 Section 内容区内
- 层级通过 CSS 类区分（颜色、边框、背景）

---

## 2. Cell 类型体系

### 2.1 CellType 枚举

```python
class CellType(Enum):
    TITLE = "title"           # 标题
    TEXT = "text"             # 纯文本
    MARKDOWN = "markdown"     # Markdown 内容
    CODE = "code"             # 代码块
    TABLE = "table"           # 数据表格
    METRICS = "metrics"       # 指标卡片网格
    CHART = "chart"           # ECharts 图表
    HEATMAP = "heatmap"       # 热力图
    PYECHARTS = "pyecharts"   # pyecharts 图表
    DIVIDER = "divider"       # 分隔线
    COLLAPSIBLE = "collapsible"  # 可折叠区域
    HTML = "html"             # 原始 HTML
    SECTION = "section"       # 嵌套 Section
```

### 2.2 Cell 数据结构

```python
@dataclass
class Cell:
    type: CellType            # 类型
    content: Any              # 内容（根据类型变化）
    title: Optional[str]      # 标题（可选）
    options: Dict             # 配置选项
    created_at: datetime      # 创建时间
```

### 2.3 各类型内容格式

| 类型 | content 格式 | options 常用字段 |
|------|-------------|-----------------|
| TITLE | str | level: 1/2/3 |
| TEXT | str | style: normal/heading/code |
| MARKDOWN | str | - |
| CODE | {code, language, output} | - |
| TABLE | List[Dict] | columns: List[str] |
| METRICS | List[Dict{name,value,desc}] | columns: int |
| CHART | {chart_type, data} | height, color, ... |
| PYECHARTS | {option, width, height} | - |
| COLLAPSIBLE | List[Cell] | collapsed: bool |
| SECTION | List[Cell] | level: int |

---

## 3. Notebook API 设计

### 3.1 基础用法

```python
from notebook import Notebook

# 创建报告
nb = Notebook("策略回测报告")

# 添加内容（链式调用）
nb.add_title("回测结果", level=1) \
  .add_text("本报告展示策略表现...") \
  .add_metrics([
      {'name': '总收益', 'value': '45.6%', 'desc': '累计'},
      {'name': '夏普比率', 'value': '1.85', 'desc': '风险调整后'}
  ], title="核心指标")

# 导出
nb.export_html("report.html")
```

### 3.2 Section 模块化用法

```python
# 方式1: 上下文管理器（推荐）
with nb.section("收益分析"):
    nb.add_metrics([...], title="收益指标")
    nb.add_line_chart(dates, series, title="净值曲线")
    
    with nb.section("月度统计"):  # 嵌套
        nb.add_bar_chart(months, returns, title="月度收益")

# 方式2: 链式调用（Section 内）
with nb.section("风险分析"):
    nb.add_metrics([...], title="风险指标") \
      .add_area_chart(dates, drawdowns, title="回撤曲线") \
      .add_heatmap(monthly_data, title="月度热力图")
```

### 3.3 完整 API 列表

```python
# 标题文本
add_title(text, level=1)
add_text(text, style='normal')
add_markdown(text)
add_divider()

# 代码
add_code(code, language='python', output=None)

# 表格
add_table(data, columns=None, title=None)
add_dataframe(df, title=None, columns=None)

# 指标
add_metrics(data, title=None, columns=4)

# 图表
add_line_chart(dates, series, title=None, **options)
add_area_chart(dates, series, title=None, **options)
add_bar_chart(categories, series, title=None, **options)
add_pie_chart(data, title=None, **options)
add_heatmap(data, title=None, **options)
add_pyecharts(chart, title=None, height=400, width='100%')

# 快捷方法
add_equity_curve(dates, values, title='权益曲线', benchmark_values=None)
add_drawdown_chart(dates, drawdowns, title='回撤曲线')
add_monthly_returns_heatmap(monthly_returns, title='月度收益热力图')

# 其他
add_collapsible(title, cells, collapsed=True)
add_collapsible_table(title, data, columns=None, collapsed=True)
add_html(html_content)

# Section 容器
section(title, level=None) -> SectionContext
```

---

## 4. Section 上下文管理器实现

### 4.1 核心原理

```python
class SectionContext:
    """Section 上下文管理器"""
    
    def __init__(self, notebook, title, level=1):
        self.notebook = notebook
        self.title = title
        self.level = level
        self.cells = []  # 临时存储
    
    def __enter__(self):
        # 进入 with 块：入栈
        self.notebook._push_section(self)
        return self.notebook
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 退出 with 块：出栈，创建 Section Cell
        section_cell = CellBuilder.section(self.title, self.cells, self.level)
        self.notebook._pop_section()
        self.notebook._add_cell(section_cell)
```

### 4.2 栈机制

```python
class Notebook:
    def __init__(self):
        self._section_stack = []  # 栈结构
    
    def _add_cell(self, cell):
        if self._section_stack:
            # 有嵌套：添加到当前 Section
            self._section_stack[-1].cells.append(cell)
        else:
            # 无嵌套：添加到顶层
            self.cells.append(cell)
```

### 4.3 层级自动计算

```python
def section(self, title, level=None):
    if level is None:
        level = len(self._section_stack) + 1  # 自动计算
    return SectionContext(self, title, level)
```

---

## 5. 模板渲染系统

### 5.1 HTML 结构

```html
<div class="notebook-container">
    <div class="notebook-header">
        <h1>{{ title }}</h1>
        <span>{{ createdAt }}</span>
    </div>
    
    <template x-for="cell in cells">
        <!-- Section 类型 -->
        <template x-if="cell.type === 'section'">
            <div class="section">
                <div class="section-title" x-text="cell.title"></div>
                <div class="section-content">
                    <!-- 渲染子 Cells -->
                </div>
            </div>
        </template>
        
        <!-- 其他类型 -->
        <template x-if="cell.type !== 'section'">
            <div class="cell">
                <!-- 根据类型渲染 -->
            </div>
        </template>
    </template>
</div>
```

### 5.2 Notion 风格 CSS

```css
/* Section 模块 */
.section {
    border-radius: 6px;
    margin: 12px 0;
    background: #fff;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    border: 1px solid #e9e9e9;
}
.section-title {
    font-size: 15px;
    font-weight: 600;
    padding: 14px 16px;
    background: linear-gradient(90deg, #fafafa 0%, #fff 100%);
    color: #37352f;
}
.section-content {
    padding: 14px 16px;
}

/* Cell 内容块 */
.cell {
    background: #f7f6f3;
    border-radius: 6px;
    margin: 8px 0;
    padding: 12px 14px;
}

/* 嵌套 Section */
.nested-section {
    border-left: 4px solid #9b51e0;
    background: #faf9f7;
}
.nested-section .section-title {
    color: #6b5b95;
}
.nested-section .nested-section {
    border-left-color: #ff9500;
}
.nested-section .nested-section .section-title {
    color: #c68a00;
}
```

### 5.3 层级颜色规范

| 层级 | 左边框 | 标题颜色 | 背景 |
|------|--------|---------|------|
| Level 1 | 无 | #37352f | 白色 |
| Level 2 | #9b51e0 紫色 | #6b5b95 | #faf9f7 |
| Level 3 | #ff9500 橙色 | #c68a00 | #fffdf7 |

---

## 6. pyecharts 集成

### 6.1 使用方式

```python
from pyecharts.charts import Kline
from pyecharts import options as opts

# 创建 pyecharts 图表
kline = (
    Kline()
    .add_xaxis(dates)
    .add_yaxis("K线", kline_data)
    .set_global_opts(title_opts=opts.TitleOpts(title="K线图"))
)

# 添加到 Notebook
nb.add_pyecharts(kline, title="K线图", height=500)
```

### 6.2 数据转换

```python
def df_to_kline_data(df):
    """DataFrame 转 pyecharts K线数据 [open, close, low, high]"""
    return df[['open', 'close', 'low', 'high']].values.tolist()
```

---

## 7. 文件结构

```
ft2/
├── notebook/
│   ├── __init__.py              # 导出 Notebook, Cell, CellType
│   ├── notebook.py              # Notebook 主类 + SectionContext
│   ├── cell.py                  # Cell 数据类 + CellBuilder
│   ├── 设计方案V2.md            # 本文档
│   └── charts/                  # 图表辅助函数（可选）
│       ├── __init__.py
│       └── helpers.py
├── template/
│   ├── notebook.html            # 主模板（Notion 风格）
│   ├── js/
│   │   ├── alpine.min.js        # Alpine.js
│   │   ├── alpine-table.js      # 表格组件
│   │   └── echarts.min.js       # ECharts
│   └── css/
│       └── notion-style.css     # 样式（可选分离）
├── test_notebook.py             # 综合测试示例
├── 新式风格.html                # 样式参考
└── demo_pyecharts.py            # pyecharts 示例
```

---

## 8. 特性总结

### 8.1 核心特性

| 特性 | 说明 |
|------|------|
| **模块化布局** | Section 容器 + Cell 内容块，层次清晰 |
| **上下文管理** | `with nb.section()` 语法，自动层级计算 |
| **链式调用** | 所有 `add_xxx` 方法返回 self |
| **统一样式** | Notion 风格，三层嵌套颜色区分 |
| **pyecharts** | 直接集成，支持所有 ECharts 图表 |
| **交互表格** | 排序、分页、搜索 |
| **可折叠** | 支持 collapsible 区域 |

### 8.2 与 V1 对比

| 项目 | V1 | V2 |
|------|-----|-----|
| 布局方式 | Cell 平铺 | Section 模块化嵌套 |
| 样式风格 | 混合 | 统一 Notion 风格 |
| 层级支持 | 单层 | 三层嵌套 |
| API 风格 | 单一 | 上下文管理器 + 链式 |
| 代码高亮 | 基础 | 完整语法高亮 |
| 可折叠 | 无 | 支持 |

---

## 9. 使用示例

### 9.1 简单报告

```python
nb = Notebook("日报")
nb.add_title("今日行情", level=1)
nb.add_metrics([
    {'name': '上证指数', 'value': '3,050.21', 'desc': '+0.52%'},
    {'name': '深证成指', 'value': '9,875.43', 'desc': '+0.81%'},
])
nb.export_html("daily.html")
```

### 9.2 复杂报告

```python
nb = Notebook("策略回测报告")

with nb.section("报告概述"):
    nb.add_markdown("**策略**: 双均线 | **周期**: 2024-01 ~ 2024-12")

with nb.section("核心指标"):
    nb.add_metrics([...], title="收益指标")
    nb.add_metrics([...], title="风险指标")

with nb.section("收益分析"):
    nb.add_line_chart(dates, series, title="净值曲线")
    
    with nb.section("月度统计"):
        nb.add_bar_chart(months, returns, title="月度收益")
        nb.add_heatmap(monthly_data, title="热力图")

with nb.section("交易记录"):
    nb.add_collapsible_table("历史明细", trades, collapsed=True)

nb.export_html("report.html")
```

---

## 10. 参考文档

- pyecharts: https://pyecharts.org/
- ECharts: https://echarts.apache.org/
- Alpine.js: https://alpinejs.dev/

---

## 附录：版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| V1 | 2025-02 | 基础 Notebook 系统，pyecharts 集成 |
| V2 | 2025-02-19 | Section 模块化布局，Notion 风格，上下文管理器 |
