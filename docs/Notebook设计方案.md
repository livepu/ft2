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
- 通过右侧控制面板切换（左右浮动布局，图表靠左，控制靠右）
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
- **visualMap 范围使用实际数据最大最小值（非强制对称）
- 切换缩放倍数时自动重置 visualMap 选择区间

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

### 3.4 图表初始化（插件架构）

**架构设计：插件注册 + 通用兜底**

```javascript
// 数据提取（统一格式）
const extractChartData = (charts) => {
    if (!charts?.series?.[0]) return null;
    return {
        chart_type: charts.series[0].type,
        series: charts.series,
        xAxis: charts.xAxis?.[0]?.data || [],
        yAxis: charts.yAxis?.[0]?.data || [],
        raw: charts  // 保留原始配置，供特殊类型使用
    };
};

// 插件注册表
const chartPlugins = {
    pie: (extracted, options) => processPie(extracted, options),
    heatmap: (extracted, options) => processHeatmap(extracted, options),
    gauge: gaugePlugin,
    radar: radarPlugin,
    funnel: funnelPlugin
};

// 统一处理入口
const processChart = (extracted, options = {}) => {
    const chartType = extracted.chart_type;
    const plugin = chartPlugins[chartType];
    
    // 统一获取配色（heatmap 除外）
    if (chartType !== 'heatmap') {
        options.colors = getChartColors(chartType);
    }
    
    const option = plugin ? plugin(extracted, options) : buildGenericOption(extracted, options);
    
    // 统一添加默认 tooltip
    if (!option.tooltip) {
        option.tooltip = {};
    }
    
    return option;
};

// 图表初始化
onMounted(() => {
    if (['chart', 'heatmap', 'pyecharts'].includes(props.cell.type)) {
        chartInstance = echarts.init(chartRef.value);
        const option = processChart(extracted, options);
        chartInstance.setOption(option);
    }
});

// 窗口 resize 自适应
window.addEventListener('resize', () => {
    chartInstance?.resize();
});
```

**架构优势：**

| 特性 | 说明 |
|------|------|
| **插件注册** | 新增图表类型只需注册插件，无需修改核心逻辑 |
| **配色统一** | 在 processChart 层统一获取，避免重复调用 |
| **tooltip 统一** | 默认添加，插件可覆盖 |
| **通用兜底** | 未注册类型走 buildGenericOption |
| **特殊类型透传** | gauge/radar/funnel 等保留原始配置 |

**图表类型处理策略：**

| 图表类型 | 处理方式 | 配色来源 |
|---------|---------|---------|
| line/bar/area/scatter | buildGenericOption | 用户可选配色 |
| pie | processPie 插件 | 用户可选配色 |
| heatmap | processHeatmap 插件 | 固定蓝-黄-红渐变 |
| gauge/radar/funnel | 透传插件 | 用户可选配色 |
| 其他 | buildGenericOption | 用户可选配色 |

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
| with 内有 title | `with nb.section("分析"): nb.table(data, title="明细")` | Cell.title = "明细"（小标题） |
| with 外有 title | `nb.table(data, title="基金列表")` | **自动创建 Section** |
| with 外无 title | `nb.text("说明文字")` | 普通 Cell，不包装 |

**核心思想**：用户不用显式创建 Section，给 `title` 参数就自动分组。

**架构设计**：详见附录I - CellBuilder/Notebook 职责分离

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
| V5.1 | 2026-03-05 | **Chart 参数设计**：参数分层 + PyEcharts 规范 + 输出统一 |
| V5.2 | 2026-03-05 | **架构重构**：CellBuilder/Notebook 职责分离 + title 统一处理 |
| V5.3 | 2026-03-07 | **图表布局优化**：饼图/热力图控制面板右浮动，左右布局清晰 |
| V5.4 | 2026-03-07 | **热力图功能增强**：visualMap 实际数据范围 + 缩放时自动重置选择区间 |
| V5.5 | 2026-03-07 | **ft-table 架构优化**：组件注入样式（核心功能）vs 外部 CSS（视觉样式）职责清晰分离 |
| V5.6 | 2026-03-21 | **图表插件架构**：插件注册模式 + 通用兜底 + 配色统一管理 + tooltip 统一添加 |

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
        ├── notebook3A.js    # Vue3 组件（插件架构版本）
        ├── notebook.css     # 样式文件
        ├── vue.global.prod.js
        ├── echarts.min.js
        └── snapdom.min.js   # 截图库
```

---

## 附录H：图表插件架构设计

### H.1 核心设计理念

```
┌─────────────────────────────────────────────────────────────────┐
│                    图表处理架构                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  extractChartData()                                              │
│  ├── 统一数据格式                                                │
│  ├── chart_type, series, xAxis, yAxis                           │
│  └── raw: 保留原始配置（供特殊类型使用）                          │
│                         ↓                                        │
│  processChart()                                                  │
│  ├── 统一获取配色（heatmap 除外）                                │
│  ├── 统一添加 tooltip                                            │
│  └── 查表分发到插件                                              │
│                         ↓                                        │
│  chartPlugins[chartType]                                         │
│  ├── 有插件 → 执行插件                                           │
│  └── 无插件 → buildGenericOption() 通用兜底                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**核心思路**：插件注册模式 + 通用兜底，新增图表类型只需注册插件，无需修改核心逻辑。

### H.2 设计目标

| 目标 | 说明 |
|------|------|
| **可扩展性** | 新增图表类型只需注册插件 |
| **职责清晰** | 插件只关心核心配置，配色和 tooltip 统一处理 |
| **避免重复** | 配色获取、tooltip 添加只在一处 |
| **兼容性好** | 特殊类型通过 raw 保留原始配置 |

### H.3 插件注册表

```javascript
const chartPlugins = {
    // 差异化处理（需要特殊逻辑）
    pie: (extracted, options) => processPie(extracted, options),
    heatmap: (extracted, options) => processHeatmap(extracted, options),
    
    // 透传型（保留原始配置）
    gauge: (extracted) => ({ series: extracted.series }),
    radar: (extracted) => ({ ...extracted.raw }),
    funnel: (extracted) => ({ series: extracted.series })
};
```

### H.4 统一处理入口

```javascript
const processChart = (extracted, options = {}) => {
    const chartType = extracted.chart_type;
    const plugin = chartPlugins[chartType];
    
    // 统一获取配色（heatmap 除外）
    if (chartType !== 'heatmap') {
        options.colors = getChartColors(chartType);
    }
    
    const option = plugin ? plugin(extracted, options) : buildGenericOption(extracted, options);
    
    // 统一添加默认 tooltip
    if (!option.tooltip) {
        option.tooltip = {};
    }
    
    return option;
};
```

### H.5 扩展新图表类型

**步骤1：添加插件**

```javascript
// 差异化处理（需要特殊逻辑）
const processNewType = (extracted, options) => {
    const colors = options.colors;
    // ... 自定义处理逻辑
    return { color: colors, series: extracted.series };
};

// 透传型（只需保留原始配置）
const newTypePlugin = (extracted) => ({
    series: extracted.series
});
```

**步骤2：注册插件**

```javascript
chartPlugins['newType'] = newTypePlugin;
```

### H.6 图表类型处理策略

| 图表类型 | 处理方式 | 配色来源 |
|---------|---------|---------|
| line/bar/area/scatter | buildGenericOption | 用户可选配色 |
| pie | processPie 插件 | 用户可选配色 |
| heatmap | processHeatmap 插件 | 固定蓝-黄-红渐变 |
| gauge/radar/funnel | 透传插件 | 用户可选配色 |
| 其他 | buildGenericOption | 用户可选配色 |

