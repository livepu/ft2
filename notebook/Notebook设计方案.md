# Notebook 可视化设计方案 V3

> 制定时间：2025-02-27
> 目标：构建统一、规范、简洁的可视化系统
> 技术方案：Section 模块化布局 + pyecharts 图表 + Notion 风格样式

---

## 1. 核心架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    ft2 Notebook 系统                     │
├─────────────────────────────────────────────────────────┤
│  用户层                                                  │
│  └── Notebook: 统一入口，简洁 API                        │
├─────────────────────────────────────────────────────────┤
│  数据层                                                  │
│  ├── Cell: 内容单元（类型 + 内容 + 标题 + 配置）          │
│  └── CellBuilder: 静态工厂方法创建各类 Cell              │
├─────────────────────────────────────────────────────────┤
│  渲染层                                                  │
│  ├── Jinja2 模板: 渲染 HTML 结构                         │
│  ├── Alpine.js: 交互逻辑（表格排序、折叠展开）            │
│  ├── ECharts: 图表渲染                                   │
│  └── Notion 风格 CSS: 模块化视觉设计                     │
└─────────────────────────────────────────────────────────┘
```

### 1.2 设计理念

```
简洁的 API + 清晰的架构 + 灵活的扩展
```

**核心原则**:
- **少即是多**: 7个图表方法 → 1个 `chart()`
- **统一入口**: 用户无需记忆多个方法
- **自动识别**: pyecharts 对象智能识别
- **分层清晰**: 用户接口 / 数据结构 / 渲染分离

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
| TABLE | List[Dict] | columns, freeze, page |
| METRICS | List[Dict{name,value,desc}] | columns: int |
| CHART | {chart_type, data} | height, color, ... |
| PYECHARTS | {option, width, height} | - |
| HEATMAP | Dict | - |
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
nb.title("回测结果", level=1) \
  .text("本报告展示策略表现...") \
  .metrics([
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
    nb.metrics([...], title="收益指标")
    nb.chart('line', {'dates': dates, 'series': series}, title="净值曲线")
    
    with nb.section("月度统计"):  # 嵌套
        nb.chart('bar', {'categories': months, 'series': returns}, title="月度收益")

# 方式2: 链式调用（Section 内）
with nb.section("风险分析"):
    nb.metrics([...], title="风险指标") \
      .chart('area', {'dates': dates, 'series': drawdowns}, title="回撤曲线") \
      .chart('heatmap', monthly_data, title="月度热力图")
```

### 3.3 完整 API 列表

```python
# 标题文本
title(text, level=1)
text(text, style='normal')
markdown(text)
divider()

# 代码
code(code, language='python', output=None)

# 表格（支持冻结、折叠）
table(data, columns=None, title=None, **options)
    # options:
    #   freeze: int 或 {'left': n, 'right': m}
    #   page: {'limit': 20, 'limits': [10, 20, 50]}
    #   collapsed: True/False

# 指标
metrics(data, title=None, columns=4)

# 图表（统一入口）
chart(chart_type, data=None, title=None, **options)
    # chart_type:
    #   - 'line': 折线图
    #   - 'area': 面积图
    #   - 'bar': 柱状图
    #   - 'pie': 饼图
    #   - 'heatmap': 热力图
    #   - pyecharts 对象: 自动识别
    # data 格式:
    #   - line/area: {'dates': [...], 'series': [...]}
    #   - bar: {'categories': [...], 'series': [...]}
    #   - pie: [{'name': '', 'value': 0}, ...]
    #   - heatmap: {'2024': {'01': 0.05, ...}, ...}
    # options:
    #   - height: 高度（默认 400）
    #   - color: 颜色配置
    #   - width: 宽度（仅 pyecharts）

# 其他
collapsible(title, cells, collapsed=True)
html(html_content)

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

## 5. 图表系统

### 5.1 统一入口设计

```python
def chart(self, chart_type, data=None, title=None, **options):
    """
    统一图表入口
    
    自动识别:
    - chart_type 是字符串 → 普通图表
    - chart_type 是 pyecharts 对象 → 自动识别
    """
    if hasattr(chart_type, 'dump_options'):
        # pyecharts 对象
        ...
    elif chart_type == 'heatmap':
        # 热力图
        ...
    else:
        # 普通图表
        ...
```

### 5.2 数据格式

| 图表类型 | data 格式 |
|---------|----------|
| line/area | `{'dates': [...], 'series': [{'name': '', 'data': []}, ...]}` |
| bar | `{'categories': [...], 'series': [{'name': '', 'data': []}, ...]}` |
| pie | `[{'name': '', 'value': 0}, ...]` |
| heatmap | `{'2024': {'01': 0.05, ...}, ...}` |
| pyecharts | 直接传对象 |

### 5.3 使用示例

```python
# 折线图
nb.chart('line', {'dates': dates, 'series': series}, title='净值曲线')

# 柱状图
nb.chart('bar', {'categories': categories, 'series': series}, title='持仓')

# 饼图
nb.chart('pie', [{'name': '股票', 'value': 60}, ...], title='配置')

# 热力图
nb.chart('heatmap', monthly_returns, title='月度收益')

