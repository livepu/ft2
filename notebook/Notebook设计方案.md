# Notebook 可视化设计方案 V4.2

> 制定时间：2025-02-27
> 修订时间：2026-03-04
> 目标：构建统一、规范、简洁的可视化系统
> 技术方案：Section 模块化布局 + pyecharts 图表 + Notion 风格样式
> **渲染架构：Vue3 组合式 API + Jinja2 模板**
> **JSON 规范：content/children 分离，语义清晰**

---

## 1. 最终展示效果

### 1.1 页面层级结构

```
┌─────────────────────────────────────────────────────────────┐
│  Header: 报告标题 + 创建时间                                  │
├─────────────────────────────────────────────────────────────┤
│  Section (收益分析)                                          │
│  ├── Metrics (核心指标)                                      │
│  │   └── 指标卡片网格: 总收益 / 夏普比率 / 最大回撤 / ...     │
│  └── Chart (净值曲线)                                        │
│      └── ECharts 折线图                                      │
├─────────────────────────────────────────────────────────────┤
│  Section (持仓明细)                                          │
│  └── Table (股票列表)                                        │
│      └── 冻结列 + 分页 + 排序                                │
├─────────────────────────────────────────────────────────────┤
│  Section (月度统计)                    ← 嵌套 Section        │
│  ├── Chart (月度收益柱状图)                                  │
│  └── Heatmap (月度热力图)                                    │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 视觉效果

```
┌──────────────────────────────────────────────────────────────┐
│                     策略回测报告                              │
│                    2026-03-03 10:30                          │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 收益分析                                    [Section]  │  │
│  │ ┌──────────────────────────────────────────────────┐  │  │
│  │ │ 核心指标                                         │  │  │
│  │ │ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │  │  │
│  │ │ │ 45.6%  │ │  1.85  │ │ -12.3% │ │  156   │    │  │  │
│  │ │ │ 总收益 │ │夏普比率│ │最大回撤│ │交易次数│    │  │  │
│  │ │ └────────┘ └────────┘ └────────┘ └────────┘    │  │  │
│  │ └──────────────────────────────────────────────────┘  │  │
│  │ ┌──────────────────────────────────────────────────┐  │  │
│  │ │ 净值曲线                               [Chart]   │  │  │
│  │ │     ╱╲                                           │  │  │
│  │ │    ╱  ╲    ╱╲                                    │  │  │
│  │ │   ╱    ╲  ╱  ╲      ← ECharts 折线图            │  │  │
│  │ │  ╱      ╲╱    ╲                                  │  │  │
│  │ └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 持仓明细                                    [Section]  │  │
│  │ ┌──────────────────────────────────────────────────┐  │  │
│  │ │ 股票列表                               [Table]    │  │  │
│  │ │ ├────────┬────────┬────────┬────────┬────────┤  │  │  │
│  │ │ │ 代码   │ 名称   │ 持仓   │ 成本   │ 收益   │  │  │  │
│  │ │ ├────────┼────────┼────────┼────────┼────────┤  │  │  │
│  │ │ │ 000001 │ 平安   │ 1000   │ 10.5   │ +5.2%  │  │  │  │
│  │ │ │ ...    │ ...    │ ...    │ ...    │ ...    │  │  │  │
│  │ │ └────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 Cell 类型一览

| 类型 | 效果 | 用途 |
|------|------|------|
| **Section** | 卡片容器 + 标题（可折叠） | 模块化分组 |
| **Metrics** | 指标卡片网格 | 核心数据展示 |
| **Table** | 数据表格 | 明细数据，支持冻结/分页 |
| **Chart** | ECharts 图表 | 折线/柱状/饼图 |
| **Heatmap** | 热力图 | 月度收益矩阵 |
| **Title/Text** | 标题/文本 | 说明内容 |

---

## 2. Python 数据层

### 2.1 数据流

```
用户 API 调用
      ↓
Notebook 实例
      ↓
Cell[] (Python 对象)
      ↓
to_dict() 序列化
      ↓
JSON 数据
      ↓
Jinja2 注入 HTML
```

### 2.2 核心类设计

#### Cell 数据类

```python
@dataclass
class Cell:
    type: CellType            # 类型枚举
    content: Any              # 核心数据（原子类型）
    children: List[Cell]      # 子节点（容器类型）
    title: Optional[str]      # 标题
    options: Dict             # 配置选项
```

#### 字段语义

| 字段 | 含义 | 适用类型 |
|------|------|----------|
| `type` | 类型标识 | 所有 |
| `content` | 核心数据 | 原子类型（table, chart, metrics 等） |
| `children` | 子节点列表 | 容器类型（section） |
| `title` | 标题 | 所有（可选） |
| `options` | 展示配置 | 所有（可选） |