### H.7 设计优势

| 优势 | 说明 |
|------|------|
| **可扩展性** | 新增图表类型只需注册插件，无需修改核心逻辑 |
| **职责清晰** | 插件只关心核心配置，配色和 tooltip 统一处理 |
| **避免重复** | 配色获取、tooltip 添加只在一处 |
| **兼容性好** | 特殊类型通过 raw 保留原始配置 |
| **易于维护** | 每个插件职责单一，代码清晰 |

### H.8 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| V1.0 | 2026-03-21 | 建立插件架构：插件注册 + 通用兜底 + 配色统一 |

---

## 附录I：Chart 参数设计思路
└─────────────────────────────────────────────────────────────────┘
```

### H.5 设计理念

```
简化但不简陋
    ↓
基础参数必填，保证图表可读性
可选参数遵循 pyecharts，保证兼容性
    ↓
用户按需使用，无学习成本
```

**设计优势：**

| 优势 | 说明 |
|------|------|
| **兼容性** | 参数命名与 pyecharts 一致，用户无需学习新规范 |
| **灵活性** | 可选参数满足高级需求，同时不影响简单用法 |
| **渐进式** | 入门简单，深入有路 |
| **文档复用** | 用户可直接查阅 pyecharts 文档 |

### H.6 容器参数设计

#### pyecharts 输出分层

| 方法 | 输出内容 | 用途 |
|------|----------|------|
| `dump_options()` | ECharts 配置 JSON | 数据层，不含容器参数 |
| `render_embed()` | 完整 HTML | 包含 `<div style="width; height">` 容器 |

#### Notebook 设计

```python
# Python 输出
{
    "charts": {...},      # pyecharts dump_options() → ECharts 配置
    "width": "100%",      # 我们包装的容器参数
    "height": "400px"     # 我们包装的容器参数
}
```

```javascript
// 前端使用
<div :style="{width: content.width, height: content.height}">
    <!-- ECharts 容器 -->
</div>
```

#### 参数分工

| 参数 | 来源 | 管理方 |
|------|------|--------|
| `charts` | pyecharts `dump_options()` | pyecharts |
| `width` | Notebook 参数 | 我们 |
| `height` | Notebook 参数 | 我们 |

**设计原因**：我们的场景是 Vue3 动态渲染，不是 pyecharts 的独立 HTML 输出，所以容器参数需要我们自己管理。

### H.7 数据格式（简化）

#### line/bar/area

```python
# Notebook 简化格式
{
    'xAxis': ['1月', '2月', '3月'],
    'series': [
        {'name': '策略', 'data': [1.0, 1.05, 1.08]},
        {'name': '基准', 'data': [1.0, 1.02, 1.04]}
    ]
}

# 对应 pyecharts 调用
line.add_xaxis(['1月', '2月', '3月'])
line.add_yaxis('策略', [1.0, 1.05, 1.08])
line.add_yaxis('基准', [1.0, 1.02, 1.04])
```

**DataFrame 转换：**

```python
# DataFrame 输入
df = pd.DataFrame({
    'date': ['1月', '2月', '3月'],
    '策略': [1.0, 1.05, 1.08],
    '基准': [1.0, 1.02, 1.04]
})

# 转换逻辑
def df_to_line_bar(df, x_col=None):
    """DataFrame → line/bar/area 数据格式"""
    x_col = x_col or df.columns[0]
    xaxis = df[x_col].tolist()
    series = [
        {'name': col, 'data': df[col].tolist()}
        for col in df.columns if col != x_col
    ]
    return {'xAxis': xaxis, 'series': series}

# 使用
nb.chart('line', df_to_line_bar(df, x_col='date'))
```

#### pie

```python
# Notebook 简化格式
[
    {'name': '股票', 'value': 60},
    {'name': '债券', 'value': 25},
    {'name': '现金', 'value': 15}
]

# 对应 pyecharts 调用
pie.add('', [('股票', 60), ('债券', 25), ('现金', 15)])
```

**DataFrame 转换：**

```python
# DataFrame 输入
df = pd.DataFrame({
    'name': ['股票', '债券', '现金'],
    'value': [60, 25, 15]
})

# 转换逻辑
def df_to_pie(df, name_col='name', value_col='value'):
    """DataFrame → pie 数据格式"""
    return [
        {'name': row[name_col], 'value': row[value_col]}
        for _, row in df.iterrows()
    ]

# 使用
nb.chart('pie', df_to_pie(df))
```

#### heatmap

```python
# Notebook 简化格式（嵌套字典）
{
    '2023': {'1月': 0.02, '2月': -0.01, '3月': 0.03},
    '2024': {'1月': 0.05, '2月': -0.02, '3月': 0.08}
}

# 对应 pyecharts 调用（需转换为坐标索引）
# [[x_index, y_index, value], ...]
```

**DataFrame 转换：**

```python
# DataFrame 输入
df = pd.DataFrame({
    'year': ['2023', '2023', '2023', '2024', '2024', '2024'],
    'month': ['1月', '2月', '3月', '1月', '2月', '3月'],
    'value': [0.02, -0.01, 0.03, 0.05, -0.02, 0.08]
})

# 转换逻辑
def df_to_heatmap(df, y_col, x_col, value_col):
    """DataFrame → heatmap 数据格式（嵌套字典）"""
    result = {}
    for _, row in df.iterrows():
        y = row[y_col]
        x = row[x_col]
        v = row[value_col]
        if y not in result:
            result[y] = {}
        result[y][x] = v
    return result

