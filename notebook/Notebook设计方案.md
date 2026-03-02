# Notebook 可视化设计方案 V3.5

> 制定时间：2025-02-27  
> 修订时间：2026-03-02  
> 目标：构建统一、规范、简洁的可视化系统  
> 技术方案：Section 模块化布局 + pyecharts 图表 + Notion 风格样式  
> **渲染架构：Alpine.js 声明式模板（接受代码重复，确保功能稳定）**

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
│  渲染层 (V3.5 稳定版)                                    │
│  ├── Alpine 声明式模板：x-for + x-if 条件渲染            │
│  ├── 三级嵌套：手动复制（Alpine 不支持递归组件）          │
│  ├── ECharts: 图表渲染                                   │
│  └── Notion 风格 CSS: 模块化视觉设计                     │
└─────────────────────────────────────────────────────────┘
```

### 1.2 设计理念

```
简洁的 API + 清晰的架构 + 稳定的渲染
```

**核心原则**:
- **少即是多**: 7 个图表方法 → 1 个 `chart()`
- **统一入口**: 用户无需记忆多个方法
- **自动识别**: pyecharts 对象智能识别
- **分层清晰**: 用户接口 / 数据结构 / 渲染分离
- **稳定优先**: 接受代码重复，确保功能正常工作

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
    title: Optional[str]       # 标题（可选）
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
# 方式 1: 上下文管理器（推荐）
with nb.section("收益分析"):
    nb.metrics([...], title="收益指标")
    nb.chart('line', {'dates': dates, 'series': series}, title="净值曲线")
    
    with nb.section("月度统计"):  # 嵌套
        nb.chart('bar', {'categories': months, 'series': returns}, title="月度收益")

# 方式 2: 链式调用（Section 内）
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
    #   - pyecharts 对象：自动识别
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
df = pd.DataFrame({
    'date': pd.date_range('2024-01-01', periods=12, freq='M'),
    'strategy': [1.0, 1.05, 1.08, 1.12, 1.15, 1.20, 1.18, 1.25, 1.30, 1.28, 1.35, 1.42],
    'benchmark': [1.0, 1.02, 1.04, 1.06, 1.08, 1.10, 1.09, 1.12, 1.15, 1.14, 1.18, 1.22]
})
nb.chart('line', df_to_line_chart(df, 'date', ['strategy', 'benchmark']), title='净值走势')

# 柱状图
allocation = pd.DataFrame({
    'category': ['股票', '债券', '现金', '其他'],
    'current': [60, 25, 10, 5],
    'target': [50, 30, 15, 5]
})
nb.chart('bar', df_to_bar_chart(allocation, 'category'), title='资产配置')

# 饼图
positions = [{'name': '茅台', 'value': 30}, {'name': '平安', 'value': 25}, {'name': '万科', 'value': 20}, {'name': '现金', 'value': 25}]
nb.chart('pie', positions, title='持仓分布')

# 热力图
monthly_returns = {
    '2023': {'1月': 0.02, '2月': -0.01, '3月': 0.03},
    '2024': {'1月': 0.05, '2月': -0.02, '3月': 0.08}
}
nb.chart('heatmap', monthly_returns, title='月度收益热力图')

# 导出
nb.export_html('report.html')
```

---

## 6. 渲染架构（V3.5 稳定版）

### 6.1 核心思路

**Alpine.js 声明式模板（三级嵌套，手动复制）**

```
JSON 数据 
  ↓ (Jinja2 模板渲染)
HTML 模板（包含 x-data、x-for、x-if 指令）
  ↓ (Alpine.js 自动扫描初始化)
Alpine 组件激活
  ↓ (init() 生命周期)
表格/图表渲染
```

### 6.2 模板结构

```html
<!-- 三级嵌套 Section - 手动复制 -->
<template x-for="(cell, index) in cells" :key="index">
    <div>
        <!-- Level 1: Section -->
        <template x-if="cell.type === 'section'">
            <div class="section">
                <div class="section-title" x-text="cell.title"></div>
                <div class="section-content">
                    <template x-for="(subCell, subIndex) in cell.content">
                        <!-- Level 2: Nested Section -->
                        <template x-if="subCell.type === 'section'">
                            <div class="section nested-section">
                                ...
                                <template x-for="(deepCell, deepIndex) in subCell.content">
                                    <!-- Level 3: Deep Nested -->
                                    <template x-if="deepCell.type === 'section'">
                                        ...
                                    </template>
                                </template>
                            </div>
                        </template>
                        
                        <!-- Table: x-data 声明式 -->
                        <template x-if="subCell.type === 'table'">
                            <div x-data="table({data: subCell.content, ...})"></div>
                        </template>
                    </template>
                </div>
            </div>
        </template>
        
        <!-- 非 Section 类型 -->
        <template x-if="cell.type !== 'section'">
            ...
        </template>
    </div>
</template>
```

### 6.3 为什么选择声明式模板

| 特性 | JS 生成 HTML | Alpine 声明式 | 结论 |
|------|-------------|--------------|------|
| 嵌套层级 | 理论无限 | 3 级手动 | ✅ 声明式足够 |
| 代码重复 | 1 次 | 4 次 | JS 生成更少 |
| 冻结功能 | ❌ 不工作 | ✅ 正常 | **声明式稳定** |
| 初始化时机 | ❌ 复杂 | ✅ 自动 | **声明式可靠** |
| 维护成本 | 低 | 中等 | 可接受 |
| 复杂度 | 高（需处理 initTree） | 低（声明即用） | **声明式简单** |