#### options 字段说明

| 字段 | 适用类型 | 含义 |
|------|----------|------|
| `level` | section | 层级（1, 2, 3...） |
| `collapsed` | section | 折叠状态（`true`=折叠，`false`=展开，省略=不可折叠） |
| `columns` | table, metrics | 列配置 |
| `freeze` | table | 冻结列配置 |
| `page` | table | 分页配置 |
| `height` | chart, heatmap, pyecharts | 图表高度 |

#### 类型划分

```
原子类型（有 content，无 children）
├── text, markdown, html
├── code
├── table, metrics
├── chart, heatmap, pyecharts
└── divider

容器类型（有 children，无 content）
└── section
```

#### CellType 枚举

```python
class CellType(Enum):
    # 原子类型
    TITLE = "title"           # 标题
    TEXT = "text"             # 纯文本
    MARKDOWN = "markdown"     # Markdown
    CODE = "code"             # 代码块
    TABLE = "table"           # 数据表格
    METRICS = "metrics"       # 指标卡片
    CHART = "chart"           # ECharts 图表
    HEATMAP = "heatmap"       # 热力图
    PYECHARTS = "pyecharts"   # pyecharts 图表
    DIVIDER = "divider"       # 分隔线
    HTML = "html"             # 原始 HTML
    
    # 容器类型
    SECTION = "section"       # 章节容器

# 容器类型标记
CONTAINER_TYPES = {CellType.SECTION}
```

### 2.3 Notebook API

#### 基础用法

```python
from notebook import Notebook

nb = Notebook("策略回测报告")

# 链式调用
nb.title("回测结果", level=1) \
  .text("本报告展示策略表现...") \
  .metrics([
      {'name': '总收益', 'value': '45.6%'},
      {'name': '夏普比率', 'value': '1.85'}
  ], title="核心指标")

nb.export_html("report.html")
```

#### Section 用法

```python
# 方式1: with 上下文管理器
with nb.section("收益分析"):
    nb.metrics([...], title="核心指标")
    nb.chart('line', data, title="净值曲线")
    
    with nb.section("月度统计"):  # 嵌套
        nb.chart('bar', monthly_data, title="月度收益")

# 方式2: 自动分组（给 title 参数）
nb.table(data, title="基金列表")  # 自动创建 Section

# 方式3: 可折叠 Section
with nb.section("详细数据", collapsed=True):
    nb.table(data)
```

#### Jupyter 风格书写习惯

Notebook 采用类似 Jupyter 的增量构建模式，代码执行顺序即报告生成顺序：

**核心思想：**
- `nb` 是增量构建的容器，所有 API 调用都在往 `children` 追加内容
- `with` 语句表达代码模块的层次结构，缩进直观对应报告层级
- 最后统一 `export_html()` 生成完整报告

```python
nb = Notebook("策略分析")

# 数据处理模块
with nb.section("数据概览"):
    nb.metrics([{'name': '样本数', 'value': 1000}])
    nb.table(df)

# 模型训练模块
with nb.section("模型训练"):
    nb.metrics([{'name': '准确率', 'value': '85%'}])
    
    with nb.section("交叉检验"):  # 嵌套层级
        nb.heatmap(cv_results)

# 回测结果模块
with nb.section("回测结果"):
    nb.chart('line', {...})
    nb.table(trades, title="交易明细")

# 最后统一输出
nb.export_html("report.html")
```

**优势：**

| 特性 | 说明 |
|------|------|
| 代码即文档 | Python 代码结构 = 报告结构 |
| 层次清晰 | `with` 缩进直观表达嵌套关系 |
| 模块化 | 每个 `with` 块对应一个报告章节 |
| 简洁输出 | 仅需最后调用一次 `export_html()` |

### 2.4 设计决策

#### 决策1: options 字段松散是合理的

不同 Cell 类型有各自专属配置：
- `TableCell.options.columns` = 列名列表
- `MetricsCell.options.columns` = 每行显示列数

同名不同义，符合各自业务语义。统一反而增加复杂度。

#### 决策2: Section 自动分类

`_add_cell` 方法三种分支：

| 场景 | 代码 | 效果 |
|------|------|------|
| with 内 | `with nb.section("分析"): nb.table(data, title="明细")` | 添加到 Section，title 保留为小标题 |
| with 外有 title | `nb.table(data, title="基金列表")` | **自动创建 Section** |
| with 外无 title | `nb.text("说明文字")` | 普通 Cell，不包装 |

**核心思想**：用户不用显式创建 Section，给 `title` 参数就自动分组。

### 2.5 JSON 输出格式

#### 结构概览