# 使用
nb.heatmap(df_to_heatmap(df, y_col='year', x_col='month', value_col='value'))
```

#### 数据格式汇总

| chart_type | Notebook 格式 | DataFrame 转换函数 |
|------------|--------------|-------------------|
| `line` | `{'xAxis': [...], 'series': [...]}` | `df_to_line_bar(df, x_col)` |
| `bar` | `{'xAxis': [...], 'series': [...]}` | `df_to_line_bar(df, x_col)` |
| `area` | `{'xAxis': [...], 'series': [...]}` | `df_to_line_bar(df, x_col)` |
| `pie` | `[{'name': ..., 'value': ...}, ...]` | `df_to_pie(df, name_col, value_col)` |
| `heatmap` | `{y: {x: value, ...}, ...}` | `df_to_heatmap(df, y_col, x_col, value_col)` |
| `kline` | `{'xAxis': [...], 'series': [{'data': [[o,c,l,h], ...]}]}` | - |

### H.7 数据转换实现

#### 转换流程

```
┌─────────────────────────────────────────────────────────────────┐
│  chart_type    输入格式                    pyecharts 方法        │
├─────────────────────────────────────────────────────────────────┤
│  line          {'xAxis': [...],             Line()              │
│  bar              'series': [...]}          Bar()               │
│  area                                 add_xaxis() + add_yaxis() │
├─────────────────────────────────────────────────────────────────┤
│  pie            [{'name': ..., 'value': Pie()                   │
│                   ...}]              add()                      │
├─────────────────────────────────────────────────────────────────┤
│  heatmap        {y: {x: value}}       HeatMap()                 │
│                 DataFrame             add_xaxis() + add_yaxis() │
├─────────────────────────────────────────────────────────────────┤
│  kline          {'xAxis': [...],      Kline()                   │
│                   'series': [...]}    add_xaxis() + add_yaxis() │
└─────────────────────────────────────────────────────────────────┘
```

#### 核心实现代码

```python
@staticmethod
def chart(chart_type: str, data, title: str, height: str = '400px', **kwargs) -> Cell:
    """创建图表（pyecharts 简化封装）"""
    from pyecharts.charts import Line, Bar, Pie, HeatMap, Kline
    from pyecharts import options as opts
    
    # 1. 提取容器参数
    width = kwargs.pop('width', '100%')
    
    # 2. 提取全局参数
    global_opts_keys = ['title_opts', 'legend_opts', 'tooltip_opts',
                        'xaxis_opts', 'yaxis_opts', 'datazoom_opts',
                        'visualmap_opts', 'grid_opts']
    global_opts = {k: kwargs.pop(k) for k in global_opts_keys if k in kwargs}
    
    # 3. 提取系列参数
    series_opts = kwargs.pop('series_opts', {})
    
    # 4. 根据 chart_type 构建实例并转换数据
    if chart_type in ('line', 'bar', 'area'):
        chart = _build_line_bar_area(chart_type, data, series_opts)
    elif chart_type == 'pie':
        chart = _build_pie(data, series_opts)
    elif chart_type == 'heatmap':
        chart = _build_heatmap(data, series_opts)
    elif chart_type == 'kline':
        chart = _build_kline(data, series_opts)
    else:
        raise ValueError(f"不支持的图表类型: {chart_type}")
    
    # 5. 应用全局配置
    if global_opts:
        chart.set_global_opts(**{
            k: _create_opts(k, v) for k, v in global_opts.items()
        })
    
    # 6. 获取 ECharts option
    option_dict = json.loads(chart.dump_options())
    
    # 7. 返回 Cell
    return Cell(
        CellType.CHART,
        {"charts": option_dict, "width": width, "height": height},
        title
    )
```

#### 各类型转换函数

```python
def _build_line_bar_area(chart_type, data, series_opts):
    """构建 line/bar/area 图表"""
    from pyecharts.charts import Line, Bar
    from pyecharts import options as opts
    
    ChartClass = Line if chart_type in ('line', 'area') else Bar
    chart = ChartClass()
    
    chart.add_xaxis(data['xAxis'])
    
    for s in data['series']:
        params = {'series_name': s['name'], 'y_axis': s['data'], **series_opts}
        if chart_type == 'area':
            params['areastyle_opts'] = opts.AreaStyleOpts(opacity=0.3)
        chart.add_yaxis(**params)
    
    return chart


def _build_pie(data, series_opts):
    """构建饼图"""
    from pyecharts.charts import Pie
    
    chart = Pie()
    data_pair = [(item['name'], item['value']) for item in data]
    chart.add(series_name='', data_pair=data_pair, **series_opts)
    return chart


def _build_heatmap(data, series_opts):
    """构建热力图"""
    from pyecharts.charts import HeatMap
    
    chart = HeatMap()
    
    # DataFrame 处理
    if HAS_PANDAS and isinstance(data, pd.DataFrame):
        df = data.copy()
        if isinstance(df.index, pd.RangeIndex) and len(df.columns) > 1:
            df = df.set_index(df.columns[0])
        data = df.to_dict(orient='index')
    
    # 转换为坐标格式
    xaxis_data, yaxis_data, values = [], [], []
    for y_idx, (y_name, x_dict) in enumerate(data.items()):
        yaxis_data.append(y_name)
        for x_name, value in x_dict.items():
            if x_name not in xaxis_data:
                xaxis_data.append(x_name)
            values.append([xaxis_data.index(x_name), y_idx, value])
    
    chart.add_xaxis(xaxis_data)
    chart.add_yaxis(series_name='', yaxis_data=yaxis_data, value=values, **series_opts)
    return chart


def _build_kline(data, series_opts):
    """构建 K 线图"""
    from pyecharts.charts import Kline
    
    chart = Kline()
    chart.add_xaxis(data['xAxis'])
    for s in data['series']:
        chart.add_yaxis(series_name=s.get('name', ''), y_axis=s['data'], **series_opts)
    return chart


def _create_opts(opts_name, opts_dict):
    """将 dict 转换为 pyecharts opts 对象"""
    from pyecharts import options as opts
    
    opts_map = {
        'title_opts': opts.TitleOpts,
        'legend_opts': opts.LegendOpts,
        'tooltip_opts': opts.TooltipOpts,
        'xaxis_opts': opts.AxisOpts,
        'yaxis_opts': opts.AxisOpts,
        'visualmap_opts': opts.VisualMapOpts,
        'grid_opts': opts.GridOpts,
    }
    
    if opts_name == 'datazoom_opts':
        return [opts.DataZoomOpts(**item) for item in opts_dict]
    
    OptClass = opts_map.get(opts_name)
    return OptClass(**opts_dict) if OptClass else opts_dict
```

### H.8 参数传递

| Notebook 参数 | 传递给 pyecharts |
|--------------|-----------------|
| `title_opts={...}` | `line.set_global_opts(title_opts=opts.TitleOpts(**title_opts))` |
| `yaxis_opts={...}` | `line.set_global_opts(yaxis_opts=opts.AxisOpts(**yaxis_opts))` |
| `series_opts={...}` | `line.add_yaxis(..., **series_opts)` |
| `datazoom_opts=[...]` | `line.set_global_opts(datazoom_opts=[opts.DataZoomOpts(**d) for d in datazoom_opts])` |

### H.8 输出格式（统一）

`nb.chart()` 和 `nb.pyecharts()` 输出格式完全一致：

```json
{
  "type": "chart",
  "title": "净值曲线",
  "content": {
    "charts": {
      "animation": true,
      "title": {"text": "净值走势"},
      "legend": {"data": ["策略", "基准"]},
      "tooltip": {"trigger": "axis"},
      "xAxis": {"type": "category", "data": ["1月", "2月", "3月"]},
      "yAxis": {"type": "value", "min": 0.9, "max": 1.2},
      "series": [
        {"name": "策略", "type": "line", "data": [1.0, 1.05, 1.08]},
        {"name": "基准", "type": "line", "data": [1.0, 1.02, 1.04]}
      ]
    },
    "width": "100%",
    "height": "500px"
  }
}
```

### H.9 前端渲染

```javascript
// Vue3 组件
onMounted(() => {
    const chartInstance = echarts.init(chartRef.value);
    chartInstance.setOption(cell.content.charts);  // 直接使用 charts
});

// 窗口 resize
window.addEventListener('resize', () => {
    chartInstance?.resize();
});
```

### H.10 方法定位

| 方法 | 定位 | 数据输入 | 输出 |
|------|------|---------|------|
| `nb.chart()` | 简化封装 | 简化格式 + pyecharts kwargs | 标准 JSON |
| `nb.pyecharts()` | 透传 | pyecharts 对象 | 标准 JSON |

```
┌─────────────────────────────────────────────────────────────────┐
│  nb.chart()      简化输入 → pyecharts 实例 → dump_options()    │
├─────────────────────────────────────────────────────────────────┤
│  nb.pyecharts()  pyecharts 对象 → dump_options()               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    统一输出 JSON 格式
                              ↓
                    前端 setOption() 渲染
```

### H.11 使用示例

```python
# 1. 基础用法（title 必填）
nb.chart('line', data, title='净值曲线')

# 2. 基础 + 容器参数
nb.chart('line', data, title='净值曲线', height='500px')