### 6.4 失败尝试总结（V4 方案）

**V4 尝试的方案**：JS 递归生成 HTML + Alpine.initTree() 激活

**失败原因**：
1. **Alpine 不支持动态初始化**：页面加载后，`x-data` 属性必须已存在于 HTML 中
2. **表格冻结功能失效**：`alpine-table.js` 依赖组件实例（`this.$refs`、`this.$nextTick`），动态添加的属性无法触发组件初始化
3. **初始化链路复杂**：需要精确控制 `innerHTML` → `Alpine.initTree()` → 组件初始化的时序

**教训**：
- Alpine.js 设计理念是"声明式优先"，不适合"动态生成 HTML"的模式
- Vue/React 有真正的组件系统（`$mount` / `createApp`），Alpine 没有
- 接受代码重复，选择稳定的架构，比追求"完美"更重要

---

## 7. 模板渲染系统

### 7.1 HTML 结构

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        <!-- Notion 风格 CSS -->
    </style>
</head>
<body x-data="notebookApp" x-init="init()">
    <!-- Toast 容器 -->
    <!-- TOC 目录面板 -->
    
    <div class="notebook-container">
        <!-- Header -->
        
        <!-- 三级嵌套 Section 模板（手动复制） -->
        <template x-for="(cell, index) in cells">
            ...
        </template>
    </div>
    
    <!-- 依赖脚本 -->
    <script src="alpine-table.js"></script>
    <script src="alpine.min.js" defer></script>
    <script src="echarts.min.js"></script>
    
    <!-- 数据 + 应用逻辑 -->
    <script id="notebook-data">{{ data_json | safe }}</script>
    <script>
        function notebookApp() { ... }
    </script>
</body>
</html>
```

### 7.2 表格组件（冻结功能关键）

```javascript
// alpine-table.js
window.table = function(config) {
    return {
        id: config.id,
        data: config.data || [],
        cols: config.cols || [],
        freeze: config.freeze || {left: 0, right: 0},
        
        init() {
            // 关键：依赖 Alpine 自动初始化
            injectFreezeStyles();
            this.loadDataFromConfig();
            
            this.$nextTick(() => {
                this.render();  // 渲染表格 + 应用冻结样式
            });
        },
        
        render() {
            // 生成表格 HTML
            // ...
            
            // 冻结功能核心
            if (this.freeze.left > 0 || this.freeze.right > 0) {
                this.$nextTick(() => {
                    this.applyFreezeStyles();  // 设置 CSS sticky + ResizeObserver
                });
            }
        }
    };
};
```

**冻结功能工作原理**：
1. **CSS sticky 定位**：`position: sticky` + `left/right` 偏移
2. **z-index 层级**：表头 100，冻结列 50，滚动区域 10
3. **ResizeObserver**：监听表格宽度变化，动态更新 CSS 变量
4. **依赖组件实例**：必须在 Alpine 初始化时创建组件实例

### 7.3 样式规范（Notion 风格）

```css
.notebook-container {
    max-width: 900px;
    margin: 0 auto;
    padding: 20px;
}

.section {
    margin: 12px 0;
    background: #fff;
    border: 1px solid #e9e9e9;
    border-radius: 6px;
}

.nested-section {
    border-left: 4px solid #9b51e0;
    background: #faf9f7;
}

.nested-section .nested-section {
    border-left-color: #ff9500;
    background: #fffdf7;
}

/* 冻结列关键样式 */
.alpine-table-freeze {
    overflow-x: auto;
    position: relative;
}

.alpine-table-freeze .freeze-col {
    position: sticky;
    background: inherit;
}

.alpine-table-freeze thead th {
    position: sticky;
    top: 0;
    z-index: 10;
}
```

---

## 8. 导出流程

```python
def export_html(self, filename):
    # 1. 构建完整数据
    data = {
        'title': self.title,
        'createdAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'cells': self.cells
    }
    
    # 2. 渲染 Jinja2 模板
    html = self._render_template(data)
    
    # 3. 写入文件
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
```

---

## 附录：版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| V1 | 2025-02 | 基础 Notebook 系统，pyecharts 集成 |
| V2 | 2025-02-19 | Section 模块化布局，Notion 风格，上下文管理器 |
| V3 | 2025-02-27 | **API 极简化**：统一 `chart()`、`table()`，移除 `add_` 前缀 |
| V3.5 | 2026-03-02 | **架构稳定化**：回归 Alpine 声明式模板，接受代码重复 |

### V3.5 核心决策

**问题驱动**：
- V4 尝试 JS 递归生成 HTML + Alpine.initTree() 激活
- 表格冻结功能失效（Alpine 初始化时机问题）
- 动态添加 x-data 后组件无法正常初始化

**解决方案**：
- 回归 Alpine.js 声明式模板
- 手动复制三级嵌套 Section 代码（代码重复但功能稳定）
- 冻结、分页、排序等功能正常工作

**技术要点**：
1. 表格使用 `x-data="table({...})"` 直接声明
2. 图表使用 JS 手动初始化（echarts.init）
3. Section 三级嵌套用模板复制（Alpine 不支持递归组件）
4. **稳定优先**：功能正确 > 代码简洁
