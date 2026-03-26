# Notebook 可视化设计方案 V5.0

> 制定时间：2025-02-27
> 修订时间：2026-03-05
> 目标：构建统一、规范、简洁的可视化系统
> 技术方案：Section 模块化布局 + ECharts 图表 + Notion 风格样式
> **渲染架构：Vue3 组合式 API + Jinja2 模板**
> **JSON 规范：content/children 分离，语义清晰**

***

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

| 类型             | 效果             | 用途           |
| -------------- | -------------- | ------------ |
| **Section**    | 卡片容器 + 标题（可折叠） | 模块化分组        |
| **Metrics**    | 指标卡片网格         | 核心数据展示       |
| **Table**      | 数据表格           | 明细数据，支持冻结/分页 |
| **Chart**      | ECharts 图表     | 折线/柱状/饼图/面积图 |
| **Heatmap**    | 热力图            | 月度收益矩阵       |
| **Title/Text** | 标题/文本          | 说明内容         |

***

## 2. 用法标准

### 2.1 基础用法

**链式调用**：`nb.title().text().metrics().export_html()`\
**Section 组织**：`with nb.section():` 上下文管理器，支持嵌套和折叠

### 2.3 ECharts 图表

#### 2.3.1 折线/柱状/面积图

**数据格式**：`{'xAxis': [...], 'series': [{'name': '', 'data': []}]}`

**前端交互**：

- 柱状图：正数红色、负数蓝色，自动区分
- 面积图：渐变色填充效果
- 坐标轴：Y轴自动缩放，留有边距

#### 2.3.2 饼图

**数据格式**：`[{'name': '', 'value': 0}]`\
**前端交互**：显示选项切换（原始数据/百分比/同时显示），右侧面板控制

#### 2.3.3 热力图

**数据格式**：DataFrame（第一列=X轴，其余列=Y轴）\
**前端交互**：数据缩放（×1000\~1/100），自动调整颜色映射

#### 2.3.4 图表参数

| 参数           | 类型        | 必填 | 说明                                  |
| ------------ | --------- | -- | ----------------------------------- |
| `chart_type` | str       | ✅  | 'line'/'bar'/'area'/'pie'/'heatmap' |
| `data`       | dict/list | ✅  | 图表数据，格式见各类型说明                       |
| `title`      | str       | ❌  | 图表标题                                |
| `height`     | int       | ❌  | 图表高度（像素），默认 400                     |
| `width`      | int       | ❌  | 图表宽度（像素），默认自适应                      |

### 2.4 表格

**数据格式**：`List[dict]` 或 DataFrame\
**关键参数**：`columns`（列配置）、`freeze`（冻结列）、`page`（分页）

### 2.5 指标卡片

**数据格式**：`[{'name': '', 'value': '', 'desc': ''}]`\
**关键参数**：`columns`（每行列数，默认4）

***

***

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

**核心原则**：`content`/`children` 分离

- 原子类型（table/chart/metrics）：有 `content`，无 `children`
- 容器类型（section）：有 `children`，无 `content`

### 3.3 渲染组件

**CellRenderer**：根据 `type` 递归渲染，Section 类型渲染 children，原子类型渲染 content

### 3.4 图表处理架构

**演进路径**：插件模式（V1.0）→ 策略注册表（实验）→ **组件模式 + Composable（V2.0）**

**当前架构（组件模式）**：

- `useChart()` Composable：统一处理配色、初始化、事件
- 独立组件：PieChart、HeatmapChart、StackedChart 等，支持交互控件
- `ChartRenderer` 入口：根据 chartType 路由到对应组件

**设计优势**：

| 特性       | 说明                  |
| -------- | ------------------- |
| **交互支持** | 组件内可定义响应式控件状态       |
| **代码复用** | Composable 统一处理通用逻辑 |
| **职责清晰** | 每个组件只关心特定图表类型       |
| **易于扩展** | 新增类型只需创建组件并注册       |

### 3.5 配色方案

**Notion 风格**：紫罗兰/粉红主题，表格红正绿负

***

## 附录A：完整示例

### A.1 使用模式

**链式调用**：`nb.title().metrics().chart().table().export_html()`\
**Section 组织**：`with nb.section():` 支持嵌套和折叠

### A.2 数据模型

**核心结构**：

```
Notebook
├── title: str
├── createdAt: str
└── children: Cell[]

Cell
├── type: str (section|chart|table|metrics|text|...)
├── title: str (可选)
├── content: Any (原子类型数据)
├── children: Cell[] (容器类型)
└── options: Dict (配置)
```

***

## 附录B：图表数据格式设计

### 设计原则

| 原则               | 说明                                            |
| ---------------- | --------------------------------------------- |
| **贴近 ECharts**   | 使用原生键名（如 `xAxis`），降低学习成本                      |
| **简化输入**         | 省略冗余配置，直接传数据                                  |
| **兼容 pyecharts** | 命名风格相似，便于迁移                                   |
| **一致性优先**        | DataFrame 格式与 `nb.table()` / `print(df)` 保持一致 |

### 核心设计理念：一致性优先

**关键洞察**：`print(df)` 和 `nb.table()` 输出时，索引被丢弃，只显示列。因此 DataFrame 的第一列就是"第一个可见数据列"，这自然适合作为图表的 X 轴。

```
DataFrame 打印输出：
       策略    基准    ← 列名（可见）
0    1.00   1.00    ← 第一列数据（可见）
1    1.05   1.02
2    1.12   1.04
...
↑ 索引被丢弃，不可见
```