# 3. 基础 + 全局参数（pyecharts 规范）
nb.chart('line', data,
    title='净值曲线',
    height='500px',
    legend_opts={'is_show': False},
    yaxis_opts={'min_': 0.9, 'max_': 1.2},
    tooltip_opts={'trigger': 'axis'}
)

# 4. 基础 + 系列参数
nb.chart('line', data,
    title='净值曲线',
    series_opts={'is_smooth': True}
)

# 5. 完整配置
nb.chart('line', data,
    title='净值曲线',
    height='500px',
    yaxis_opts={'min_': 0.9},
    series_opts={'is_smooth': True},
    datazoom_opts=[{'type_': 'slider', 'start': 20, 'end': 80}]
)

# 6. 高级需求 → 直接用 pyecharts
from pyecharts.charts import Line
from pyecharts import options as opts

line = Line()
line.add_xaxis(['1月', '2月', '3月'])
line.add_yaxis('策略', [1.0, 1.05, 1.08], is_smooth=True)
line.add_yaxis('基准', [1.0, 1.02, 1.04], is_smooth=False)
line.set_global_opts(yaxis_opts=opts.AxisOpts(min_=0.9))

nb.pyecharts(line, title='净值曲线', height='600px')
```

### H.12 设计优势

| 优势 | 说明 |
|------|------|
| **简化输入** | 数据格式比 pyecharts 简洁 |
| **复用成熟方案** | 内部使用 pyecharts，无需自己实现转换 |
| **输出标准** | 完全符合 ECharts 规范 |
| **格式统一** | chart/pyecharts 输出一致，前端处理简单 |
| **维护简单** | pyecharts 更新时自动兼容 |

---

## 附录I：架构设计 - CellBuilder/Notebook 职责分离

### I.1 设计原则

**核心思想**：Cell 只负责数据，Notebook 负责布局

```
┌─────────────────────────────────────────────────────┐
│  CellBuilder                                        │
│  ├── 只负责构建 Cell 数据                            │
│  ├── 不涉及 title                                   │
│  └── 输出：Cell(content, options)                   │
├─────────────────────────────────────────────────────┤
│  Notebook._add_cell                                 │
│  ├── 统一处理 title 逻辑                            │
│  ├── with 内 → Cell.title = title（小标题）         │
│  ├── with 外有 title → 自动创建 Section             │
│  └── with 外无 title → 直接添加 Cell                │
└─────────────────────────────────────────────────────┘
```

### I.2 数据流

```python
# 用户调用
nb.table(data, title='基金列表')
    ↓
# CellBuilder 构建纯数据（无 title）
cell = CellBuilder.table(data, columns, options)
    ↓
# Notebook 处理布局
_add_cell(cell, title)  # title 只传一次
```

### I.3 _add_cell 逻辑

| 场景 | 代码 | 效果 |
|------|------|------|
| with 内有 title | `with nb.section("分析"): nb.table(data, title="明细")` | Cell.title = "明细"（小标题） |
| with 外有 title | `nb.table(data, title="基金列表")` | 自动创建 Section |
| with 外无 title | `nb.text("说明文字")` | 普通 Cell |

### I.4 CellBuilder 方法签名

```python
class CellBuilder:
    # 文本类
    def title(text: str, level: int = 1) -> Cell
    def text(text: str, style: str = 'normal') -> Cell
    def markdown(text: str) -> Cell
    
    # 代码类
    def code(code: str, language: str = 'python', output: str = None) -> Cell
    
    # 数据类
    def table(data: List[Dict], columns: List[str] = None, options: dict = None) -> Cell
    def metrics(data: List[Dict], columns: int = 4) -> Cell
    
    # 图表类
    def chart(chart_type: str, data, height: str = '400px', **kwargs) -> Cell
    def pyecharts(chart, height: str = '400px', width: str = '100%') -> Cell
    
    # 布局类
    def divider() -> Cell
    def html(html_content: str) -> Cell
    def section(title: str, children: List[CellLike] = None, level: int = 1, collapsed: bool = None) -> Section
```

**关键点**：所有方法都不包含 `title` 参数

### I.5 Notebook 方法签名

```python
class Notebook:
    # 文本类
    def title(self, text: str, level: int = 1) -> Notebook
    def text(self, text: str, style: str = 'normal') -> Notebook
    def markdown(self, text: str) -> Notebook
    
    # 代码类
    def code(self, code: str, language: str = 'python', output: str = None) -> Notebook
    
    # 数据类
    def table(self, data, columns=None, title=None, **options) -> Notebook
    def metrics(self, data, title=None, columns: int = 4) -> Notebook
    
    # 图表类
    def chart(self, chart_type, data, title=None, height='400px', **kwargs) -> Notebook
    def pyecharts(self, chart, title=None, height='400px', width='100%') -> Notebook
    
    # 布局类
    def divider() -> Notebook
    def html(html_content: str) -> Notebook
    def section(self, title: str, collapsed: bool = None) -> SectionContext
```

**关键点**：数据类和图表类方法包含 `title` 参数，传给 `_add_cell` 统一处理

### I.6 设计优势

| 优势 | 说明 |
|------|------|
| **单一职责** | CellBuilder 只管数据，Notebook 只管布局 |
| **参数简洁** | title 只传一次，不冗余 |
| **逻辑集中** | title 处理集中在 `_add_cell` 一处 |
| **易于维护** | 新增 Cell 类型只需关注数据构建 |

### I.7 使用示例
```python
# 自动创建 Section
nb.table(data, title='基金列表')
nb.chart('line', data, title='净值曲线')

# Section 内作为小标题
with nb.section("分析"):
    nb.table(data, title='明细')
    nb.chart('line', data, title='走势')

# 可折叠 Section
with nb.section("详细数据", collapsed=True):
    nb.table(data)
    nb.chart('bar', data)
```

---

## 附录J：Python端图表插件架构重构思路

### J.1 问题背景

**当前架构**：`nb.chart()` 使用 if-elif 判断图表类型

```python
if chart_type in ('line', 'bar', 'area'):
    chart = _build_line_bar_area(chart_type, data, series_opts)
elif chart_type == 'pie':
    chart = _build_pie(data, series_opts)
elif chart_type == 'heatmap':
    chart = _build_heatmap(data, series_opts)
elif chart_type == 'kline':
    chart = _build_kline(data, series_opts)
else:
    raise ValueError(f"不支持的图表类型: {chart_type}")
```

**问题**：
1. 扩展新图表类型需要修改核心代码
2. 数据转换逻辑和构建逻辑混在一起
3. 与前端插件架构不一致

### J.2 数据格式分析

| 图表类型 | 用户输入格式 | pyecharts 需要 | 是否需要转换 |
|---------|-------------|---------------|-------------|
| line/bar/area/scatter/kline | `{xAxis, series}` | `{xAxis, series}` | ❌ 无需转换 |
| pie | `[{name, value}]` | `[(name, value)]` | ✅ 需要转换 |
| heatmap | `{y: {x: value}}` 或 DataFrame | `[[x,y,value], ...]` | ✅ 需要转换 |

**关键发现**：5种图表（line/bar/area/scatter/kline）已经是统一格式！

### J.3 重构方案一：适配器 + 构建器分离

#### 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           数据转换流程                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  chart(chart_type, data)                                                     │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────┐                                                         │
│  │ 查表获取配置     │                                                         │
│  │ CHART_REGISTRY   │                                                        │
│  └─────────────────┘                                                         │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────┐      ┌─────────────────┐                               │
│  │ 数据适配器       │      │ 转换后的数据     │                               │
│  │ adapter(data)   │ ───→ │ adapted_data    │                               │
│  └─────────────────┘      └─────────────────┘                               │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────┐                                                         │
│  │ 图表构建器       │                                                         │
│  │ builder(...)    │                                                         │
│  └─────────────────┘                                                         │
│         │                                                                    │
│         ▼                                                                    │
│  pyecharts 图表对象                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 数据适配器

```python
def _adapt_passthrough(data):
    """透传（无需转换）"""
    return data

