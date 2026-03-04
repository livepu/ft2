# Notebook 可视化设计方案 V5.0

> 制定时间：2025-02-27
> 修订时间：2026-03-05
> 目标：构建统一、规范、简洁的可视化系统
> 技术方案：Section 模块化布局 + ECharts 图表 + Notion 风格样式
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
│  │ │ └────────────────────────────────────────────────┘  │  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 Cell 类型一览

| 类型 | 效果 | 用途 |
|------|------|------|
| **Section** | 卡片容器 + 标题（可折叠） | 模块化分组 |
| **Metrics** | 指标卡片网格 | 核心数据展示 |
| **Table** | 数据表格 | 明细数据，支持冻结/分页 |
| **Chart** | ECharts 图表 | 折线/柱状/饼图/面积图 |
| **Heatmap** | 热力图 | 月度收益矩阵 |
| **Title/Text** | 标题/文本 | 说明内容 |

---

## 2. 用法标准

### 2.1 Python API 基础用法

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

### 2.2 Section 用法

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

### 2.3 ECharts 图表详细规范

#### 2.3.1 折线图 / 面积图 / 柱状图

**函数签名：**
```python
def chart(self, chart_type, data, title=None, **options) -> Notebook:
    """
    创建图表
    
    Args:
        chart_type: 图表类型 - 'line' | 'bar' | 'area' | 'pie'
        data: 图表数据，格式见下文
        title: 图表标题
        **options: 其他配置，如 height, width 等
    
    Returns:
        Notebook: 支持链式调用
    """
```

**数据格式：**
```python
# 标准格式
{
    'xAxis': ['1月', '2月', '3月', '4月', '5月'],  # X轴数据
    'series': [
        {
            'name': '策略',           # 系列名称
            'data': [1.0, 1.05, 1.08, 1.12, 1.15]  # Y轴数据
        },
        {
            'name': '基准',
            'data': [1.0, 1.02, 1.04, 1.05, 1.06]
        }
    ]
}

# 简化格式（单系列）
{
    'xAxis': ['1月', '2月', '3月'],
    'series': {'data': [100, 120, 140]}
}
```

**使用示例：**
```python
# 折线图
nb.chart('line', {
    'xAxis': ['2024-01', '2024-02', '2024-03'],
    'series': [
        {'name': '策略净值', 'data': [1.0, 1.05, 1.12]},
        {'name': '基准净值', 'data': [1.0, 1.02, 1.04]}
    ]
}, title="净值曲线", height=400)

# 柱状图
nb.chart('bar', {
    'xAxis': ['1月', '2月', '3月'],
    'series': [
        {'name': '收益', 'data': [5.2, -2.1, 8.3]}
    ]
}, title="月度收益")

# 面积图
nb.chart('area', {
    'xAxis': ['周一', '周二', '周三', '周四', '周五'],
    'series': [
        {'name': '成交量', 'data': [120, 200, 150, 80, 70]}
    ]
}, title="成交量趋势")
```

**前端交互：**
- 柱状图：正数红色、负数蓝色，自动区分
- 面积图：渐变色填充效果
- 坐标轴：Y轴自动缩放，留有边距

#### 2.3.2 饼图

**数据格式：**
```python
# 对象数组格式
[
    {'name': '股票', 'value': 60},
    {'name': '债券', 'value': 30},
    {'name': '现金', 'value': 10}
]
```

**使用示例：**
```python
nb.chart('pie', [
    {'name': '股票', 'value': 60},
    {'name': '债券', 'value': 30},
    {'name': '现金', 'value': 10}
], title="资产配置")
```

**前端交互：**
- 支持显示原始数据、百分比或同时显示
- 通过右侧控制面板切换
- 环形图样式，标签引导线

#### 2.3.3 热力图

**函数签名：**
```python
def heatmap(self, data, title=None, **options) -> Notebook:
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

**数据格式：**
```python
# 嵌套字典格式（外层 key = Y轴，内层 key = X轴）
{
    '2023': {'1月': 0.02, '2月': -0.01, '3月': 0.03},
    '2024': {'1月': 0.05, '2月': -0.02, '3月': 0.08}
}

# DataFrame 格式（第一列 = Y轴，其余列 = X轴）
#     年    1月    2月    3月
# 0  2023  0.02  -0.01  0.03
# 1  2024  0.05  -0.02  0.08
```

**使用示例：**
```python
# 方式1：嵌套字典
nb.heatmap({
    '2023': {'1月': 0.02, '2月': -0.01, '3月': 0.03},
    '2024': {'1月': 0.05, '2月': -0.02, '3月': 0.08}
}, title='月度收益热力图')