**统一规则**：

- `nb.table()` → 丢弃索引，只显示列
- `nb.chart()` → 第一列作为 X 轴，其余列作为 Y 轴/series

### 格式对比

| 图表类型              | pyecharts                     | Notebook 字典格式                                            | Notebook DataFrame 格式 |
| ----------------- | ----------------------------- | -------------------------------------------------------- | --------------------- |
| **line/bar/area** | `add_xaxis()` + `add_yaxis()` | `{'xAxis': [...], 'series': [{'name': '', 'data': []}]}` | 第一列→xAxis，其余列→series  |
| **pie**           | `[(name, value)]`             | `[{'name': '', 'value': 0}]`                             | 第一列→name，第二列→value    |
| **heatmap**       | DataFrame                     | `{y: {x: value}}`                                        | 第一列→xAxis，其余列→yAxis   |

### B.3 设计理念

**核心思想**：DataFrame 格式与 `print(df)` / `nb.table()` 保持视觉一致性。

| 图表类型          | 简化点                          |
| ------------- | ---------------------------- |
| line/bar/area | 第一列→xAxis，无需 reset\_index()  |
| pie           | 第一列→name，第二列→value           |
| heatmap       | 第一列→xAxis，其余列→yAxis，无需手动计算坐标 |

### DataFrame 格式最佳实践

**推荐结构**：

```python
# 折线图/柱状图
df = pd.DataFrame({
    "月份": ["1月", "2月", "3月"],      # ← 第一列 = X 轴
    "策略": [1.0, 1.05, 1.12],           # ← 其余列 = series
    "基准": [1.0, 1.02, 1.04]
})

# 对应字典格式
{
    'xAxis': ["1月", "2月", "3月"],
    'series': [
        {'name': '策略', 'data': [1.0, 1.05, 1.12]},
        {'name': '基准', 'data': [1.0, 1.02, 1.04]}
    ]
}
```

**优势**：

- 数据只定义一次，字典和 DataFrame 共享
- 第一列既用于显示（table），又用于 X 轴（chart）
- 无需 reset\_index()，无需 to\_dict()，自然对应

***

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

#### Cell 数据模型

| 字段         | 含义    | 适用类型                       |
| ---------- | ----- | -------------------------- |
| `type`     | 类型标识  | 所有                         |
| `content`  | 核心数据  | 原子类型（table/chart/metrics等） |
| `children` | 子节点列表 | 容器类型（section）              |
| `title`    | 标题    | 所有（可选）                     |
| `options`  | 展示配置  | 所有（可选）                     |

**类型划分**：

- **原子类型**：有 content，无 children（text/table/chart/metrics等）
- **容器类型**：有 children，无 content（section）

### C.3 设计决策

#### 决策1: options 字段松散是合理的

不同 Cell 类型有各自专属配置：

- `TableCell.options.columns` = 列名列表
- `MetricsCell.options.columns` = 每行显示列数

同名不同义，符合各自业务语义。统一反而增加复杂度。

#### 决策2: Section 自动分类

`_add_cell` 方法三种分支：

| 场景            | 代码                                                  | 效果                     |
| ------------- | --------------------------------------------------- | ---------------------- |
| with 内有 title | `with nb.section("分析"): nb.table(data, title="明细")` | Cell.title = "明细"（小标题） |
| with 外有 title | `nb.table(data, title="基金列表")`                      | **自动创建 Section**       |
| with 外无 title | `nb.text("说明文字")`                                   | 普通 Cell，不包装            |

**核心思想**：用户不用显式创建 Section，给 `title` 参数就自动分组。

**架构设计**：详见附录I - CellBuilder/Notebook 职责分离

***

## 附录D：选择性截图功能

### D.1 功能需求

用户可以在 TOC 面板中勾选需要截图的内容（支持多选），点击"截图选中"按钮后，将选中内容截图并复制到剪贴板。

### D.2 技术挑战

| 挑战            | 说明                                         |
| ------------- | ------------------------------------------ |
| **Vue3 响应式**  | `:class` 绑定变化触发虚拟 DOM 更新，可能导致图表重新渲染        |
| **Canvas 克隆** | `cloneNode()` 无法克隆 Canvas 内容，ECharts 图表会丢失 |
| **布局变化**      | 使用 `display: none` 隐藏元素会触发重排，影响图表尺寸        |

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

| 方案                         | 原理          | 问题                           | 状态       |
| -------------------------- | ----------- | ---------------------------- | -------- |
| ❌ CSS `display: none`      | 隐藏未选中元素     | 触发重排，图表尺寸变化                  | 废弃       |
| ❌ CSS `visibility: hidden` | 隐藏但保留空间     | 占用空白，截图有空白                   | 废弃       |
| ❌ Vue `:class` 绑定          | 响应式更新 class | Vue 虚拟 DOM 更新可能影响图表          | 废弃       |
| ⚠️ DOM 克隆 + 独立容器           | 克隆内容到新容器    | `cloneNode()` 不保留折叠状态、表格滚动位置 | V1.0     |
| ✅ **逐个截图 + Canvas 拼接**     | 直接截图原元素后拼接  | 所见即所得，无需 DOM 克隆              | **V2.0** |

***

## 附录E：技术探索路径（方法论）

### E.1 问题定义

**需求**：Vue3 环境下实现选择性截图（勾选部分内容后截图到剪贴板）