def _adapt_pie(data):
    """饼图适配：[{name, value}] → [(name, value)]"""
    return [(item['name'], item['value']) for item in data]

def _adapt_heatmap(data):
    """热力图适配：{y: {x: value}} → {xAxis, yAxis, data}"""
    if HAS_PANDAS and isinstance(data, pd.DataFrame):
        df = data.copy()
        if isinstance(df.index, pd.RangeIndex) and len(df.columns) > 1:
            df = df.set_index(df.columns[0])
        data = df.to_dict(orient='index')
    
    xaxis_data, yaxis_data, values = [], [], []
    for y_idx, (y_name, x_dict) in enumerate(data.items()):
        yaxis_data.append(str(y_name))
        for x_name, value in x_dict.items():
            x_name_str = str(x_name)
            if x_name_str not in xaxis_data:
                xaxis_data.append(x_name_str)
            values.append([xaxis_data.index(x_name_str), y_idx, value])
    
    return {'xAxis': xaxis_data, 'yAxis': yaxis_data, 'data': values}
```

#### 图表构建器

```python
def _build_xy_chart(ChartClass, adapted_data, series_opts, is_area=False):
    """XY 轴图表构建器（通用）"""
    from pyecharts import options as opts
    chart = ChartClass()
    chart.add_xaxis(adapted_data['xAxis'])
    for s in adapted_data['series']:
        params = {'series_name': s.get('name', ''), 'y_axis': s['data'], **series_opts}
        if is_area:
            params['areastyle_opts'] = opts.AreaStyleOpts(opacity=0.3)
        chart.add_yaxis(**params)
    return chart

def _build_pie_chart(adapted_data, series_opts):
    """饼图构建器"""
    from pyecharts.charts import Pie
    chart = Pie()
    chart.add('', adapted_data, **series_opts)
    return chart

def _build_heatmap_chart(adapted_data, series_opts):
    """热力图构建器"""
    from pyecharts.charts import HeatMap
    chart = HeatMap()
    chart.add_xaxis(adapted_data['xAxis'])
    chart.add_yaxis('', adapted_data['yAxis'], adapted_data['data'], **series_opts)
    return chart
```

#### 图表类型注册表

```python
from pyecharts.charts import Line, Bar, Scatter, Kline

CHART_REGISTRY = {
    # XY 轴系列（透传 + 统一构建器）
    'line': {
        'class': Line,
        'adapter': _adapt_passthrough,
        'builder': lambda d, opts: _build_xy_chart(Line, d, opts)
    },
    'bar': {
        'class': Bar,
        'adapter': _adapt_passthrough,
        'builder': lambda d, opts: _build_xy_chart(Bar, d, opts)
    },
    'area': {
        'class': Line,
        'adapter': _adapt_passthrough,
        'builder': lambda d, opts: _build_xy_chart(Line, d, opts, is_area=True)
    },
    'scatter': {
        'class': Scatter,
        'adapter': _adapt_passthrough,
        'builder': lambda d, opts: _build_xy_chart(Scatter, d, opts)
    },
    'kline': {
        'class': Kline,
        'adapter': _adapt_passthrough,
        'builder': lambda d, opts: _build_xy_chart(Kline, d, opts)
    },
    
    # 特殊类型（自定义适配器 + 构建器）
    'pie': {
        'adapter': _adapt_pie,
        'builder': _build_pie_chart
    },
    'heatmap': {
        'adapter': _adapt_heatmap,
        'builder': _build_heatmap_chart
    },
}
```

#### 统一入口

```python
@staticmethod
def chart(chart_type: str, data, height: str = '400px', **kwargs) -> Cell:
    spec = CHART_REGISTRY.get(chart_type)
    if not spec:
        raise ValueError(f"不支持的图表类型: {chart_type}")
    
    # 1. 数据适配
    adapted_data = spec['adapter'](data)
    
    # 2. 图表构建
    series_opts = kwargs.pop('series_opts', {})
    chart = spec['builder'](adapted_data, series_opts)
    
    # 3. 全局配置
    global_opts_keys = ['title_opts', 'legend_opts', 'tooltip_opts',
                        'xaxis_opts', 'yaxis_opts', 'datazoom_opts',
                        'visualmap_opts', 'grid_opts']
    global_opts = {k: kwargs.pop(k) for k in global_opts_keys if k in kwargs}
    
    if global_opts:
        chart.set_global_opts(**{k: _create_opts(k, v) for k, v in global_opts.items()})
    
    # 4. 输出
    option_dict = json.loads(chart.dump_options())
    return Cell(CellType.CHART, {"charts": option_dict, "width": kwargs.get('width', '100%'), "height": height})
```

### J.4 扩展新图表类型

#### 情况1：XY 轴系列（最简单）

```python
# 只需加一行
CHART_REGISTRY['scatterGL'] = {
    'class': ScatterGL,
    'adapter': _adapt_passthrough,
    'builder': lambda d, opts: _build_xy_chart(ScatterGL, d, opts)
}
```

#### 情况2：特殊格式（需要适配器）

```python
# 1. 写适配器
def _adapt_radar(data):
    """雷达图适配"""
    return data  # 或自定义转换

# 2. 写构建器
def _build_radar_chart(adapted_data, series_opts):
    from pyecharts.charts import Radar
    chart = Radar()
    chart.add_schema(schema=adapted_data['schema'])
    for s in adapted_data['series']:
        chart.add(s['name'], s['data'], **series_opts)
    return chart