```
顶层结构
├── title: 报告标题
├── createdAt: 创建时间
└── children: Cell[] 列表

原子类型 Cell（有 content，无 children）
├── type: 类型标识
├── content: 核心数据
├── title?: 可选标题
└── options?: 可选配置

容器类型 Section（有 children，无 content）
├── type: "section"
├── children: 子节点列表
├── title?: 可选标题
└── options?: {level, collapsed}
```

#### 格式规范

```json
{
  "type": "<类型>",
  "content": "<核心数据>",      // 原子类型
  "children": [...],           // 容器类型
  "title": "<可选标题>",
  "options": {<可选配置>}
}
```

#### 设计原则

| 原则 | 说明 |
|------|------|
| **语义分离** | `content` = 数据，`children` = 子节点，职责分明 |
| **类型区分** | Vue3 通过 `type` 判断原子/容器，递归渲染简单直观 |
| **字段省略** | `title`/`options` 为空时省略，减少 JSON 体积 |

#### 完整示例

```json
{
  "title": "策略回测报告",
  "createdAt": "2026-03-03 10:30:00",
  "children": [
    {
      "type": "section",
      "title": "收益分析",
      "children": [
        {
          "type": "metrics",
          "title": "核心指标",
          "content": [
            {"name": "总收益", "value": "45.6%", "desc": "累计"},
            {"name": "夏普比率", "value": "1.85", "desc": "风险调整后"}
          ],
          "options": {"columns": 4}
        },
        {
          "type": "chart",
          "title": "净值曲线",
          "content": {
            "chart_type": "line",
            "data": {"x": [...], "series": [...]}
          },
          "options": {"height": 400}
        }
      ],
      "options": {"level": 1}
    }
  ]
}
```

#### 嵌套示例

```json
{
  "type": "section",
  "title": "收益分析",
  "children": [
    {
      "type": "metrics",
      "content": [...]
    },
    {
      "type": "section",
      "title": "月度统计",
      "children": [
        {"type": "chart", "content": {...}}
      ],
      "options": {"level": 2}
    }
  ],
  "options": {"level": 1}
}
```

#### 折叠示例

```json
{
  "type": "section",
  "title": "详细数据",
  "children": [
    {"type": "table", "content": [...]}
  ],
  "options": {"level": 1, "collapsed": true}
}
```

#### 字段省略规则

| 条件 | 处理 |
|------|------|
| `title` 为 `None` | 省略该字段 |
| `options` 为空对象 `{}` | 省略该字段 |
| `options.collapsed` 省略 | 不可折叠（默认行为） |
| `content` 为 `None`（如 divider） | 保留 `"content": null` |
| `children` 为空列表 | 保留 `"children": []` |

---

## 3. Vue3 渲染层

### 3.1 渲染流程

```
Jinja2 模板
    ↓ (注入 JSON 到 window.notebookConfig)
HTML 页面
    ↓ (Vue3 createApp)
CellRenderer 组件
    ↓ (递归渲染)
最终页面
```

### 3.2 模板结构 (notebook.html)

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <!-- 依赖: Vue3, ECharts, 表格组件 -->
</head>
<body>
    <div id="app">
        <!-- Header -->
        <div class="notebook-header">
            <h1>{{ title }}</h1>
            <span>📅 {{ createdAt }}</span>
        </div>
        
        <!-- Cell 列表 -->
        <cell-renderer 
            v-for="(cell, index) in children" 
            :key="index"
            :cell="cell"
            :cell-id="index"
            :level="0">
        </cell-renderer>
    </div>
    
    <!-- 数据注入 -->
    <script id="notebook-data" type="application/json">
        {{ data_json | safe }}
    </script>
    
    <!-- Vue3 应用 -->
    <script src="notebook-vue3.js"></script>
    <script>
        window.notebookConfig = JSON.parse(
            document.getElementById('notebook-data').textContent
        );
        createNotebookApp().mount('#app');
    </script>