**约束**：

- ECharts 图表必须完整显示
- 折叠/展开状态需同步
- 表格滚动位置需保留
- 不能影响原页面交互

### E.2 探索历程

| 尝试 | 方案                       | 结果 | 原因                |
| -- | ------------------------ | -- | ----------------- |
| 1  | CSS `display: none`      | ❌  | 触发重排，图表尺寸变化       |
| 2  | CSS `visibility: hidden` | ❌  | 占用空白，截图有空白        |
| 3  | Vue `:class` 绑定          | ❌  | Vue 虚拟 DOM 更新影响图表 |
| 4  | 绝对定位移出视口                 | ❌  | 仍需操作 Vue 管理的 DOM  |
| 5  | DOM 克隆 + 独立容器            | ⚠️ | 不保留折叠状态、滚动位置      |
| 6  | **逐个截图 + Canvas 拼接**     | ✅  | 所见即所得，无需克隆        |

### E.3 关键洞察

| 洞察               | 说明                                    |
| ---------------- | ------------------------------------- |
| **避免 Vue 响应式干扰** | 不要通过 `:class` 或数据绑定来控制截图相关样式          |
| **DOM 克隆有局限**    | `cloneNode()` 只克隆 DOM 结构，不克隆组件状态      |
| **直接截图最可靠**      | 对最终渲染结果截图，而非试图重建渲染状态                  |
| **工具各司其职**       | snapdom 处理 HTML→PNG，手动 Canvas 处理拼接和间距 |

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

***

## 附录F：版本记录

| 版本   | 日期         | 说明                                                  |
| ---- | ---------- | --------------------------------------------------- |
| V1   | 2025-02    | 基础 Notebook 系统                                      |
| V2   | 2025-02-19 | Section 模块化，Notion 风格                               |
| V3   | 2025-02-27 | API 极简化，统一 `chart()`                                |
| V3.5 | 2026-03-02 | Alpine 声明式模板                                        |
| V4.0 | 2026-03-03 | 重构文档结构：效果 → Python → Vue3                           |
| V4.1 | 2026-03-03 | **JSON 规范优化**：`content`/`children` 分离               |
| V4.2 | 2026-03-04 | **选择性截图 V1.0**：独立截图容器 + Canvas 手动复制                 |
| V4.3 | 2026-03-04 | **技术讨论**：ctx.drawImage() vs SVG 方案                  |
| V4.4 | 2026-03-04 | **选择性截图 V2.0**：逐个截图 + Canvas 拼接                     |
| V5.0 | 2026-03-05 | **文档重构**：三段式主体 + 六大附录                               |
| V5.1 | 2026-03-05 | **Chart 参数设计**：参数分层 + PyEcharts 规范 + 输出统一           |
| V5.2 | 2026-03-05 | **架构重构**：CellBuilder/Notebook 职责分离 + title 统一处理     |
| V5.3 | 2026-03-07 | **图表布局优化**：饼图/热力图控制面板右浮动，左右布局清晰                     |
| V5.4 | 2026-03-07 | **热力图功能增强**：visualMap 实际数据范围 + 缩放时自动重置选择区间          |
| V5.5 | 2026-03-07 | **ft-table 架构优化**：组件注入样式（核心功能）vs 外部 CSS（视觉样式）职责清晰分离 |
| V5.6 | 2026-03-21 | **图表插件架构**：插件注册模式 + 通用兜底 + 配色统一管理 + tooltip 统一添加    |
| V5.7 | 2026-03-22 | **架构升级**：组件模式 + Composable 复用，替代插件模式，更灵活可扩展         |

***

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
        ├── notebook3C.js    # Vue3 组件（组件模式 + Composable）⭐ 当前使用
        ├── notebook.css     # 样式文件
        ├── vue.global.prod.js
        ├── echarts.min.js
        └── snapdom.min.js   # 截图库
```

***

## 附录H：图表组件架构设计（V2.0 - 组件模式 + Composable）

### H.1 架构演进

```
V1.0 插件模式（notebook3A.js）
    ↓ 问题：插件逻辑分散，难以针对特定图表添加交互控件
    
V2.0 组件模式 + Composable（notebook3C.js）⭐ 当前使用
    ↓ 优势：每个图表独立组件，灵活添加交互，代码复用通过 Composable
```

### H.2 核心设计理念

```
┌─────────────────────────────────────────────────────────────────┐
│                    图表组件架构（V2.0）                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  useChart() Composable                                           │
│  ├── 统一配色获取（getColors）                                   │
│  ├── 统一数据处理（extractData）                                 │
│  ├── 统一图表初始化（initChart）                                 │
│  └── 统一事件监听（resize, colorSchemeChanged）                  │
│                         ↓                                        │
│  图表组件（独立、灵活）                                           │
│  ├── GenericChart    → 通用图表（line/bar/area/scatter）        │
│  ├── PieChart        → 饼图（带显示选项控件）                    │
│  ├── HeatmapChart    → 热力图（带倍数缩放控件）                  │
│  ├── StackedChart    → 堆叠图（带归一化/百分比控件）            │
│  └── GridChart       → 网格图（多个图表组合）                    │
│                         ↓                                        │
│  ChartRenderer（入口组件）                                        │
│  └── 根据 chartType 路由到对应组件                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**核心思路**：组件化 + Composable 复用，每个图表类型独立成组件，灵活添加交互控件。

### H.3 核心实现