# 3. 注册
CHART_REGISTRY['radar'] = {
    'adapter': _adapt_radar,
    'builder': _build_radar_chart
}
```

### J.5 方案对比

| 维度 | 当前 if-elif | 插件注册表 |
|------|-------------|-----------|
| 扩展 XY 类型 | 改 if 条件 | 加一行注册 |
| 扩展特殊类型 | 加 elif 分支 | 加适配器 + 构建器 + 注册 |
| 数据转换逻辑 | 混在构建器里 | 独立适配器 |
| 类型一目了然 | ❌ 需看代码 | ✅ 看注册表 |
| 与前端架构一致 | ❌ 不一致 | ✅ 一致 |

### J.6 设计优势

| 优势 | 说明 |
|------|------|
| **职责分离** | 数据适配、图表构建、全局配置各司其职 |
| **扩展简单** | 新增类型只需注册，无需修改核心代码 |
| **与前端一致** | 前端有 chartPlugins，后端有 CHART_REGISTRY |
| **易于维护** | 每个类型的适配器和构建器独立 |

---

### J.4 重构方案二：简化注册表模式（推荐）

#### 核心思路

**不过度分离**：
- 5种图表（line/bar/area/scatter/kline）：无需 adapter，直接用统一 builder
- 2种特殊图表（pie/heatmap）：转换 + 构建合并在一个函数里

#### 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        简化注册表模式流程                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  chart(chart_type, data)                                                     │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────┐                                                         │
│  │ 查表获取配置     │                                                         │
│  │ CHART_REGISTRY   │                                                        │
│  └─────────────────┘                                                         │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────┐                                                         │
│  │ 图表构建器       │                                                         │
│  │ builder(...)    │                                                         │
│  │ (转换+构建合并)  │                                                         │
│  └─────────────────┘                                                         │
│         │                                                                    │
│         ▼                                                                    │
│  pyecharts 图表对象                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 注册表定义

```python
CHART_REGISTRY = {
    # ---------- 通用 XY 轴系列（统一处理）----------
    'line': {
        'class': Line,
        'builder': lambda data, opts: _build_xy_chart(Line, data, opts)
    },
    'bar': {
        'class': Bar,
        'builder': lambda data, opts: _build_xy_chart(Bar, data, opts)
    },
    'area': {
        'class': Line,
        'builder': lambda data, opts: _build_xy_chart(Line, data, opts, is_area=True)
    },
    'scatter': {
        'class': Scatter,
        'builder': lambda data, opts: _build_xy_chart(Scatter, data, opts)
    },
    'kline': {
        'class': Kline,
        'builder': lambda data, opts: _build_xy_chart(Kline, data, opts)
    },
    
    # ---------- 特殊类型（转换+构建合并）----------
    'pie': {
        'class': Pie,
        'builder': _build_pie
    },
    'heatmap': {
        'class': HeatMap,
        'builder': _build_heatmap
    },
}
```

#### 通用构建器

```python
def _build_xy_chart(ChartClass, data, series_opts, is_area=False):
    """通用 XY 轴图表构建器（转换+构建合并）"""
    from pyecharts import options as opts
    chart = ChartClass()
    chart.add_xaxis(data['xAxis'])
    for s in data['series']:
        params = {'series_name': s.get('name', ''), 'y_axis': s['data'], **series_opts}
        if is_area:
            params['areastyle_opts'] = opts.AreaStyleOpts(opacity=0.3)
        chart.add_yaxis(**params)
    return chart
```

#### 特殊构建器（转换+构建合并）

```python
def _build_pie(data, series_opts):
    """饼图构建器（转换+构建合并）"""
    from pyecharts.charts import Pie
    chart = Pie()
    data_pair = [(item['name'], item['value']) for item in data]  # 转换
    chart.add('', data_pair, **series_opts)  # 构建
    return chart
```

#### 统一入口

```python
@staticmethod
def chart(chart_type: str, data, height: str = '400px', **kwargs) -> Cell:
    width = kwargs.pop('width', '100%')
    
    # 1. 查表
    spec = CHART_REGISTRY.get(chart_type)
    if not spec:
        supported = list(CHART_REGISTRY.keys())
        raise ValueError(f"不支持的图表类型: {chart_type}，可用: {supported}")
    
    # 2. 提取参数
    global_opts_keys = ['title_opts', 'legend_opts', 'tooltip_opts',
                        'xaxis_opts', 'yaxis_opts', 'datazoom_opts',
                        'visualmap_opts', 'grid_opts']
    global_opts = {k: kwargs.pop(k) for k in global_opts_keys if k in kwargs}
    series_opts = kwargs.pop('series_opts', {})
    
    # 3. 构建图表
    chart = spec['builder'](data, series_opts)
    
    # 4. 全局配置
    if global_opts:
        chart.set_global_opts(**{k: _create_opts(k, v) for k, v in global_opts.items()})
    
    # 5. 输出
    option_dict = json.loads(chart.dump_options())
    return Cell(CellType.CHART, {"charts": option_dict, "width": width, "height": height})
```

---

### J.5 方案对比

| 维度 | 当前 if-elif | 方案一（适配器+构建器分离） | 方案二（简化注册表，推荐） |
|------|-------------|-------------------------|-----------------------|
| **代码简洁度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **职责分离** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **扩展性** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **易于理解** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **与前端一致** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **过度设计风险** | ❌ 无 | ⚠️ 有 | ❌ 无 |

---

### J.6 最终推荐

| 场景 | 推荐方案 |
|------|---------|
| **当前状态** | 方案二（简化注册表） |
| **需要频繁扩展** | 方案二（简化注册表） |
| **追求极致职责分离** | 方案一（适配器+构建器分离） |

---

### J.7 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| V1.0 | 2026-03-21 | 设计方案：适配器 + 构建器分离 |
| V1.1 | 2026-03-21 | 方案对比：新增简化注册表模式（推荐） |

---

## 附录K：页面布局架构设计

### K.1 问题背景

**需求**：主体内容与目录面板需要作为一个整体居中显示，且目录在滚动时保持固定位置。

**核心挑战**：
- 主体宽度有限制（900px），需要居中
- 目录宽度固定（200px），需要跟随主体
- 滚动时目录需要"粘"在视口顶部
- 响应式：小屏幕时目录需要适配

---

### K.2 方案对比

#### 方案一：Fixed + Calc（Alpine版）

**架构**：
```css
.notebook-container {
    max-width: 900px;
    margin: 0 auto;
}

.toc-panel {
    position: fixed;
    top: 20px;
    right: 20px;
}
```

**特点**：
- 主体独立居中
- 目录脱离文档流，固定在视口右侧
- 目录与主体间距随窗口宽度变化

**问题**：
- 目录位置不稳定，与主体距离不固定
- 响应式处理复杂

---

#### 方案二：Flex + Sticky（推荐）

**架构**：
```css
.notebook-wrapper {
    display: flex;
    justify-content: center;
    gap: 20px;
}

.notebook-container {
    flex: 1;
    max-width: 900px;
}

.toc-panel {
    width: 200px;
    position: sticky;
    top: 20px;
    align-self: flex-start;
}
```

**特点**：
- 目录在文档流内
- 滚动时自动"粘"在顶部
- 间距恒定（gap: 20px）

**优势**：
- 代码简洁，无需复杂计算
- 目录与主体相对位置固定
- 响应式处理简单

---

#### 方案三：Grid + Sticky（最终选择）

**架构**：
```css
.notebook-wrapper {
    display: grid;
    grid-template-columns: minmax(300px, 900px) 200px;
    gap: 20px;
    justify-content: center;
    padding: 20px;
}

.toc-panel {
    position: sticky;
    top: 20px;
    align-self: start;
}
```

**特点**：
- Grid 二维布局，适合固定列宽
- `justify-content: center` 整体居中
- `minmax(300px, 900px)` 主体自适应

**优势**：
- 语义清晰：两列布局
- 列宽控制精确
- 代码最简洁

---

### K.3 方案对比表

| 方面 | Fixed+Calc | Flex+Sticky | Grid+Sticky |
|------|-----------|-------------|-------------|
| 代码复杂度 | 高 | 低 | **最低** |
| 目录位置稳定性 | ❌ 随窗口变化 | ✅ 恒定 | ✅ 恒定 |
| 滚动固定 | ✅ | ✅ | ✅ |
| 响应式处理 | 复杂 | 简单 | **简单** |
| 语义清晰度 | 低 | 中 | **高** |
| 浏览器兼容性 | 最佳 | 好 | 好（IE11+） |

---

### K.4 最终选择：Grid + Sticky

**选择理由**：

1. **场景匹配**：主体有上限宽度、目录固定宽度，这是典型的"固定列宽"场景，Grid 更合适

2. **代码简洁**：
   - `justify-content: center` 一行实现整体居中
   - `grid-template-columns` 清晰定义列宽
   - 无需额外的 flex 属性控制

3. **响应式友好**：
   ```css
   @media (max-width: 1140px) {
       .notebook-wrapper {
           grid-template-columns: 1fr;
           max-width: 900px;
       }
       .toc-panel {
           position: relative;
           order: -1;
       }
   }
   ```

4. **目录行为可控**：
   - `sticky` 实现滚动固定
   - `align-self: start` 让目录高度自适应
   - 文档流内，不影响主体布局

---

### K.5 完整实现

```css
:root {
    --toc-width: 200px;
    --toc-gap: 20px;
    --container-max-width: 900px;
}