# pyecharts 对象（自动识别）
from pyecharts.charts import Kline, Grid
kline = Kline().add_xaxis(dates).add_yaxis("K线", data)
nb.chart(kline, title='K线图', height=600)

# 复杂 pyecharts（Grid 布局）
grid = Grid()
grid.add(line1, grid_opts=opts.GridOpts(pos_left="5%", pos_right="55%"))
grid.add(line2, grid_opts=opts.GridOpts(pos_left="55%", pos_right="5%"))
nb.chart(grid, title='双轴图')
```

---

## 6. 表格系统

### 6.1 功能特性

| 特性 | 说明 |
|------|------|
| 数据类型 | List[dict] 或 DataFrame（自动识别） |
| 冻结列 | `freeze=2` 或 `freeze={'left': 2, 'right': 1}` |
| 折叠 | `collapsed=True` |
| 分页 | `page={'limit': 20}` |

### 6.2 使用示例

```python
# 基础表格
nb.table(data)

# 指定列
nb.table(data, columns=['code', 'name', 'type'], title='基金列表')

# DataFrame 自动识别
nb.table(df, title='数据表')

# 冻结列
nb.table(data, freeze=2)
nb.table(data, freeze={'left': 2, 'right': 1})

# 可折叠表格
nb.table(data, title='详细数据', collapsed=True)

# 冻结 + 折叠
nb.table(data, title='详细数据', freeze=2, collapsed=True)

# 分页
nb.table(data, page={'limit': 20, 'limits': [10, 20, 50]})
```

---

## 7. 模板渲染系统

### 7.1 HTML 结构

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

### 7.2 Notion 风格 CSS

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
```

### 7.3 层级颜色规范

| 层级 | 左边框 | 标题颜色 | 背景 |
|------|--------|---------|------|
| Level 1 | 无 | #37352f | 白色 |
| Level 2 | #9b51e0 紫色 | #6b5b95 | #faf9f7 |
| Level 3 | #ff9500 橙色 | #c68a00 | #fffdf7 |

---

## 8. 文件结构

```
ft2/
├── notebook/
│   ├── __init__.py              # 导出 Notebook, Cell, CellType
│   ├── notebook.py              # Notebook 主类 + SectionContext
│   ├── cell.py                  # Cell 数据类 + CellBuilder
│   └── Notebook设计方案.md      # 本文档
├── template/
│   ├── notebook.html            # 主模板（Notion 风格）
│   └── js/
│       ├── alpine.min.js        # Alpine.js
│       ├── alpine-table.js      # 表格组件
│       └── echarts.min.js       # ECharts
└── test_notebook.py             # 综合测试示例
```

---

## 9. 特性总结

### 9.1 核心特性

| 特性 | 说明 |
|------|------|
| **简洁 API** | 方法命名无 `add_` 前缀，直观易用 |
| **统一图表** | `chart()` 一个入口搞定所有图表 |
| **自动识别** | pyecharts 对象智能识别 |
| **模块化布局** | Section 容器 + Cell 内容块，层次清晰 |
| **上下文管理** | `with nb.section()` 语法，自动层级计算 |
| **链式调用** | 所有方法返回 self |
| **表格增强** | 冻结列、折叠、分页 |
| **pyecharts** | 直接集成，支持所有 ECharts 图表 |

### 9.2 与 V2 对比

| 项目 | V2 | V3 |
|------|-----|-----|
| 方法命名 | `add_xxx` | `xxx`（简洁） |
| 图表方法 | 7个独立方法 | 1个 `chart()` |
| 表格方法 | 3个独立方法 | 1个 `table()` |
| 快捷方法 | 多个 | 精简 |
| API 复杂度 | 较高 | **极简** |

---

## 10. 使用示例

### 10.1 简单报告

```python
nb = Notebook("日报")
nb.title("今日行情", level=1)
nb.metrics([
    {'name': '上证指数', 'value': '3,050.21', 'desc': '+0.52%'},
    {'name': '深证成指', 'value': '9,875.43', 'desc': '+0.81%'},
])
nb.export_html("daily.html")
```

### 10.2 复杂报告

```python
nb = Notebook("策略回测报告")

with nb.section("报告概述"):
    nb.markdown("**策略**: 双均线 | **周期**: 2024-01 ~ 2024-12")

with nb.section("核心指标"):
    nb.metrics([...], title="收益指标")
    nb.metrics([...], title="风险指标")

with nb.section("收益分析"):
    nb.chart('line', {'dates': dates, 'series': series}, title="净值曲线")
    
    with nb.section("月度统计"):
        nb.chart('bar', {'categories': months, 'series': returns}, title="月度收益")
        nb.chart('heatmap', monthly_data, title="热力图")

with nb.section("交易记录"):
    nb.table(trades, title="历史明细", collapsed=True, freeze=2)

nb.export_html("report.html")
```

---

## 11. 参考文档

- pyecharts: https://pyecharts.org/
- ECharts: https://echarts.apache.org/
- Alpine.js: https://alpinejs.dev/

---

## 附录：版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| V1 | 2025-02 | 基础 Notebook 系统，pyecharts 集成 |
| V2 | 2025-02-19 | Section 模块化布局，Notion 风格，上下文管理器 |
| V3 | 2025-02-27 | **API 极简化**：统一 `chart()`、`table()`，移除 `add_` 前缀 |