</body>
</html>
```

### 3.3 CellRenderer 组件

```javascript
const CellRenderer = {
    name: 'CellRenderer',
    props: {
        cell: { type: Object, required: true },
        cellId: { type: [String, Number], required: true },
        level: { type: Number, default: 0 }
    },
    template: `
        <!-- Section: 递归渲染 children -->
        <div v-if="cell.type === 'section'" class="section">
            <!-- 可折叠 -->
            <details v-if="cell.options?.collapsed !== undefined" 
                     :open="!cell.options.collapsed">
                <summary class="section-title">{{ cell.title }}</summary>
                <div class="section-content">
                    <cell-renderer 
                        v-for="(subCell, idx) in cell.children" 
                        :key="idx"
                        :cell="subCell"
                        :cell-id="cellId + '-' + idx"
                        :level="level + 1">
                    </cell-renderer>
                </div>
            </details>
            
            <!-- 不可折叠 -->
            <template v-else>
                <div class="section-title">{{ cell.title }}</div>
                <div class="section-content">
                    <cell-renderer 
                        v-for="(subCell, idx) in cell.children" 
                        :key="idx"
                        :cell="subCell"
                        :cell-id="cellId + '-' + idx"
                        :level="level + 1">
                    </cell-renderer>
                </div>
            </template>
        </div>
        
        <!-- Table: 渲染 content -->
        <div v-else-if="cell.type === 'table'" class="cell-table">
            <h3 v-if="cell.title">{{ cell.title }}</h3>
            <vue-table :data-source="cell.content" ...></vue-table>
        </div>
        
        <!-- Metrics: 渲染 content -->
        <div v-else-if="cell.type === 'metrics'" class="cell-metrics">
            <h3 v-if="cell.title">{{ cell.title }}</h3>
            <div class="metrics-grid">
                <div v-for="m in cell.content" class="metric-card">
                    <div class="metric-value">{{ m.value }}</div>
                    <div class="metric-label">{{ m.name }}</div>
                </div>
            </div>
        </div>
        
        <!-- Chart/Heatmap/Pyecharts: 渲染 content -->
        <div v-else-if="['chart','heatmap','pyecharts'].includes(cell.type)" 
             class="cell-chart">
            <h3 v-if="cell.title">{{ cell.title }}</h3>
            <div ref="chartRef" class="chart-container"></div>
        </div>
        
        <!-- 其他类型... -->
    `
};
```

#### 渲染规则

| 类型 | 数据字段 | 渲染方式 |
|------|----------|----------|
| `section` | `children` | 递归渲染子节点 |
| `section` (折叠) | `options.collapsed` | `<details>` 标签 |
| `table` | `content` | 渲染表格数据 |
| `metrics` | `content` | 渲染指标卡片 |
| `chart` | `content` | 渲染图表配置 |

### 3.4 图表初始化

```javascript
setup(props) {
    const chartRef = ref(null);
    let chartInstance = null;
    
    onMounted(() => {
        if (['chart', 'heatmap', 'pyecharts'].includes(props.cell.type)) {
            nextTick(() => {
                chartInstance = echarts.init(chartRef.value);
                const option = buildChartOption(props.cell);
                chartInstance.setOption(option);
            });
        }
    });
    
    return { chartRef };
}
```

### 3.5 样式规范 (Notion 风格)

```css
/* Section 卡片 */
.section {
    margin: 12px 0;
    background: #fff;
    border: 1px solid #e9e9e9;
    border-radius: 6px;
}

.section-title {
    padding: 12px 16px;
    font-size: 16px;
    font-weight: 600;
    border-bottom: 1px solid #e9e9e9;
}

/* 嵌套 Section */
.nested-section {
    border-left: 4px solid #9b51e0;
    background: #faf9f7;
}

/* 指标卡片 */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(var(--columns, 4), 1fr);
    gap: 16px;
    padding: 16px;
}

.metric-card {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
}

.metric-value {
    font-size: 24px;
    font-weight: 600;
    color: #333;
}