**Composable（useChart）**：统一处理配色、初始化、事件监听\
**组件**：通过 `buildOption` 参数定制配置，支持交互控件\
**入口（ChartRenderer）**：根据 `chartType` 路由到对应组件

### H.4 扩展方式

1. 创建组件 → 使用 `useChart()` + 定义控件状态
2. 注册到 `ChartRenderer.components`
3. 在 `chartType` 计算属性中添加类型判断

### H.6 图表类型处理策略

| 图表类型                  | 组件           | 交互控件                    | 配色来源      |
| --------------------- | ------------ | ----------------------- | --------- |
| line/bar/area/scatter | GenericChart | 无                       | 用户可选配色    |
| pie                   | PieChart     | 显示选项（值/百分比）             | 用户可选配色    |
| heatmap               | HeatmapChart | 数据缩放（×1/×10/×100/×1000） | 固定蓝-黄-红渐变 |
| stacked               | StackedChart | 归一化、显示选项                | 用户可选配色    |
| grid                  | GridChart    | 无（简化处理）                 | 用户可选配色    |
| 其他                    | GenericChart | 无                       | 用户可选配色    |

### H.7 架构对比

| 特性       | 插件模式（V1.0） | 组件模式（V2.0）    |
| -------- | ---------- | ------------- |
| **扩展方式** | 注册插件函数     | 创建独立组件        |
| **交互控件** | 难以添加       | 天然支持（Vue 响应式） |
| **代码复用** | 提取公共函数     | Composable    |
| **灵活性**  | 中          | 高             |
| **复杂度**  | 低          | 中             |
| **适用场景** | 简单图表       | 复杂交互图表        |

### H.8 设计优势

| 优势         | 说明                                |
| ---------- | --------------------------------- |
| **灵活性**    | 每个图表独立组件，可自由添加交互控件                |
| **复用性**    | useChart Composable 统一处理配色、初始化、事件 |
| **可维护**    | 组件职责清晰，代码结构直观                     |
| **可扩展**    | 新增图表类型只需创建组件并注册                   |
| **CDN 友好** | 单文件结构，方便 CDN 管理                   |

### H.9 版本记录

| 版本   | 日期         | 变更                                  |
| ---- | ---------- | ----------------------------------- |
| V1.0 | 2026-03-21 | 插件架构：插件注册 + 通用兜底 + 配色统一             |
| V2.0 | 2026-03-22 | **组件架构**：组件化 + Composable 复用，替代插件模式 |

***

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

````

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
````

```javascript
// 前端使用
<div :style="{width: content.width, height: content.height}">
    <!-- ECharts 容器 -->
</div>
```

#### 参数分工

| 参数       | 来源                         | 管理方       |
| -------- | -------------------------- | --------- |
| `charts` | pyecharts `dump_options()` | pyecharts |
| `width`  | Notebook 参数                | 我们        |
| `height` | Notebook 参数                | 我们        |

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

**DataFrame 转换函数**：`df_to_line_bar()`、`df_to_pie()`、`df_to_heatmap()`

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

#### 核心实现（注册表模式）

```python
# CellBuilder.chart() - 查表构建
@staticmethod
def chart(chart_type: str, data, height: str = '400px', **kwargs) -> Cell:
    # 1. 初始化注册表
    _init_chart_registry()
    
    # 2. 查表获取构建器
    spec = CHART_REGISTRY.get(chart_type)
    if not spec:
        raise ValueError(f"不支持的图表类型: {chart_type}")
    
    # 3. 提取参数
    global_opts = {k: kwargs.pop(k) for k in GLOBAL_OPTS_KEYS if k in kwargs}
    series_opts = kwargs.pop('series_opts', {})
    
    # 4. 构建图表
    chart = spec['builder'](data, series_opts)
    
    # 5. 应用全局配置
    if global_opts:
        chart.set_global_opts(**{k: _create_opts(k, v) for k, v in global_opts.items()})
    
    # 6. 输出
    option_dict = json.loads(chart.dump_options())
    return Cell(CellType.CHART, {"charts": option_dict, "width": width, "height": height})
```

**注册表示例**：

```python
CHART_REGISTRY = {
    'line': {'builder': _build_line},
    'bar': {'builder': _build_bar},
    'pie': {'builder': _build_pie},
    'heatmap': {'builder': _build_heatmap},
}
```

#### 构建器函数

| 函数                       | 用途                           |
| ------------------------ | ---------------------------- |
| `_build_line_bar_area()` | 构建 line/bar/area 图表          |
| `_build_pie()`           | 构建饼图                         |
| `_build_heatmap()`       | 构建热力图（支持 DataFrame 自动转换）     |
| `_build_kline()`         | 构建 K 线图                      |
| `_create_opts()`         | 将 dict 转换为 pyecharts opts 对象 |

### H.8 参数传递

| Notebook 参数           | 传递给 pyecharts                                                                         |
| --------------------- | ------------------------------------------------------------------------------------- |
| `title_opts={...}`    | `line.set_global_opts(title_opts=opts.TitleOpts(**title_opts))`                       |
| `yaxis_opts={...}`    | `line.set_global_opts(yaxis_opts=opts.AxisOpts(**yaxis_opts))`                        |
| `series_opts={...}`   | `line.add_yaxis(..., **series_opts)`                                                  |
| `datazoom_opts=[...]` | `line.set_global_opts(datazoom_opts=[opts.DataZoomOpts(**d) for d in datazoom_opts])` |