.notebook-wrapper {
    display: grid;
    grid-template-columns: minmax(300px, var(--container-max-width)) var(--toc-width);
    gap: var(--toc-gap);
    justify-content: center;
    padding: 20px;
}

.notebook-container {
    min-width: 0;
}

.toc-panel {
    position: sticky;
    top: 20px;
    align-self: start;
    max-height: calc(100vh - 40px);
    overflow-y: auto;
}

/* 响应式：空间不足时目录移到底部 */
@media (max-width: 1140px) {
    .notebook-wrapper {
        grid-template-columns: 1fr;
        max-width: var(--container-max-width);
    }
    .toc-panel {
        position: relative;
        top: auto;
        max-height: none;
        order: -1;
    }
}

/* 小屏幕：目录隐藏或折叠 */
@media (max-width: 768px) {
    .toc-panel {
        display: none;
    }
}
```

---

### K.6 设计决策记录

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 目录是否在文档流内 | ✅ 是 | 间距恒定，代码简洁 |
| 目录定位方式 | `sticky` | 滚动固定，不脱离文档流 |
| 布局模型 | Grid | 固定列宽场景，语义清晰 |
| 响应式策略 | 目录移到底部 | 保留功能，体验好 |
| 主体宽度控制 | `minmax(300px, 900px)` | 最小300px保证可读，最大900px限制宽度 |

---

### K.7 架构图示

```
┌─────────────────────────────────────────────────────┐
│                     body                            │
│  ┌───────────────────────────────────────────────┐  │
│  │           notebook-wrapper (grid)             │  │
│  │  ┌─────────────────────┐ ┌────────────────┐   │  │
│  │  │ notebook-container  │ │   toc-panel    │   │  │
│  │  │ (minmax 300-900px)  │ │   (200px)      │   │  │
│  │  │                     │ │   sticky       │   │  │
│  │  │                     │ │                │   │  │
│  │  └─────────────────────┘ └────────────────┘   │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**关键点**：
- `justify-content: center` 整体居中
- `sticky` 滚动时目录固定在顶部
- `gap: 20px` 主体与目录间距恒定
- 响应式时 `grid-template-columns: 1fr` 单列布局

---

## 附录K：Section 嵌套层级设计规范

### K.1 设计原则

**核心目标**：层级关系清晰，视觉统一，适度紧凑。

**设计哲学**：
- 用**颜色**区分层级（紫→粉红→橙）
- 用**左边框**作为视觉引导线
- 统一的**padding**规范，保持节奏感

---

### K.2 层级定义

| 层级 | 名称 | 颜色 | 用途 |
|------|------|------|------|
| Level 1 | 主章节 | 紫色 #9b51e0 | 报告主要章节 |
| Level 2 | 子章节 | 粉红 #ec4899 | 章节内的分析模块 |
| Level 3 | 孙子章节 | 橙色 #ff9500 | 详细数据/子分析 |

---

### K.3 间距规范 - 化繁为简

#### 核心原则

**Cell 和嵌套 Section 共用基础样式**，只区分颜色和边框。

| 元素 | Padding | Margin | 说明 |
|------|---------|--------|------|
| **Section L1** | 16px 12px | 16px 0 | 主章节，白色卡片 |
| **Cell / L2 / L3** | 16px 12px | 8px 0 | 统一基础样式 |

---

### K.4 完整 CSS 实现 - 简化版

```css
/* ========== Section 层级规范 - 化繁为简 ========== */

/* Section L1: 主章节 - 白色卡片 */
.notion .section {
    border-radius: 6px;
    margin: 16px 0;
    background: #fff;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    border: 1px solid #e9e9e9;
}
.notion .section-title {
    font-size: 15px;
    font-weight: 600;
    padding: 16px 12px;
    background: linear-gradient(90deg, #fafafa 0%, #fff 100%);
    border-radius: 6px 6px 0 0;
    color: #37352f;
}
.notion .section-content {
    padding: 16px 12px;
}

/* 基础容器 - Cell 和嵌套 Section 统一 */
.notion .cell,
.notion .nested-section {
    padding: 16px 12px;
    margin: 8px 0;
    border-radius: 6px;
}

/* Cell - 米色背景 */
.notion .cell {
    background: #f7f6f3;
}

/* Level 2 - 紫色 */
.notion .nested-section {
    border-left: 4px solid #9b51e0;
    background: #faf9f7;
}
.notion .nested-section .section-title {
    background: transparent;
    font-size: 14px;
    color: #6b5b95;
    padding: 0 0 12px 0;
}
.notion .nested-section .section-content {
    padding: 0;
}

/* Level 3 - 粉红 */
.notion .nested-section .nested-section {
    border-left-color: #ec4899;
    background: #fdf2f8;
}
.notion .nested-section .nested-section .section-title {
    font-size: 14px;
    color: #be185d;
    padding: 0 0 8px 0;
}
```

**简化要点**：
- Cell 和 nested-section 共用 `padding: 16px 12px` 和 `margin: 8px 0`
- 只通过颜色和边框区分类型
- 大红大紫，简洁明了

---

### K.5 视觉层级示意

```
┌─────────────────────────────────┐
│ Level 1: 主章节                  │
│ margin: 16px 0                   │
│ padding: 16px 12px               │
│ 白色卡片 + 阴影                   │
│ ┌─────────────────────────────┐ │
│ │ Level 2: 子章节              │ │
│ │ margin: 8px 0                │ │
│ │ padding: 16px 12px           │ │
│ │ 紫色左边框                    │ │
│ │ ┌─────────────────────────┐ │ │
│ │ │ Level 3: 孙子章节        │ │ │
│ │ │ margin: 8px 0            │ │ │
│ │ │ padding: 16px 12px       │ │ │
│ │ │ 粉红色左边框              │ │ │
│ │ └─────────────────────────┘ │ │
│ └─────────────────────────────┘ │
└─────────────────────────────────┘
```

---

### K.6 设计决策记录

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 层级区分方式 | 颜色 + 左边框 | 视觉清晰，有品牌特色 |
| Padding 方向 | 上下 > 左右 | 内容垂直排列，需要更多垂直空间 |
| 嵌套缩进 | 无缩进，左对齐 | 避免内容区域过窄，保持整洁 |
| Section 间距 | L1: 16px, L2/L3: 8px | 章节分隔明显，嵌套紧凑 |
| 背景色 | 灰度渐变 | 不干扰内容，突出边框色 |

---

### K.7 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| V5.3 | 2026-03-06 | 添加附录K：Section 嵌套层级设计规范 |

---

### K.8 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| V5.2 | 2026-03-05 | 添加附录J：页面布局架构设计 |
| V5.3 | 2026-03-06 | 添加附录K：Section 嵌套层级设计规范 |

---

## 附录L：Ft-Table 组件架构设计规范

### L.1 核心设计原则