.metric-value.positive { color: #52c41a; }
.metric-value.negative { color: #ff4d4f; }
```

---

## 4. 完整示例

### 4.1 Python 代码

```python
from notebook import Notebook

nb = Notebook("策略回测报告")

# Section 1: 收益分析
with nb.section("收益分析"):
    nb.metrics([
        {'name': '总收益', 'value': '45.6%', 'desc': '累计'},
        {'name': '夏普比率', 'value': '1.85', 'desc': '风险调整后'},
        {'name': '最大回撤', 'value': '-12.3%', 'desc': '历史最大'},
        {'name': '交易次数', 'value': '156', 'desc': '总交易'}
    ], title="核心指标")
    
    nb.chart('line', {
        'dates': ['2024-01', '2024-02', ...],
        'series': [
            {'name': '策略', 'data': [1.0, 1.05, 1.08, ...]},
            {'name': '基准', 'data': [1.0, 1.02, 1.04, ...]}
        ]
    }, title="净值曲线")

# Section 2: 持仓明细
nb.table(
    data=[
        {'code': '000001', 'name': '平安银行', 'shares': 1000, 'profit': '+5.2%'},
        {'code': '600519', 'name': '贵州茅台', 'shares': 100, 'profit': '+12.8%'},
    ],
    columns=['code', 'name', 'shares', 'profit'],
    title="持仓明细",
    freeze=2  # 冻结前2列
)

# 导出
nb.export_html("report.html")
```

### 4.2 生成的 JSON

```json
{
  "title": "策略回测报告",
  "createdAt": "2026-03-03 10:30:00",
  "children": [
    {
      "type": "section",
      "title": "收益分析",
      "children": [
        {
          "type": "metrics",
          "title": "核心指标",
          "content": [
            {"name": "总收益", "value": "45.6%", "desc": "累计"},
            {"name": "夏普比率", "value": "1.85", "desc": "风险调整后"},
            {"name": "最大回撤", "value": "-12.3%", "desc": "历史最大"},
            {"name": "交易次数", "value": "156", "desc": "总交易"}
          ],
          "options": {"columns": 4}
        },
        {
          "type": "chart",
          "title": "净值曲线",
          "content": {
            "chart_type": "line",
            "data": {
              "x": ["2024-01", "2024-02"],
              "series": [
                {"name": "策略", "data": [1.0, 1.05]},
                {"name": "基准", "data": [1.0, 1.02]}
              ]
            }
          },
          "options": {"height": 400}
        }
      ],
      "options": {"level": 1}
    },
    {
      "type": "section",
      "title": "持仓明细",
      "children": [
        {
          "type": "table",
          "content": [
            {"code": "000001", "name": "平安银行", "shares": 1000, "profit": "+5.2%"},
            {"code": "600519", "name": "贵州茅台", "shares": 100, "profit": "+12.8%"}
          ],
          "options": {
            "columns": ["code", "name", "shares", "profit"],
            "freeze": {"left": 2, "right": 0}
          }
        }
      ],
      "options": {"level": 1}
    }
  ]
}
```

---

## 5. 文件结构

```
ft2/
├── notebook/
│   ├── __init__.py
│   ├── notebook.py      # Notebook 主类
│   └── cell.py          # Cell + CellBuilder
│
└── template/
    ├── notebook.html        # Jinja2 + Vue3 模板
    └── js/
        ├── notebook-vue3.js # Vue3 组件
        ├── vue.global.prod.js
        ├── echarts.min.js
        └── vue3-table.js    # 表格组件
```

---

## 附录A：图表数据格式对比

### 设计原则

Notebook 的数据格式设计遵循以下原则：
1. **贴近 ECharts**：使用 ECharts 原生键名（如 `xAxis`），降低学习成本
2. **简化用户输入**：相比 ECharts 原生格式更简洁，省略冗余配置
3. **兼容 pyecharts**：命名风格与 pyecharts 相似，便于迁移

### A.1 折线图 / 面积图 / 柱状图

**pyecharts:**
```python
Line() \
    .add_xaxis(['1月', '2月', '3月']) \
    .add_yaxis('策略', [1.0, 1.05, 1.12]) \
    .add_yaxis('基准', [1.0, 1.02, 1.08])
```

**ECharts JS:**
```javascript
{
    xAxis: { type: 'category', data: ['1月', '2月', '3月'] },
    yAxis: { type: 'value' },
    series: [
        { name: '策略', type: 'line', data: [1.0, 1.05, 1.12] },
        { name: '基准', type: 'line', data: [1.0, 1.02, 1.08] }
    ]
}
```

**Notebook:**
```python
nb.chart('line', {
    'xAxis': ['1月', '2月', '3月'],
    'series': [
        {'name': '策略', 'data': [1.0, 1.05, 1.12]},
        {'name': '基准', 'data': [1.0, 1.02, 1.08]}
    ]
})
```

| 对比项 | pyecharts | ECharts | Notebook |
|--------|-----------|---------|----------|
| X轴数据 | `add_xaxis([...])` | `xAxis.data` | `xAxis` (直接赋值) |
| 系列数据 | `add_yaxis(name, data)` | `series[].data` | `series[].data` |
| 简化程度 | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ |

---

### A.2 饼图

**pyecharts:**
```python
Pie().add('', [('股票', 60), ('债券', 30), ('现金', 10)])
```

**ECharts JS:**
```javascript
{
    series: [{
        type: 'pie',
        data: [
            { name: '股票', value: 60 },
            { name: '债券', value: 30 },
            { name: '现金', value: 10 }
        ]
    }]
}
```

**Notebook:**
```python
nb.chart('pie', [
    {'name': '股票', 'value': 60},
    {'name': '债券', 'value': 30},
    {'name': '现金', 'value': 10}
])
```

| 对比项 | pyecharts | ECharts | Notebook |
|--------|-----------|---------|----------|
| 数据结构 | 元组列表 `[(name, value)]` | 对象数组 | 对象数组 |
| 键名 | 隐式 | `name`, `value` | `name`, `value` |
| 简化程度 | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |

---

### A.3 热力图

#### 输入参数格式

```python
def heatmap(data, title=None, **options) -> Notebook:
    """
    创建热力图
    
    Args:
        data: 数据源，支持格式：
            - dict: 嵌套字典 {y: {x: value, ...}, ...}
            - DataFrame: 第一列作为Y轴，其余列作为X轴
        title: 标题
        **options: 其他配置（如 height）
    
    Returns:
        Notebook: 支持链式调用
    """
```

#### 数据格式说明

嵌套字典与 DataFrame 宽格式结构等价，可互转：

**例1：年月收益**
```python
# dict 嵌套格式（外层 key = Y轴，内层 key = X轴）
{
    '2023': {'1月': 0.02, '2月': -0.01, '3月': 0.03},
    '2024': {'1月': 0.05, '2月': -0.02, '3月': 0.08}
}

# DataFrame 格式（第一列 = Y轴，其余列 = X轴）
#     年    1月    2月    3月
# 0  2023  0.02  -0.01  0.03
# 1  2024  0.05  -0.02  0.08
```

**例2：相关性矩阵**
```python
# dict 嵌套格式
{
    '茅台': {'茅台': 1.00, '平安': 0.35, '万科': 0.28},
    '平安': {'茅台': 0.35, '平安': 1.00, '万科': 0.52},
    '万科': {'茅台': 0.28, '平安': 0.52, '万科': 1.00}
}

# DataFrame 格式（索引已设置）
#        茅台   平安   万科
# 茅台  1.00  0.35  0.28
# 平安  0.35  1.00  0.52
# 万科  0.28  0.52  1.00
```

**例3：交叉检验（模型对比）**
```python
# dict 嵌套格式：不同模型在各折上的准确率
{
    'RandomForest': {'Fold1': 0.85, 'Fold2': 0.87, 'Fold3': 0.84, 'Fold4': 0.86, 'Fold5': 0.88},
    'XGBoost':      {'Fold1': 0.88, 'Fold2': 0.86, 'Fold3': 0.89, 'Fold4': 0.87, 'Fold5': 0.90},
    'LightGBM':     {'Fold1': 0.87, 'Fold2': 0.89, 'Fold3': 0.86, 'Fold4': 0.88, 'Fold5': 0.91},
    'NeuralNet':    {'Fold1': 0.82, 'Fold2': 0.84, 'Fold3': 0.83, 'Fold4': 0.85, 'Fold5': 0.86}
}

# DataFrame 格式
#          Model   Fold1  Fold2  Fold3  Fold4  Fold5
# 0  RandomForest   0.85   0.87   0.84   0.86   0.88
# 1       XGBoost   0.88   0.86   0.89   0.87   0.90
# 2      LightGBM   0.87   0.89   0.86   0.88   0.91
# 3     NeuralNet   0.82   0.84   0.83   0.85   0.86

# 调用示例
cv_results = pd.DataFrame({
    'Model': ['RandomForest', 'XGBoost', 'LightGBM', 'NeuralNet'],
    'Fold1': [0.85, 0.88, 0.87, 0.82],
    'Fold2': [0.87, 0.86, 0.89, 0.84],
    'Fold3': [0.84, 0.89, 0.86, 0.83],
    'Fold4': [0.86, 0.87, 0.88, 0.85],
    'Fold5': [0.88, 0.90, 0.91, 0.86]
})
nb.heatmap(cv_results, title='5折交叉检验准确率对比')
```

#### DataFrame 转换规则

| DataFrame 索引类型 | 处理方式 |
|-------------------|----------|
| `RangeIndex`（默认 0,1,2...） | 自动 `set_index(第一列)` → Y轴 |
| 已命名索引（如年/股票名） | 直接使用 → Y轴 |

```python
# 情况1：默认索引 → 自动转换
df = pd.DataFrame({'年': ['2023', '2024'], '1月': [0.02, 0.05]})
# RangeIndex(0, 2) → set_index('年') → {'2023': {'1月': 0.02}, ...}

# 情况2：已设置索引 → 直接使用
df = pd.DataFrame({'1月': [0.02, 0.05]}, index=['2023', '2024'])
# Index(['2023', '2024']) → {'2023': {'1月': 0.02}, ...}
```

#### 格式互转

```python
# dict → DataFrame
pd.DataFrame.from_dict(data, orient='index')

# DataFrame → dict
df.to_dict(orient='index')
```

#### 调用示例

```python
# 方式1：嵌套字典
nb.heatmap({
    '2023': {'1月': 0.02, '2月': -0.01, '3月': 0.03},
    '2024': {'1月': 0.05, '2月': -0.02, '3月': 0.08}
}, title='月度收益热力图')

# 方式2：DataFrame
df = pd.DataFrame({
    '年': ['2023', '2024'],
    '1月': [0.02, 0.05],
    '2月': [-0.01, -0.02],
    '3月': [0.03, 0.08]
})
nb.heatmap(df, title='月度收益热力图')

# 方式3：通过 chart 方法
nb.chart('heatmap', data, title='热力图', height=500)
```

---

#### 与其他方案对比

**pyecharts:** (与 ECharts 相同，需手动计算坐标索引)
```python
HeatMap() \
    .add_xaxis(['1月', '2月', '3月']) \
    .add_yaxis('收益率', [
        [0, 0, 0.05],   # [x索引, y索引, 值]
        [1, 0, 0.03],
        [2, 0, 0.08]
    ])
```

**ECharts JS:**
```javascript
{
    xAxis: { type: 'category', data: ['1月', '2月', '3月'] },
    yAxis: { type: 'category', data: ['2023', '2024'] },
    series: [{
        type: 'heatmap',
        data: [[0,0,0.05], [1,0,0.03], [2,0,0.08]]  // [x索引, y索引, 值]
    }]
}
```

**Notebook:** (语义化嵌套字典，自动转换坐标)
```python
# 方式1: 嵌套字典
nb.heatmap({
    '2023': {'1月': 0.05, '2月': 0.03, '3月': 0.08},
    '2024': {'1月': 0.10, '2月': -0.02, '3月': 0.06}
})

# 方式2: DataFrame（自动转换）
df = pd.DataFrame({
    '月份': ['1月', '2月', '3月'],
    '2023': [0.05, 0.03, 0.08],
    '2024': [0.10, -0.02, 0.06]
})
nb.heatmap(df)  # 第一列自动作为Y轴索引
```

| 对比项 | pyecharts | ECharts | Notebook |
|--------|-----------|---------|----------|
| 数据格式 | 坐标索引 `[x, y, v]` | 坐标索引 | 嵌套字典 `{y: {x: v}}` |
| DataFrame支持 | ❌ | ❌ | ✅ 自动转换 |
| 用户负担 | 需计算索引 | 需计算索引 | **直接语义化** ✅ |
| 简化程度 | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |

---

### A.4 表格数据格式

Notebook 的 `table()` 方法支持两种数据格式：

**方式1: List[dict]（字典列表）**
```python
nb.table([
    {'code': '000001', 'name': '平安银行', 'shares': 1000, 'profit': '+5.2%'},
    {'code': '600519', 'name': '贵州茅台', 'shares': 100, 'profit': '+12.8%'},
])
```

**方式2: DataFrame（自动转换）**
```python
df = pd.DataFrame({
    'code': ['000001', '600519'],
    'name': ['平安银行', '贵州茅台'],
    'shares': [1000, 100],
    'profit': ['+5.2%', '+12.8%']
})
nb.table(df)  # 自动识别列名
```

**格式对比：**

| 对比项 | List[dict] | DataFrame |
|--------|------------|-----------|
| 数据来源 | API返回、手动构造 | pandas处理结果 |
| 列顺序 | 不保证（字典无序） | 按 DataFrame 列顺序 |
| columns参数 | 可指定列及顺序 | 同左，或 None 使用全部列 |
| 适用场景 | 简单数据、JSON转换 | 数据分析结果展示 |

**columns 参数示例：**
```python
# 指定列及顺序
nb.table(df, columns=['name', 'code', 'profit'])

# 不指定，使用全部列
nb.table(df)
```

---

### A.5 总结对比表

| 图表类型 | pyecharts 风格 | ECharts 键名 | Notebook 简化 |
|---------|---------------|-------------|--------------|
| line/area/bar | `add_xaxis()` / `add_yaxis()` | `xAxis.data` / `series[].data` | `xAxis` + `series` |
| pie | 元组列表 | `{name, value}` 对象 | 同 ECharts |
| heatmap | 坐标索引 | 坐标索引 | **嵌套字典** (更语义化) |

**设计理念**：Notebook 在保持 ECharts 键名习惯的同时，尽可能简化用户输入。热力图采用嵌套字典格式，无需用户手动计算坐标索引，是最大的简化点。

---

## 6. 选择性截图功能

### 6.1 功能需求

用户可以在 TOC 面板中勾选需要截图的内容（支持多选），点击"截图选中"按钮后，将选中内容截图并复制到剪贴板。

### 6.2 技术挑战

| 挑战 | 说明 |
|------|------|
| **Vue3 响应式** | `:class` 绑定变化触发虚拟 DOM 更新，可能导致图表重新渲染 |
| **Canvas 克隆** | `cloneNode()` 无法克隆 Canvas 内容，ECharts 图表会丢失 |
| **布局变化** | 使用 `display: none` 隐藏元素会触发重排，影响图表尺寸 |

### 6.3 最终方案：独立截图容器 + Canvas 手动复制

#### 架构设计

```
┌─────────────────────────────────────┐
│  主体容器 (.notebook-container)      │  ← 用户交互，完全不动
│  ├── Header                         │
│  └── Section[]                      │
└─────────────────────────────────────┘
                    ↓ cloneNode(true)
┌─────────────────────────────────────┐
│  截图容器 (#screenshot-container)    │  ← 隐藏在视口外
│  position: absolute;                │
│  left: -99999px;                    │
│  width: 900px;                      │
└─────────────────────────────────────┘
                    ↓ ctx.drawImage()
                 Canvas 内容复制
                    ↓ snapdom()
                 截图输出
```

#### 核心代码

```javascript
// 截图功能 - 克隆DOM到专用容器，手动处理Canvas
const captureScreenshot = async () => {
    const mainContainer = document.querySelector('.notebook-container');
    const screenshotContainer = document.getElementById('screenshot-container');

    // 1. 清空截图容器
    screenshotContainer.innerHTML = '';

    // 2. 收集原始canvas和克隆canvas的对应关系
    const canvasPairs = [];

    // 辅助函数：克隆元素并记录canvas
    const cloneWithCanvas = (original) => {
        const cloned = original.cloneNode(true);
        const originalCanvases = original.querySelectorAll('canvas');
        const clonedCanvases = cloned.querySelectorAll('canvas');

        originalCanvases.forEach((origCanvas, i) => {
            const clonedCanvas = clonedCanvases[i];
            if (clonedCanvas && origCanvas.width > 0) {
                canvasPairs.push({ original: origCanvas, cloned: clonedCanvas });
            }
        });
        return cloned;
    };

    // 3. 克隆选中的内容（头部 + sections）
    if (selectedIndices.has(-1)) {
        screenshotContainer.appendChild(cloneWithCanvas(header));
    }
    selectedIndices.forEach(index => {
        const section = document.getElementById('section-' + index);
        if (section) {
            screenshotContainer.appendChild(cloneWithCanvas(section));
        }
    });

    // 4. 复制Canvas内容（关键步骤！）
    canvasPairs.forEach(({ original, cloned }) => {
        const ctx = cloned.getContext('2d');
        cloned.width = original.width;
        cloned.height = original.height;
        ctx.drawImage(original, 0, 0);  // 核心：复制位图数据
    });

    // 5. 截图
    const result = await snapdom(screenshotContainer, {
        scale: 2,
        backgroundColor: '#f5f5f5',
        cache: 'auto'
    });

    // 6. 复制到剪贴板
    const blob = await result.toBlob({ type: 'png' });
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);

    // 7. 清空截图容器
    screenshotContainer.innerHTML = '';
};
```

#### HTML 结构

```html
<!-- 主体容器 -->
<div class="notebook-container">
    <div class="notebook-header">...</div>
    <cell-renderer v-for="..." />
</div>

<!-- 截图专用容器（隐藏在视口外） -->
<div id="screenshot-container"
     class="notebook-container"
     style="position: absolute; left: -99999px; top: 0; width: 900px;">
</div>
```

### 6.4 方案对比

| 方案 | 原理 | 问题 |
|------|------|------|
| ❌ CSS `display: none` | 隐藏未选中元素 | 触发重排，图表尺寸变化 |
| ❌ CSS `visibility: hidden` | 隐藏但保留空间 | 占用空白，截图有空白 |
| ❌ Vue `:class` 绑定 | 响应式更新 class | Vue 虚拟 DOM 更新可能影响图表 |
| ✅ **独立截图容器** | 克隆选中内容到新容器 | 主体不动，图表完整，无空白 |

### 6.5 关键技术点

1. **Canvas 克隆问题**
   - `cloneNode(true)` 只克隆 DOM 结构
   - Canvas 的绑定数据（如 ECharts 实例）不会复制
   - 必须用 `ctx.drawImage()` 手动复制位图

2. **截图容器定位**
   - `position: absolute; left: -99999px` 移出视口
   - 必须设置固定宽度 `width: 900px` 保证样式正确

3. **主体零干扰**
   - 主体 DOM 完全不受影响
   - Vue 组件状态不变
   - 图表实例保持活跃

---

## 附录B：版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| V1 | 2025-02 | 基础 Notebook 系统 |
| V2 | 2025-02-19 | Section 模块化，Notion 风格 |
| V3 | 2025-02-27 | API 极简化，统一 `chart()` |
| V3.5 | 2026-03-02 | Alpine 声明式模板 |
| V4.0 | 2026-03-03 | 重构文档结构：效果 → Python → Vue3 |
| V4.1 | 2026-03-03 | **JSON 规范优化**：`content`/`children` 分离，`collapsed` 作为 section 可选参数 |
| V4.2 | 2026-03-04 | **选择性截图**：独立截图容器 + Canvas 手动复制技术方案 |