### H.8 输出格式

`nb.chart()` 和 `nb.pyecharts()` 统一输出 ECharts 标准 JSON 格式

### H.9 前端渲染

Vue3 组件：`echarts.init()` → `setOption(cell.content.charts)` → `resize()` 响应窗口变化

### H.10 方法定位

| 方法               | 定位   | 数据输入                    | 输出      |
| ---------------- | ---- | ----------------------- | ------- |
| `nb.chart()`     | 简化封装 | 简化格式 + pyecharts kwargs | 标准 JSON |
| `nb.pyecharts()` | 透传   | pyecharts 对象            | 标准 JSON |

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

**参数层次**：

1. **基础**：`chart_type`, `data`, `title`（必填）
2. **容器**：`height`, `width`
3. **全局**：`yaxis_opts`, `legend_opts`, `tooltip_opts` 等（pyecharts 规范）
4. **系列**：`series_opts`（统一应用到所有系列）

**高级需求**：直接使用 `nb.pyecharts()` 透传 pyecharts 对象

### H.12 设计优势

| 优势         | 说明                          |
| ---------- | --------------------------- |
| **简化输入**   | 数据格式比 pyecharts 简洁          |
| **复用成熟方案** | 内部使用 pyecharts，无需自己实现转换     |
| **输出标准**   | 完全符合 ECharts 规范             |
| **格式统一**   | chart/pyecharts 输出一致，前端处理简单 |
| **维护简单**   | pyecharts 更新时自动兼容           |

***

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

用户调用 → CellBuilder 构建纯数据 → Notebook.\_add\_cell 处理布局

### I.3 \_add\_cell 逻辑

| 场景            | 代码                                                  | 效果                     |
| ------------- | --------------------------------------------------- | ---------------------- |
| with 内有 title | `with nb.section("分析"): nb.table(data, title="明细")` | Cell.title = "明细"（小标题） |
| with 外有 title | `nb.table(data, title="基金列表")`                      | 自动创建 Section           |
| with 外无 title | `nb.text("说明文字")`                                   | 普通 Cell                |

### I.4 职责分离

| 类               | 职责          | 特点                   |
| --------------- | ----------- | -------------------- |
| **CellBuilder** | 构建 Cell 数据  | 方法不含 `title` 参数      |
| **Notebook**    | 处理布局和 title | 数据/图表类方法含 `title` 参数 |

### I.6 设计优势

| 优势       | 说明                             |
| -------- | ------------------------------ |
| **单一职责** | CellBuilder 只管数据，Notebook 只管布局 |
| **参数简洁** | title 只传一次，不冗余                 |
| **逻辑集中** | title 处理集中在 `_add_cell` 一处     |
| **易于维护** | 新增 Cell 类型只需关注数据构建             |

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

***

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

| 图表类型                        | 用户输入格式                        | pyecharts 需要         | 是否需要转换 |
| --------------------------- | ----------------------------- | -------------------- | ------ |
| line/bar/area/scatter/kline | `{xAxis, series}`             | `{xAxis, series}`    | ❌ 无需转换 |
| pie                         | `[{name, value}]`             | `[(name, value)]`    | ✅ 需要转换 |
| heatmap                     | `{y: {x: value}}` 或 DataFrame | `[[x,y,value], ...]` | ✅ 需要转换 |

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

#### 核心组件

| 组件        | 职责                | 示例                                        |
| --------- | ----------------- | ----------------------------------------- |
| **数据适配器** | 统一输入格式            | `_adapt_pie()`, `_adapt_heatmap()`        |
| **图表构建器** | 创建 pyecharts 对象   | `_build_xy_chart()`, `_build_pie_chart()` |
| **注册表**   | 类型 → 适配器+构建器映射    | `CHART_REGISTRY = {...}`                  |
| **统一入口**  | 查表 → 适配 → 构建 → 输出 | `chart()` 方法                              |

### J.4 扩展方式

| 情况         | 步骤                        | 示例                                    |
| ---------- | ------------------------- | ------------------------------------- |
| **XY 轴系列** | 注册表加一行                    | `CHART_REGISTRY['scatterGL'] = {...}` |
| **特殊格式**   | 1. 写适配器 → 2. 写构建器 → 3. 注册 | radar, heatmap                        |

### J.5 方案对比

| 维度       | 当前 if-elif | 插件注册表           |
| -------- | ---------- | --------------- |
| 扩展 XY 类型 | 改 if 条件    | 加一行注册           |
| 扩展特殊类型   | 加 elif 分支  | 加适配器 + 构建器 + 注册 |
| 数据转换逻辑   | 混在构建器里     | 独立适配器           |
| 类型一目了然   | ❌ 需看代码     | ✅ 看注册表          |
| 与前端架构一致  | ❌ 不一致      | ✅ 一致            |

### J.6 设计优势

| 优势        | 说明                                   |
| --------- | ------------------------------------ |
| **职责分离**  | 数据适配、图表构建、全局配置各司其职                   |
| **扩展简单**  | 新增类型只需注册，无需修改核心代码                    |
| **与前端一致** | 前端有 chartPlugins，后端有 CHART\_REGISTRY |
| **易于维护**  | 每个类型的适配器和构建器独立                       |

***

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

***

### J.5 方案对比