**职责清晰分离，避免样式冲突：**
```
┌─────────────────────────────────────────────────────────┐
│  Ft-Table 组件架构                                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  组件注入样式（ft-table.js）             ← 核心功能    │
│  ├── position: sticky                               │
│  ├── z-index 层级配置 (10, 50, 100)                │
│  ├── overflow-x: auto                                │
│  ├── border-collapse: separate                       │
│  └── box-shadow (冻结列阴影)                          │
│                                                         │
│  外部 CSS（notebook.css）                ← 视觉样式    │
│  ├── 背景色、文字色                                  │
│  ├── padding、margin                                  │
│  ├── border-radius                                     │
│  ├── hover 效果                                        │
│  ├── white-space: nowrap                              │
│  └── min-width: 80px                                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### L.2 组件注入样式（ft-table.js）

**核心功能配置：**

```css
/* 只负责冻结功能的核心逻辑 */
.ft-table-freeze {
  overflow-x: auto;
  position: relative;
}

.ft-table-freeze .freeze-col {
  position: sticky;
}

.ft-table-freeze thead th {
  position: sticky;
  top: 0;
  z-index: 10;
}

.ft-table-freeze thead .freeze-col {
  z-index: 100;
}

.ft-table-freeze tbody .freeze-col {
  z-index: 50;
}

.ft-table-freeze .ft-table {
  border-collapse: separate;
  border-spacing: 0;
}

.ft-table-freeze .freeze-left {
  box-shadow: 2px 0 4px rgba(0, 0, 0, 0.1);
}

.ft-table-freeze .freeze-right {
  box-shadow: -2px 0 4px rgba(0, 0, 0, 0.1);
}
```

**设计原则：**
- ✅ 只包含冻结功能必须的样式
- ✅ 不包含任何视觉样式（颜色、背景等）
- ✅ z-index 层级由组件统一管理
- ✅ 避免与外部 CSS 产生冲突

### L.3 外部 CSS（notebook.css）

**视觉样式配置：**

```css
/* 只负责视觉效果，不涉及核心功能 */
.ft-table-freeze .ft-table th,
.ft-table-freeze .ft-table td {
  white-space: nowrap;
  min-width: 80px;
}

/* 表体单元格背景色 */
.ft-table-freeze .ft-table tbody td {
  background: white;
}

/* 表头冻结 - 白色背景 */
.ft-table-freeze thead th {
  background: #fff;
}

.ft-table-freeze tbody .freeze-col {
  background: white;
}

.ft-table-freeze tbody tr:hover .freeze-col {
  background: #f7f6f3 !important;
}
```

**设计原则：**
- ✅ 只包含视觉相关样式
- ✅ 可以安全修改颜色、背景等
- ✅ 不影响组件核心功能
- ✅ 与组件注入样式职责清晰分离

### L.4 层级管理原则

**Z-Index 层级规范：**

| 层级 | 值 | 元素 | 说明 |
|------|----|------|------|
| 最底层 | 1 | 普通 tbody td | 普通表格单元格 |
| | 10 | thead th | 表头（固定顶部） |
| | 50 | tbody .freeze-col | 冻结列（左右固定） |
| 最顶层 | 100 | thead .freeze-col | 冻结列的表头（固定 + 冻结） |

**层级优先级：**
```
thead.freeze-col (100) > thead (10) > tbody.freeze-col (50) > tbody (1)
```

### L.5 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| V1.0 | 2026-03-07 | 建立架构规范：组件注入 vs 外部 CSS 职责分离 |

---

## 附录M：CSS 与 ECharts 冲突案例分析

### M.1 问题背景

**时间**：2026-03-09
**场景**：重构 `notebook-vue3.js` 中的 tooltip 配置，尝试删除重复的自定义样式，改用 ECharts 默认样式
**结果**：tooltip 显示异常（尺寸过大、样式错乱）

### M.2 冲突原因分析

#### 冲突点 1：宽泛的 CSS 选择器

**问题代码**（`template/js/notebook.css`）：
```css
/* 危险：匹配所有带 z-index 的 div，包括 ECharts tooltip */
div[style*='z-index'] {
    line-height: normal;
    color: initial;
}
```

**影响**：
- ECharts tooltip 有 `z-index` 样式，被此选择器匹配
- 强制设置了 `line-height: normal` 和 `color: initial`
- 破坏了 ECharts 默认的 tooltip 样式

#### 冲突点 2：子元素全匹配选择器

**问题代码**（`template/js/notebook.css`）：
```css
/* 危险：匹配 .chart-container 下所有子 div */
.chart-container > div,
.pyecharts-container > div {
    width: 100% !important;
    height: 100% !important;
}
```

**影响**：
- ECharts 初始化后会创建多个 div（主容器、tooltip、legend 等）
- 此选择器匹配了所有子 div，包括 tooltip 容器
- 强制设置 `width: 100% !important; height: 100% !important`
- 导致 tooltip 尺寸异常大（占满整个图表容器）

### M.3 解决方案

#### 修复 1：精确匹配 ECharts 实例

**修复后代码**：
```css
/* 只针对 ECharts 图表容器，不影响 tooltip */
[class*='echarts-instance'],
[class*='_echarts_instance'] {
    line-height: normal;
    color: initial;
}
```

**改进点**：
- 使用类名属性选择器，只匹配 ECharts 主容器
- 不匹配 tooltip 等其他元素

#### 修复 2：只匹配第一个子元素

**修复后代码**：
```css
/* 只针对第一层子元素，不影响 tooltip */
.chart-container > div:first-child,
.pyecharts-container > div:first-child {
    width: 100% !important;
    height: 100% !important;
}
```

**改进点**：
- 使用 `:first-child` 伪类，只匹配 ECharts 主容器
- tooltip、legend 等其他元素是后续添加的，不受影响
- 既保证了图表尺寸正确，又不干扰其他元素

### M.4 经验教训

#### ❌ 避免使用的 CSS 选择器

| 类型 | 示例 | 风险 |
|------|------|------|
| 属性包含选择器 | `div[style*='xxx']` | 匹配所有带该样式的元素，包括第三方库动态生成的元素 |
| 子元素全匹配 | `.container > div` | 匹配所有子 div，可能包含动态生成的组件内部元素 |
| 全局标签选择器 | `div { ... }` | 影响所有 div，包括第三方组件 |
| 宽泛的类名匹配 | `[class*='xxx']` | 可能匹配到意外的元素 |

#### ✅ 推荐做法

| 类型 | 示例 | 说明 |
|------|------|------|
| 精确类名选择器 | `.my-component` | 只匹配特定组件 |
| 伪类限定 | `:first-child` | 只匹配第一个子元素 |
| 特定类名匹配 | `[class*='echarts-instance']` | 只匹配特定类名（需确保唯一性） |
| 子元素限定 | `.parent > .child` | 明确指定子元素的类名 |

### M.5 最佳实践

**当与第三方库（ECharts、Element UI 等）共存时**：

1. **避免使用属性选择器匹配样式**
   - ❌ `div[style*='position: absolute']`
   - ❌ `div[style*='z-index']`

2. **避免宽泛的子元素选择器**
   - ❌ `.container > div`
   - ❌ `.container > *`

3. **使用精确的类名或伪类限定**
   - ✅ `.container > div:first-child`
   - ✅ `.container > .specific-class`

4. **为第三方库容器添加特定类名**
   - 在 HTML 中明确标记第三方库容器
   - 通过特定类名控制，而非依赖第三方库的内部结构

### M.6 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| V1.0 | 2026-03-09 | 添加 CSS 与 ECharts 冲突案例分析 |