# 方式2：DataFrame
import pandas as pd
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

**前端交互：**
- 支持数据缩放（×1000, ×100, ×10, 原始, 1/10, 1/100）
- 默认显示原始数据
- 根据数据范围自动调整颜色映射（蓝红渐变）

#### 2.3.4 图表参数总结

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `chart_type` | str | ✅ | 'line'/'bar'/'area'/'pie'/'heatmap' |
| `data` | dict/list | ✅ | 图表数据，格式见各类型说明 |
| `title` | str | ❌ | 图表标题 |
| `height` | int | ❌ | 图表高度（像素），默认 400 |
| `width` | int | ❌ | 图表宽度（像素），默认自适应 |

### 2.4 表格详细规范

**函数签名：**
```python
def table(self, data, columns=None, title=None, **options) -> Notebook:
    """
    创建表格
    
    Args:
        data: 表格数据，支持 List[dict] 或 DataFrame
        columns: 列配置，格式：['col1', 'col2'] 或 {'col1': '列名1', 'col2': '列名2'}
        title: 表格标题
        **options: 其他配置
            - freeze: 冻结列配置，如 {'left': 2, 'right': 0}
            - page: 分页配置，如 {'pageSize': 10}
    
    Returns:
        Notebook: 支持链式调用
    """
```

**使用示例：**
```python
# 基础用法
nb.table([
    {'code': '000001', 'name': '平安银行', 'profit': '+5.2%'},
    {'code': '600519', 'name': '贵州茅台', 'profit': '+12.8%'},
], title="持仓明细")

# 指定列及顺序
nb.table(data, columns=['name', 'code', 'profit'])

# 冻结列 + 分页
nb.table(data, 
    columns=['code', 'name', 'shares', 'cost', 'profit'],
    freeze={'left': 2, 'right': 0},
    page={'pageSize': 20},
    title="交易明细"
)
```

### 2.5 指标卡片详细规范

**函数签名：**
```python
def metrics(self, data, columns=4, title=None, **options) -> Notebook:
    """
    创建指标卡片网格
    
    Args:
        data: 指标数据列表，每个元素为 {'name': str, 'value': str, 'desc': str}
        columns: 每行显示列数，默认 4
        title: 标题
        **options: 其他配置
    
    Returns:
        Notebook: 支持链式调用
    """
```

**数据格式：**
```python
[
    {'name': '总收益', 'value': '45.6%', 'desc': '累计'},
    {'name': '夏普比率', 'value': '1.85', 'desc': '风险调整后'},
    {'name': '最大回撤', 'value': '-12.3%', 'desc': '历史最大'},
    {'name': '交易次数', 'value': '156', 'desc': '总交易'}
]
```

**使用示例：**
```python
nb.metrics([
    {'name': '总收益', 'value': '45.6%', 'desc': '累计'},
    {'name': '夏普比率', 'value': '1.85', 'desc': '风险调整后'},
    {'name': '最大回撤', 'value': '-12.3%', 'desc': '历史最大'},
    {'name': '交易次数', 'value': '156', 'desc': '总交易'}
], columns=4, title="核心指标")
```

---

## 3. Vue3 实现逻辑（简要）

### 3.1 数据流

```
Python Notebook
      ↓ to_dict()
JSON 数据
      ↓ Jinja2 注入
HTML 页面 (window.notebookConfig)
      ↓ Vue3 createApp
CellRenderer 组件递归渲染
      ↓
最终页面
```

### 3.2 JSON 规范

**核心原则：** `content`/`children` 分离

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
          "content": [...],
          "options": {"columns": 4}
        },
        {
          "type": "chart",
          "title": "净值曲线",
          "content": {
            "chart_type": "line",
            "data": {"xAxis": [...], "series": [...]}
          },
          "options": {"height": 400}
        }
      ],
      "options": {"level": 1}
    }
  ]
}
```

**字段规则：**
- 原子类型（table/chart/metrics）：有 `content`，无 `children`
- 容器类型（section）：有 `children`，无 `content`
- `title`/`options` 为空时省略

### 3.3 渲染组件

```javascript
// CellRenderer 根据 type 递归渲染
const CellRenderer = {
    props: ['cell', 'cellId', 'level'],
    template: `
        <!-- Section: 递归渲染 children -->
        <div v-if="cell.type === 'section'" class="section">
            <cell-renderer 
                v-for="(subCell, idx) in cell.children" 
                :key="idx"
                :cell="subCell"
                :level="level + 1">
            </cell-renderer>
        </div>
        
        <!-- 原子类型: 渲染 content -->
        <div v-else-if="cell.type === 'chart'" class="cell-chart">
            <div ref="chartRef"></div>
        </div>
        
        <!-- 其他类型... -->
    `
};
```

### 3.4 图表初始化

```javascript
// ECharts 初始化
onMounted(() => {
    if (['chart', 'heatmap'].includes(props.cell.type)) {
        chartInstance = echarts.init(chartRef.value);
        const option = buildChartOption(props.cell);
        chartInstance.setOption(option);
    }
});