| 维度         | 当前 if-elif | 方案一（适配器+构建器分离） | 方案二（简化注册表，推荐） |
| ---------- | ---------- | -------------- | ------------- |
| **代码简洁度**  | ⭐⭐⭐⭐⭐      | ⭐⭐⭐            | ⭐⭐⭐⭐          |
| **职责分离**   | ⭐⭐         | ⭐⭐⭐⭐⭐          | ⭐⭐⭐⭐          |
| **扩展性**    | ⭐⭐         | ⭐⭐⭐⭐⭐          | ⭐⭐⭐⭐⭐         |
| **易于理解**   | ⭐⭐⭐⭐       | ⭐⭐⭐            | ⭐⭐⭐⭐          |
| **与前端一致**  | ⭐⭐         | ⭐⭐⭐⭐⭐          | ⭐⭐⭐⭐⭐         |
| **过度设计风险** | ❌ 无        | ⚠️ 有           | ❌ 无           |

***

### J.6 最终推荐

| 场景           | 推荐方案           |
| ------------ | -------------- |
| **当前状态**     | 方案二（简化注册表）     |
| **需要频繁扩展**   | 方案二（简化注册表）     |
| **追求极致职责分离** | 方案一（适配器+构建器分离） |

***

### J.7 版本记录

| 版本   | 日期         | 变更                 |
| ---- | ---------- | ------------------ |
| V1.0 | 2026-03-21 | 设计方案：适配器 + 构建器分离   |
| V1.1 | 2026-03-21 | 方案对比：新增简化注册表模式（推荐） |

***

## 附录K：页面布局架构设计

### K.1 最终选择：Flex + Sticky

**当前方案**：

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

.toc-float-menu {
    position: sticky;
    top: 20px;
    width: 40px;  /* 折叠态 */
    /* expanded 时 width: 200px */
}
```

### K.2 选择理由

| 特性            | 说明                                 |
| ------------- | ---------------------------------- |
| **Flex 居中**   | `justify-content: center` 简单实现整体居中 |
| **Sticky 固定** | 目录滚动时"粘"在顶部，不脱离文档流                 |
| **Gap 间距**    | `gap: 20px` 恒定间距，无需计算              |
| **响应式**       | 小屏幕目录自动折叠或隐藏                       |

### K.3 方案对比

| 方案         | 问题                 |
| ---------- | ------------------ |
| **Fixed**  | 目录位置随窗口变化，不稳定      |
| **Grid**   | 代码略复杂，需要定义列宽模板     |
| **Flex** ✅ | 代码简洁，天然一维布局，目录天然跟随 |

**结论**：Flex 适合一维布局（主体 + 目录），代码最简洁，响应式友好。

***

## 附录K：Section 嵌套层级设计规范

### K.1 设计原则

**核心目标**：层级关系清晰，视觉统一，适度紧凑。

**设计哲学**：

- 用**颜色**区分层级（紫→粉红→橙）
- 用**左边框**作为视觉引导线
- 统一的**padding**规范，保持节奏感

***

### K.2 层级定义

| 层级      | 名称   | 颜色         | 用途       |
| ------- | ---- | ---------- | -------- |
| Level 1 | 主章节  | 紫色 #9b51e0 | 报告主要章节   |
| Level 2 | 子章节  | 粉红 #ec4899 | 章节内的分析模块 |
| Level 3 | 孙子章节 | 橙色 #ff9500 | 详细数据/子分析 |

***

### K.3 间距规范 - 化繁为简

#### 核心原则

**Cell 和嵌套 Section 共用基础样式**，只区分颜色和边框。

| 元素                 | Padding   | Margin | 说明       |
| ------------------ | --------- | ------ | -------- |
| **Section L1**     | 16px 12px | 16px 0 | 主章节，白色卡片 |
| **Cell / L2 / L3** | 16px 12px | 8px 0  | 统一基础样式   |

***

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

***

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

***

### K.6 设计决策记录

| 决策点        | 选择                   | 理由              |
| ---------- | -------------------- | --------------- |
| 层级区分方式     | 颜色 + 左边框             | 视觉清晰，有品牌特色      |
| Padding 方向 | 上下 > 左右              | 内容垂直排列，需要更多垂直空间 |
| 嵌套缩进       | 无缩进，左对齐              | 避免内容区域过窄，保持整洁   |
| Section 间距 | L1: 16px, L2/L3: 8px | 章节分隔明显，嵌套紧凑     |
| 背景色        | 灰度渐变                 | 不干扰内容，突出边框色     |

***

### K.7 版本记录

| 版本   | 日期         | 变更                     |
| ---- | ---------- | ---------------------- |
| V5.3 | 2026-03-06 | 添加附录K：Section 嵌套层级设计规范 |

***

### K.8 版本记录

| 版本   | 日期         | 变更                     |
| ---- | ---------- | ---------------------- |
| V5.2 | 2026-03-05 | 添加附录J：页面布局架构设计         |
| V5.3 | 2026-03-06 | 添加附录K：Section 嵌套层级设计规范 |

***

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

### L.2 职责分离原则

| 样式来源                        | 职责   | 示例                                          |
| --------------------------- | ---- | ------------------------------------------- |
| **组件注入** (`ft-table.js`)    | 核心功能 | `position: sticky`, `z-index`, `overflow-x` |
| **外部 CSS** (`notebook.css`) | 视觉样式 | 颜色、背景、hover效果、间距                            |

**核心原则**：

- 组件只注入功能必需的样式（如冻结列的 `sticky` 定位）
- 视觉样式（颜色、背景等）完全由外部 CSS 控制
- 两者职责清晰，避免冲突

### L.4 层级管理原则

**Z-Index 层级规范：**

| 层级     | 值   | 元素                | 说明              |
| ------ | --- | ----------------- | --------------- |
| 最底层    | 1   | 普通 tbody td       | 普通表格单元格         |
| <br /> | 10  | thead th          | 表头（固定顶部）        |
| <br /> | 50  | tbody .freeze-col | 冻结列（左右固定）       |
| 最顶层    | 100 | thead .freeze-col | 冻结列的表头（固定 + 冻结） |

**层级优先级：**

```
thead.freeze-col (100) > thead (10) > tbody.freeze-col (50) > tbody (1)
```

### L.5 版本记录

| 版本   | 日期         | 变更                         |
| ---- | ---------- | -------------------------- |
| V1.0 | 2026-03-07 | 建立架构规范：组件注入 vs 外部 CSS 职责分离 |

***

## 附录M：CSS 最小化设计原则

### M.1 设计背景

**时间**：2026-03-22\
**问题**：早期 CSS 使用宽泛选择器（如 `div[style*='z-index']`、`.chart-container > div`），导致与 ECharts 等第三方库产生冲突\
**解决方案**：重构整个 CSS，遵循最小化原则

### M.2 最小化原则

#### 原则 1：只定义必要的样式

```css
/* ✅ 好的做法：只定义组件必需的样式 */
.cell-chart {
    margin-bottom: 20px;
}