// 窗口 resize 自适应
window.addEventListener('resize', () => {
    chartInstance?.resize();
});
```

### 3.5 配色方案

```css
/* Notion 风格大红大紫 */
/* 二级嵌套：紫罗兰 #9b51e0 + 浅紫背景 #faf9f7 */
/* 三级嵌套：粉红 #ec4899 + 浅粉背景 #fdf2f8 */
/* 主按钮：中粉 #ec4899（悬停深粉 #db2777） */
/* 选中高亮：紫罗兰 #9b51e0 */
/* 表格正数：红色 #e64340 */
/* 表格负数：绿色 #00b300 */
```

---

## 附录A：完整示例

### A.1 Python 代码

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
        'xAxis': ['2024-01', '2024-02', '2024-03'],
        'series': [
            {'name': '策略', 'data': [1.0, 1.05, 1.08]},
            {'name': '基准', 'data': [1.0, 1.02, 1.04]}
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
    freeze={'left': 2}
)

# 导出
nb.export_html("report.html")
```

### A.2 生成的 JSON

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
              "xAxis": ["2024-01", "2024-02", "2024-03"],
              "series": [
                {"name": "策略", "data": [1.0, 1.05, 1.08]},
                {"name": "基准", "data": [1.0, 1.02, 1.04]}
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

## 附录B：图表数据格式对比

### 设计原则

Notebook 的数据格式设计遵循以下原则：
1. **贴近 ECharts**：使用 ECharts 原生键名（如 `xAxis`），降低学习成本
2. **简化用户输入**：相比 ECharts 原生格式更简洁，省略冗余配置
3. **兼容 pyecharts**：命名风格与 pyecharts 相似，便于迁移

### B.1 折线图 / 面积图 / 柱状图

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

### B.2 饼图

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

### B.3 热力图

**pyecharts:** (需手动计算坐标索引)
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
nb.heatmap({
    '2023': {'1月': 0.05, '2月': 0.03, '3月': 0.08},
    '2024': {'1月': 0.10, '2月': -0.02, '3月': 0.06}
})
```

| 对比项 | pyecharts | ECharts | Notebook |
|--------|-----------|---------|----------|
| 数据格式 | 坐标索引 `[x, y, v]` | 坐标索引 | 嵌套字典 `{y: {x: v}}` |
| DataFrame支持 | ❌ | ❌ | ✅ 自动转换 |
| 用户负担 | 需计算索引 | 需计算索引 | **直接语义化** ✅ |
| 简化程度 | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |

### B.4 总结对比表

| 图表类型 | pyecharts 风格 | ECharts 键名 | Notebook 简化 |
|---------|---------------|-------------|--------------|
| line/area/bar | `add_xaxis()` / `add_yaxis()` | `xAxis.data` / `series[].data` | `xAxis` + `series` |
| pie | 元组列表 | `{name, value}` 对象 | 同 ECharts |
| heatmap | 坐标索引 | 坐标索引 | **嵌套字典** (更语义化) |

**设计理念**：Notebook 在保持 ECharts 键名习惯的同时，尽可能简化用户输入。热力图采用嵌套字典格式，无需用户手动计算坐标索引，是最大的简化点。

---

## 附录C：Python 数据层设计

### C.1 数据流

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

### C.2 核心类设计

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

### C.3 设计决策

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

---

## 附录D：选择性截图功能

### D.1 功能需求

用户可以在 TOC 面板中勾选需要截图的内容（支持多选），点击"截图选中"按钮后，将选中内容截图并复制到剪贴板。

### D.2 技术挑战

| 挑战 | 说明 |
|------|------|
| **Vue3 响应式** | `:class` 绑定变化触发虚拟 DOM 更新，可能导致图表重新渲染 |
| **Canvas 克隆** | `cloneNode()` 无法克隆 Canvas 内容，ECharts 图表会丢失 |
| **布局变化** | 使用 `display: none` 隐藏元素会触发重排，影响图表尺寸 |

### D.3 最终方案：逐个截图 + Canvas 拼接

**架构设计：**
```
┌──────────────────────────────────────────────┐
│  主体容器 (.notebook-container)               │
│  ├── Header ──────────────────────────────┐  │
│  │  ↓ snapdom(element)                     │  │
│  │  → Blob 1                              │  │
│  ├── Section 0 (已折叠) ─────────────────┐ │  │
│  │  ↓ snapdom(element)                     │ │  │
│  │  → Blob 2                              │ │  │
│  ├── Section 1 (展开，表格已滚动) ───────┐│  │
│  │  ↓ snapdom(element)                    ││  │
│  │  → Blob 3                             ││  │
│  └─────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
                    ↓
         Canvas 拼接（保留间距和 padding）
                    ↓
              输出 PNG
```

### D.4 方案对比

| 方案 | 原理 | 问题 | 状态 |
|------|------|------|------|
| ❌ CSS `display: none` | 隐藏未选中元素 | 触发重排，图表尺寸变化 | 废弃 |
| ❌ CSS `visibility: hidden` | 隐藏但保留空间 | 占用空白，截图有空白 | 废弃 |
| ❌ Vue `:class` 绑定 | 响应式更新 class | Vue 虚拟 DOM 更新可能影响图表 | 废弃 |
| ⚠️ DOM 克隆 + 独立容器 | 克隆内容到新容器 | `cloneNode()` 不保留折叠状态、表格滚动位置 | V1.0 |
| ✅ **逐个截图 + Canvas 拼接** | 直接截图原元素后拼接 | 所见即所得，无需 DOM 克隆 | **V2.0** |

---

## 附录E：技术探索路径（方法论）

### E.1 问题定义

**需求**：Vue3 环境下实现选择性截图（勾选部分内容后截图到剪贴板）

**约束**：
- ECharts 图表必须完整显示
- 折叠/展开状态需同步
- 表格滚动位置需保留
- 不能影响原页面交互

### E.2 探索历程

| 尝试 | 方案 | 结果 | 原因 |
|------|------|------|------|
| 1 | CSS `display: none` | ❌ | 触发重排，图表尺寸变化 |
| 2 | CSS `visibility: hidden` | ❌ | 占用空白，截图有空白 |
| 3 | Vue `:class` 绑定 | ❌ | Vue 虚拟 DOM 更新影响图表 |
| 4 | 绝对定位移出视口 | ❌ | 仍需操作 Vue 管理的 DOM |
| 5 | DOM 克隆 + 独立容器 | ⚠️ | 不保留折叠状态、滚动位置 |
| 6 | **逐个截图 + Canvas 拼接** | ✅ | 所见即所得，无需克隆 |

### E.3 关键洞察

| 洞察 | 说明 |
|------|------|
| **避免 Vue 响应式干扰** | 不要通过 `:class` 或数据绑定来控制截图相关样式 |
| **DOM 克隆有局限** | `cloneNode()` 只克隆 DOM 结构，不克隆组件状态 |
| **直接截图最可靠** | 对最终渲染结果截图，而非试图重建渲染状态 |
| **工具各司其职** | snapdom 处理 HTML→PNG，手动 Canvas 处理拼接和间距 |

### E.4 可复用的方法论

**面对"截图特定内容"类问题时的决策树：**

```
是否需要保留交互状态（折叠、滚动）？
├── 是 → 逐个元素截图 + Canvas 拼接
└── 否 → DOM 克隆方案可接受
    └── 是否包含 Canvas/ECharts？
        ├── 是 → 需要手动 ctx.drawImage() 复制
        └── 否 → 纯 DOM 克隆即可
```

---

## 附录F：版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| V1 | 2025-02 | 基础 Notebook 系统 |
| V2 | 2025-02-19 | Section 模块化，Notion 风格 |
| V3 | 2025-02-27 | API 极简化，统一 `chart()` |
| V3.5 | 2026-03-02 | Alpine 声明式模板 |
| V4.0 | 2026-03-03 | 重构文档结构：效果 → Python → Vue3 |
| V4.1 | 2026-03-03 | **JSON 规范优化**：`content`/`children` 分离 |
| V4.2 | 2026-03-04 | **选择性截图 V1.0**：独立截图容器 + Canvas 手动复制 |
| V4.3 | 2026-03-04 | **技术讨论**：ctx.drawImage() vs SVG 方案 |
| V4.4 | 2026-03-04 | **选择性截图 V2.0**：逐个截图 + Canvas 拼接 |
| V5.0 | 2026-03-05 | **文档重构**：三段式主体 + 六大附录 |

---

## 附录G：文件结构

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
        ├── notebook.css     # 样式文件
        ├── vue.global.prod.js
        ├── echarts.min.js
        └── snapdom.min.js   # 截图库
```