.cell-chart h3 {
    font-size: 16px;
    margin-bottom: 10px;
}

/* ❌ 避免：过度定义，可能覆盖第三方库样式 */
.cell-chart div {
    line-height: normal;  /* 会影响 ECharts */
}
```

#### 原则 2：使用精确的选择器

```css
/* ✅ 好的做法：精确类名 */
.chart-container {
    width: 100%;
    height: 400px;
}

/* ❌ 避免：属性选择器匹配动态生成的元素 */
[style*='z-index'] {
    color: initial;  /* 危险！ */
}
```

#### 原则 3：不假设第三方库的内部结构

```css
/* ✅ 好的做法：只控制容器 */
.chart-wrapper {
    position: relative;
    width: 100%;
}

/* ❌ 避免：匹配第三方库内部元素 */
.chart-container > div:first-child {
    width: 100% !important;  /* 可能破坏 ECharts 布局 */
}
```

### M.3 当前 CSS 结构

```css
/* notebook.css - 最小化设计 */

/* 1. 布局框架 */
.notebook-wrapper { }
.notebook-container { }
.toc-panel { }

/* 2. 单元格基础样式 */
.cell { }
.cell-title { }
.cell-text { }

/* 3. 组件容器（只定义容器，不干预内容） */
.cell-chart { }      /* 图表容器 */
.cell-table { }      /* 表格容器 */
.cell-metrics { }    /* 指标容器 */

/* 4. 控件样式 */
.pie-control { }     /* 饼图控件面板 */
.heatmap-control { } /* 热力图控件面板 */

/* 5. 工具类 */
.text-emphasis { }
.text-warning { }
```

### M.4 与 ECharts 的协作

**不干预原则**：

- CSS 只定义图表容器的大小和位置
- ECharts 内部样式完全由 ECharts 自己管理
- 不覆盖任何 ECharts 生成的类名

```html
<!-- 好的结构 -->
<div class="cell-chart">
    <h3>图表标题</h3>
    <div ref="chartRef" class="chart-container"></div>
    <!-- ECharts 在这里初始化，CSS 不干预内部 -->
</div>
```

### M.5 最佳实践

| 原则                | 说明             | 示例                        |
| ----------------- | -------------- | ------------------------- |
| **最小作用域**         | 样式只作用于明确标记的元素  | `.my-component { }`       |
| **不穿透第三方**        | 不定义第三方库内部元素的样式 | 避免 `.echarts-tooltip { }` |
| **容器控制**          | 只控制容器，不控制内容    | 定义宽高，不定义内部布局              |
| **避免 !important** | 减少样式冲突         | 用特异性代替 `!important`       |

### M.6 经验教训

**早期问题**：

- 宽泛选择器导致与 ECharts 冲突
- 需要不断修复特定选择器
- 维护成本高

**重构后**：

- CSS 文件体积减小 60%
- 与第三方库零冲突
- 维护简单，新增组件无需考虑样式冲突

### M.7 版本记录

| 版本   | 日期         | 变更                       |
| ---- | ---------- | ------------------------ |
| V1.0 | 2026-03-09 | 添加 CSS 与 ECharts 冲突案例分析  |
| V2.0 | 2026-03-22 | **重构为最小化设计原则**，删除所有宽泛选择器 |

***

## 附录N：前端图表架构模式对比

### N.1 三种模式概览

在 Notebook 项目的前端架构演进中，我们尝试了三种不同的图表处理模式：

```
┌─────────────────────────────────────────────────────────────────┐
│                    架构演进路线                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  插件模式（V1.0）                                                │
│  ├── notebook3A.js                                               │
│  └── 问题：难以添加交互控件                                       │
│                         ↓                                        │
│  策略注册表模式（实验）                                           │
│  ├── notebook3B.js                                               │
│  └── 问题：模板个性化控制困难                                     │
│                         ↓                                        │
│  组件模式 + Composable（V2.0）⭐ 最终选择                         │
│  └── notebook3C.js                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### N.2 模式一：插件模式

**文件**：`notebook3A.js`

**核心思想**：

- 统一的 `processChart()` 入口函数
- 通过 `chartPlugins` 注册表分发到各插件
- 插件返回 ECharts 配置对象

**代码结构**：

```javascript
// 插件注册表
const chartPlugins = {
    pie: (extracted, options) => processPie(extracted, options),
    heatmap: (extracted, options) => processHeatmap(extracted, options),
    // ...
};

// 统一处理入口
const processChart = (extracted, options) => {
    const plugin = chartPlugins[chartType];
    const option = plugin ? plugin(extracted, options) : buildGenericOption(extracted, options);
    return option;
};
```

**优点**：

- 代码简洁，逻辑集中
- 新增图表类型只需注册插件

**缺点**：

- ❌ 难以添加交互控件（如 pie 的显示选项、heatmap 的缩放按钮）
- ❌ 插件只能返回配置对象，无法包含 Vue 响应式逻辑
- ❌ 控件状态管理困难

**适用场景**：

- 纯展示型图表，无需交互
- 简单项目，快速开发

***

### N.3 模式二：策略注册表模式

**文件**：`notebook3B.js`（实验性）

**核心思想**：

- 纯策略模式，策略对象包含 `test` 和 `render` 方法
- 通过 `test` 方法自动识别图表类型
- `render` 方法返回 Vue 渲染函数

**代码结构**：

```javascript
// 策略注册表
const chartStrategies = [
    {
        name: 'pie',
        test: (charts) => charts.series?.[0]?.type === 'pie',
        render: (props) => h(PieChart, { cell: props.cell })
    },
    // ...
];

// 自动匹配策略
const matchStrategy = (charts) => {
    return chartStrategies.find(s => s.test(charts)) || genericStrategy;
};
```

**优点**：

- 策略自动识别，无需显式指定类型
- 每个策略独立，易于扩展

**缺点**：

- ❌ 模板个性化控制困难（策略与模板分离）
- ❌ 复杂交互场景下，策略对象变得臃肿
- ❌ 与 Vue 组件化思想不够契合

**适用场景**：

- 需要自动识别图表类型的场景
- 后端标准化输出（如 pyecharts）

**结论**：

> "注册表式，因为涉及到模板个性控制，和 cell.py 的注册交给 pyecharts 标准化输出不同。注册表式，不一定适合。" —— 用户反馈

***

### N.4 模式三：组件模式 + Composable（推荐）

**文件**：`notebook3C.js` ⭐ 当前使用

**核心思想**：

- 每个图表类型独立成 Vue 组件
- 共用逻辑提取到 `useChart()` Composable
- `ChartRenderer` 作为入口组件，根据类型路由

**核心结构**：`useChart()` Composable + 独立组件 + `ChartRenderer` 入口路由

**优点**：

- ✅ 天然支持交互控件（Vue 响应式）
- ✅ 代码复用通过 Composable，避免重复
- ✅ 组件职责清晰，易于维护
- ✅ 与 Vue 生态完全契合
- ✅ 单文件结构，CDN 友好

**缺点**：

- 文件体积略大（但可接受）
- 需要理解 Vue 组合式 API

**适用场景**：

- 复杂交互图表（pie、heatmap、stacked 等）
- 需要个性化控件的场景
- Vue 3 项目

***

### N.5 三种模式对比

| 维度           | 插件模式    | 策略注册表模式 | 组件模式 + Composable |
| ------------ | ------- | ------- | ----------------- |
| **交互控件支持**   | ❌ 困难    | ⚠️ 中等   | ✅ 天然支持            |
| **代码复用**     | ⚠️ 提取函数 | ⚠️ 策略继承 | ✅ Composable      |
| **扩展性**      | ✅ 注册插件  | ✅ 注册策略  | ✅ 创建组件            |
| **与 Vue 契合** | ⚠️ 一般   | ⚠️ 一般   | ✅ 完美契合            |
| **模板控制**     | ⚠️ 有限   | ❌ 困难    | ✅ 完全控制            |
| **学习成本**     | 低       | 中       | 中                 |
| **适用场景**     | 简单展示    | 自动识别    | 复杂交互              |

### N.6 选择建议

| 场景            | 推荐模式                    |
| ------------- | ----------------------- |
| **纯展示图表，无交互** | 插件模式                    |
| **后端标准化输出**   | 策略注册表模式                 |
| **复杂交互控件**    | **组件模式 + Composable** ⭐ |
| **Vue 3 项目**  | **组件模式 + Composable** ⭐ |
| **需要个性化模板**   | **组件模式 + Composable** ⭐ |

### N.7 最终结论

Notebook 项目最终选择 **组件模式 + Composable**，原因：

1. **交互需求**：pie、heatmap、stacked 等图表需要丰富的交互控件
2. **Vue 生态**：与 Vue 3 组合式 API 完美契合
3. **代码复用**：`useChart()` Composable 统一处理配色、初始化、事件
4. **维护性**：组件职责清晰，代码结构直观
5. **CDN 友好**：单文件结构，方便 CDN 管理

```
最终架构：
    useChart() Composable
         ↓
    图表组件（PieChart/HeatmapChart/...）
         ↓
    ChartRenderer 入口组件
         ↓
    CellRenderer 统一渲染
```

### N.8 版本记录

| 版本   | 日期         | 变更             |
| ---- | ---------- | -------------- |
| V1.0 | 2026-03-22 | 添加三种前端架构模式对比分析 |

