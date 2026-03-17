# FT Table 组件说明书

## 版本信息

- **当前版本**: v1.5.20260316-1
- **版本号说明**: 主版本.次版本.日期(YYYYMMDD)-修订号

### 版本历史

| 版本 | 更新内容 |
|------|----------|
| v1.3 | 新增热力图功能（heatmap） |
| v1.3.20260313-1 | 优化：热力图单元格禁用正负颜色类，避免字体颜色与背景色冲突 |
| v1.4 | 重构分页参数：新增 page 参数，pagination 降级为兼容 |
| v1.5 | 新版 page 参数优先，pagination 后期移除 |
| v1.5.20260316-1 | 优化：悬停滚动按钮逻辑，隐藏延迟调整为1.5秒，滚动步长120px，新增移动阈值检测 |
| v1.5.20260316-2 | 新增：scrollButton 参数可禁用悬停滚动按钮功能 |

---

## 一、组件概述

FT Table 是一个基于 Vue 3 组合式 API 的表格组件，支持以下核心功能：

- ✅ 数据展示与格式化
- ✅ 多列排序（支持多列优先级排序）
- ✅ 分页功能（支持自定义每页条数）
- ✅ 冻结列（左右冻结）
- ✅ 热力图（支持列级别和全局配置）
- ✅ 自定义插槽
- ✅ 响应式设计

---

## 二、快速开始

### 1. 基础用法

```javascript
// 1. 定义数据
const tableData = [
  { code: "001", name: "苹果", price: 5.80 },
  { code: "002", name: "香蕉", price: 3.20 }
];

// 2. 定义列（支持两种格式）
// 格式 A：字符串数组
const cols1 = ["代码", "名称", "价格"];

// 格式 B：对象数组（推荐）
const cols2 = [
  { field: "code", title: "代码" },
  { field: "name", title: "名称" },
  { field: "price", title: "价格", sort: false }
];
```

```html
<!-- 3. 模板使用 -->
<ft-table 
  :data="tableData" 
  :cols="cols"
  :page="{ size: 20 }"
  :freeze="{ left: 2 }"
></ft-table>
```

---

## 三、Props 参数明细

### 3.1 基础参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `data` | `Array` | `[]` | **必需**，表格数据源 |
| `cols` | `Array` | `[]` | **必需**，列配置数组 |
| `page` | `Object \| Boolean` | `{ size: 10, options: [10, 20, 50, 100] }` | 新版分页配置（推荐），`false` 禁用分页 |
| `pagination` | `Object \| Boolean` | `false` | 旧版分页配置（兼容，后期移除） |
| `freeze` | `Object` | `{ left: 0, right: 0 }` | 冻结列配置 |
| `heatmap` | `Object \| Boolean` | `false` | 热力图配置 |
| `emptyText` | `String` | `'暂无数据'` | 空数据提示文本 |
| `resetPage` | `Boolean` | `true` | 数据变化时是否自动重置到第一页 |
| `scrollButton` | `Boolean` | `true` | 是否启用悬停滚动按钮功能，`false` 禁用 |

### 3.2 列配置（cols）详解

列配置支持两种格式：

#### 格式 A：字符串数组（简写形式）
```javascript
const cols = ["代码", "名称", "价格"];
// 自动转换为：field=标题, title=标题, slot=cell-标题
```

#### 格式 B：对象数组（完整形式）

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `field` | `String` | - | **必需**，字段名 |
| `title` | `String` | - | **必需**，列标题 |
| `sort` | `Boolean` | `true` | 是否可排序，`false` 禁用 |
| `width` | `Number` | - | 列宽度（可选） |
| `slot` | `String` | `cell-{field}` | 自定义插槽名称（可选） |
| `heatmap` | `Object` | - | 列级别热力图配置（可选） |

#### 列配置示例

```javascript
const cols = [
  // 基础列
  { field: 'name', title: '名称', sort: false, width: 120 },
  
  // 带热力图的列（独立色阶）
  { field: 'change', title: '涨跌幅', heatmap: {} },
  
  // 分组热力图（多列共享色阶）
  { field: 'c1', title: 'C 列', heatmap: { group: 'g1' } },
  { field: 'c2', title: 'D 列', heatmap: { group: 'g1' } },  // 与 C 列共享范围
  
  // 自定义颜色热力图
  { field: 'score', title: '分数', heatmap: { colors: ['#e8f5e9', '#1b5e20'] } }
];
```

---

## 四、功能详解

### 4.1 分页配置（page）

#### 新版 page 参数（推荐）

```javascript
// 不传参数 - 默认分页，每页 10 条
<ft-table :data="data" :cols="cols"></ft-table>

// 启用分页，每页 20 条
<ft-table :data="data" :cols="cols" :page="{ size: 20 }"></ft-table>

// 启用分页，自定义每页条数选项
<ft-table :data="data" :cols="cols" :page="{ size: 20, options: [10, 20, 50, 100] }"></ft-table>

// 禁用分页
<ft-table :data="data" :cols="cols" :page="false"></ft-table>
```

#### page 配置对象属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `size` | `Number` | `10` | 每页显示条数 |
| `options` | `Array` | `[10, 20, 50, 100]` | 每页条数选项 |

#### 旧版 pagination 参数（兼容，后期移除）

```javascript
// 启用分页，每页 20 条
<ft-table :data="data" :cols="cols" :pagination="{ pageSize: 20 }"></ft-table>

// 自定义每页条数选项
<ft-table :data="data" :cols="cols" :pagination="{ pageSize: 20, pageSizeOptions: [10, 20, 50, 100] }"></ft-table>
```

---

### 4.2 冻结列（freeze）

冻结列功能允许固定表格的左侧或右侧列，在水平滚动时保持可见。

```javascript
// 冻结左侧 2 列
<ft-table :freeze="{ left: 2 }"></ft-table>

// 冻结右侧 1 列
<ft-table :freeze="{ right: 1 }"></ft-table>

// 同时冻结左右
<ft-table :freeze="{ left: 2, right: 1 }"></ft-table>
```

#### freeze 配置对象属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `left` | `Number` | `0` | 冻结左侧列数 |
| `right` | `Number` | `0` | 冻结右侧列数 |

#### 悬停滚动按钮逻辑

当表格内容超出容器宽度时，组件提供悬停触发的浮动滚动按钮，方便用户快速左右滚动。

**功能控制：**

```javascript
// 默认开启（不传或传 true）
<ft-table :data="data" :cols="cols" />

// 禁用悬停滚动按钮
<ft-table :data="data" :cols="cols" :scroll-button="false" />
```

**触发逻辑：**

| 事件 | 行为 | 延迟 | 说明 |
|------|------|------|------|
| `mouseenter` 进入表格 | 启动显示计时器 | 2秒 | 悬停 2 秒后显示滚动按钮 |
| `mouseleave` 离开表格 | 清除显示计时器 | - | 如果未满 2 秒，取消显示 |
| `mousemove` 在表格内移动 | 更新按钮位置 | - | 按钮实时跟随鼠标位置 |

**消失逻辑：**

| 事件 | 行为 | 延迟 | 说明 |
|------|------|------|------|
| `mouseleave` 离开表格 | 启动隐藏计时器 | 1.5秒 | 离开表格 1.5 秒后隐藏按钮 |
| `mouseenter` 进入按钮 | 清除隐藏计时器 | - | 鼠标移入按钮时保持显示 |
| `mousemove` 移动超过阈值 | 启动隐藏计时器 | 1.5秒 | 移动超过 25px 且不在按钮上时触发 |

**状态流转图：**

```
┌─────────────┐     mouseenter      ┌─────────────┐
│   等待状态   │ ──────────────────→ │  等待显示    │
│  (waiting)  │   (启动2s计时器)     │  (waiting)  │
└─────────────┘                     └──────┬──────┘
       ↑                                   │
       │ mouseleave                        │ 2秒到
       │ (如果未显示则清除计时器)            ↓
       │                            ┌─────────────┐
       │                            │   显示状态   │
       │                            │  (visible)  │
       │                            └──────┬──────┘
       │                                   │
       │ mouseleave                        │ 1.5秒到
       │ (启动1.5s隐藏计时器)               │ (或移动超过阈值)
       │                                   ↓
       │                            ┌─────────────┐
       │                            │  等待隐藏    │
       │                            │  (hiding)   │
       │                            └──────┬──────┘
       │                                   │
       │ 再次进入表格                        │ 1.5秒到
       │ (启动显示计时器)                    │
       │                                   ↓
       │                            ┌─────────────┐
       └────────────────────────────│   等待状态   │
              再次进入表格          │  (waiting)  │
```

**关键实现细节：**

1. **实时位置更新**：按钮显示后仍然跟随鼠标移动，确保鼠标移动到新位置时按钮在正确位置

2. **单计时器机制**：显示和隐藏共用一个 `buttonTimer`，状态转换时自动清除旧计时器

3. **移动阈值检测**：新增 25px 移动阈值，避免误触发隐藏（鼠标轻微抖动不会触发）

4. **防闪烁处理**：鼠标从表格移入按钮区域时，会清除隐藏计时器，确保按钮不会闪烁消失

5. **滚动步长**：每次点击左右按钮滚动 120px

6. **显示时立即隐藏**：按钮显示状态下离开表格，立即启动 1.5 秒隐藏计时器

**相关响应式数据：**

```javascript
const showScrollButtons = ref(false);      // 控制按钮显示/隐藏
const scrollButtonPos = ref({ x: 0, y: 0 }); // 按钮位置（跟随鼠标）
let buttonTimer = null;                     // 单一计时器（显示或隐藏共用）
let btnState = 'waiting';                   // 按钮状态：waiting | visible | hiding
let isOnButton = false;                     // 标记鼠标是否在按钮上
let lastMousePos = { x: 0, y: 0 };          // 上次鼠标位置
const HOVER_DELAY = 2000;                   // 悬停显示延迟（毫秒）
const HIDE_DELAY = 1500;                    // 隐藏延迟（毫秒）
const MOVE_THRESHOLD = 25;                  // 移动阈值（像素）
```

---

### 4.3 热力图（heatmap）

热力图功能通过颜色深浅直观展示数值大小，支持全局配置和列级别配置。

#### 4.3.1 全局热力图配置

```javascript
// 基础用法：从第 2 列开始应用热力图
<ft-table :heatmap="{ start: 2 }"></ft-table>

// 指定列范围（第 2-5 列，1-based，包含 end）
<ft-table :heatmap="{ start: 2, end: 5 }"></ft-table>

// 使用负数索引（第 2 列到倒数第 2 列）
<ft-table :heatmap="{ start: 2, end: -2 }"></ft-table>

// 排除特定列
<ft-table :heatmap="{ start: 2, exclude: [5, 6] }"></ft-table>

// 直接指定列名（优先级最高）
<ft-table :heatmap="{ columns: ['change', 'volume'] }"></ft-table>

// 自定义颜色（2 色或 3 色）
<ft-table :heatmap="{ start: 2, colors: ['#e8f5e9', '#1b5e20'] }"></ft-table>

// 全表统一归一化（便于跨列比较）
<ft-table :heatmap="{ columns: ['open', 'high', 'low', 'close'], axis: 'table' }"></ft-table>

// 排除汇总行（最后一行不参与计算）
<ft-table :heatmap="{ columns: ['amount'], excludeRows: [-1] }"></ft-table>
```

#### 全局 heatmap 配置属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `start` | `Number` | `1` | 起始列索引（1-based）<br>• 正数：从左到右第 N 列<br>• 负数：从右到左计算 |
| `end` | `Number` | `-1` | 结束列索引（1-based）<br>• 正数：从左到右第 N 列<br>• 负数：从右到左计算，如 `-2` 表示倒数第 2 列 |
| `exclude` | `Array` | `[]` | 排除的列索引数组（1-based，支持负数）<br>• `[5, 6]` 排除第 5、6 列<br>• `[-1]` 排除最后一列 |
| `columns` | `Array` | `null` | 直接指定应用热力图的列名数组（优先级最高）<br>• `['change', 'volume']` 仅对这两列应用 |
| `colors` | `Array` | `['#2196f3', '#fff', '#f44336']` | 自定义颜色数组<br>• 2 色：`['#e3f2fd', '#1565c0']` 浅蓝→深蓝<br>• 3 色：`['#2196f3', '#fff', '#f44336']` 蓝→白→红（默认，A 股配色） |
| `axis` | `String` | `'column'` | 归一化方式<br>• `'column'`：每列独立归一化（默认）<br>• `'table'`：全表统一归一化 |
| `excludeRows` | `Array` | `[]` | 排除参与计算的行索引（支持负数）<br>• `[-1]` 排除最后一行（汇总行）<br>• `[0]` 排除第一行<br>• `[-1, -2]` 排除最后两行 |

#### 4.3.2 列级别热力图配置

列级别热力图优先级高于全局热力图。

```javascript
const cols = [
  // 独立色阶，按列归一化，使用默认颜色
  { field: 'change', title: '涨跌幅', heatmap: {} },
  
  // 独立色阶 + 自定义颜色
  { field: 'score', title: '分数', heatmap: { colors: ['#e8f5e9', '#1b5e20'] } },
  
  // 分组色阶 + 默认颜色（多列共享色阶）
  { field: 'c1', title: 'C 列', heatmap: { group: 'g1' } },
  { field: 'c2', title: 'D 列', heatmap: { group: 'g1' } },
  
  // 分组色阶 + 自定义颜色
  { field: 'e1', title: 'E 列', heatmap: { group: 'g2', colors: ['#ffebee', '#c62828'] } },
  { field: 'e2', title: 'F 列', heatmap: { group: 'g2', colors: ['#ffebee', '#c62828'] } }
];
```

#### 列级别 heatmap 配置属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `group` | `String` | 字段名 | 分组名称，相同 group 的列共享色阶 |
| `colors` | `Array` | 全局配置 | 自定义颜色数组（2 色或 3 色） |

#### 4.3.3 颜色配置说明

**2 色渐变**（低→高）：
```javascript
colors: ['#e3f2fd', '#1565c0']  // 浅蓝→深蓝
```

**3 色渐变**（低→中→高）：
```javascript
colors: ['#2196f3', '#fff', '#f44336']  // 蓝→白→红（A 股配色：红涨蓝跌）
```

---

### 4.4 排序功能

FT Table 支持多列排序，按点击顺序形成优先级。

- 单击列头：按该列降序排序
- 再次单击：切换为升序排序
- 第三次单击：取消该列排序
- 多列排序：按住优先级依次点击多列

排序指示器显示：
- `▼` 表示降序
- `▲` 表示升序
- 数字表示排序优先级（1, 2, 3...）

```javascript
// 禁用特定列的排序
const cols = [
  { field: 'name', title: '名称', sort: false },  // 该列不可排序
  { field: 'price', title: '价格' }  // 默认可排序
];
```

---

### 4.5 自定义插槽

FT Table 支持通过插槽自定义单元格内容。

```html
<ft-table :data="tableData" :cols="cols">
  <!-- 自定义代码列 -->
  <template #cell-code="{ row, value, index }">
    <a :href="`/stock/${value}`" class="stock-link">{{ value }}</a>
  </template>
  
  <!-- 自定义涨跌幅列 -->
  <template #cell-change="{ row, value, index }">
    <span :class="value >= 0 ? 'up' : 'down'">
      {{ value >= 0 ? '+' : '' }}{{ value }}%
    </span>
  </template>
</ft-table>
```

#### 插槽参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `row` | `Object` | 当前行数据 |
| `value` | `Any` | 当前单元格值 |
| `index` | `Number` | 当前行索引 |

#### 默认插槽名称

默认插槽名称为 `cell-{field}`，也可以在列配置中自定义：

```javascript
const cols = [
  { field: 'code', title: '代码', slot: 'custom-code' }  // 使用 #custom-code 插槽
];
```

---

## 五、完整案例

### 案例 1：基础表格

```html
<template>
  <ft-table 
    :data="stocks" 
    :cols="cols"
    :page="{ size: 10 }"
  ></ft-table>
</template>

<script>
export default {
  data() {
    return {
      stocks: [
        { code: '000001', name: '平安银行', price: 12.50, change: 2.5 },
        { code: '000002', name: '万科A', price: 15.20, change: -1.2 },
        { code: '000063', name: '中兴通讯', price: 28.60, change: 0.8 }
      ],
      cols: [
        { field: 'code', title: '代码', width: 100 },
        { field: 'name', title: '名称', width: 120 },
        { field: 'price', title: '价格', width: 100 },
        { field: 'change', title: '涨跌幅', width: 100 }
      ]
    };
  }
};
</script>
```

### 案例 2：带热力图的表格

```html
<template>
  <ft-table 
    :data="industryData" 
    :cols="cols"
    :heatmap="heatmapConfig"
    :freeze="{ left: 1 }"
  ></ft-table>
</template>

<script>
export default {
  data() {
    return {
      industryData: [
        { name: '银行', day: 1.2, week: 2.5, month: 5.8, quarter: 8.2 },
        { name: '证券', day: -0.5, week: 1.8, month: 3.2, quarter: 6.5 },
        { name: '保险', day: 0.8, week: 1.5, month: 4.1, quarter: 7.3 }
      ],
      cols: [
        { field: 'name', title: '行业', sort: false, width: 100 },
        { field: 'day', title: '日涨跌', width: 90 },
        { field: 'week', title: '周涨跌', width: 90 },
        { field: 'month', title: '月涨跌', width: 90 },
        { field: 'quarter', title: '季涨跌', width: 90 }
      ],
      // 从第 2 列开始应用热力图，使用 A 股配色（红涨蓝跌）
      heatmapConfig: {
        start: 2,
        colors: ['#2196f3', '#fff', '#f44336']
      }
    };
  }
};
</script>
```

### 案例 3：分组热力图

```html
<template>
  <ft-table 
    :data="fundData" 
    :cols="cols"
  ></ft-table>
</template>

<script>
export default {
  data() {
    return {
      fundData: [
        { name: '基金A', nav1: 1.2, nav2: 1.25, return1: 5.2, return2: 8.5 },
        { name: '基金B', nav1: 0.95, nav2: 0.98, return1: -2.1, return3: 1.5 }
      ],
      cols: [
        { field: 'name', title: '基金名称', sort: false },
        // 净值列共享色阶
        { field: 'nav1', title: '净值1', heatmap: { group: 'nav' } },
        { field: 'nav2', title: '净值2', heatmap: { group: 'nav' } },
        // 收益率列共享色阶，使用 A 股配色
        { field: 'return1', title: '收益1', heatmap: { group: 'return', colors: ['#2196f3', '#fff', '#f44336'] } },
        { field: 'return2', title: '收益2', heatmap: { group: 'return', colors: ['#2196f3', '#fff', '#f44336'] } }
      ]
    };
  }
};
</script>
```

### 案例 4：带自定义插槽的表格

```html
<template>
  <ft-table 
    :data="stocks" 
    :cols="cols"
    :page="{ size: 20 }"
  >
    <!-- 自定义代码列 -->
    <template #cell-code="{ value }">
      <a :href="`https://quote.eastmoney.com/${value}.html`" target="_blank" class="stock-code">
        {{ value }}
      </a>
    </template>
    
    <!-- 自定义涨跌幅列 -->
    <template #cell-change="{ value }">
      <span :class="['change-tag', value >= 0 ? 'up' : 'down']">
        {{ value >= 0 ? '+' : '' }}{{ value.toFixed(2) }}%
      </span>
    </template>
    
    <!-- 自定义操作列 -->
    <template #cell-action="{ row }">
      <button @click="addToFavorite(row)">收藏</button>
      <button @click="viewDetail(row)">详情</button>
    </template>
  </ft-table>
</template>

<script>
export default {
  data() {
    return {
      stocks: [
        { code: '000001', name: '平安银行', price: 12.50, change: 2.5 },
        { code: '000002', name: '万科A', price: 15.20, change: -1.2 }
      ],
      cols: [
        { field: 'code', title: '代码', width: 100 },
        { field: 'name', title: '名称', width: 120 },
        { field: 'price', title: '价格', width: 100 },
        { field: 'change', title: '涨跌幅', width: 100 },
        { field: 'action', title: '操作', sort: false, width: 120, slot: 'cell-action' }
      ]
    };
  },
  methods: {
    addToFavorite(row) {
      console.log('收藏:', row.name);
    },
    viewDetail(row) {
      console.log('查看详情:', row.name);
    }
  }
};
</script>

<style>
.stock-code {
  color: #1976d2;
  text-decoration: none;
}
.change-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: bold;
}
.change-tag.up {
  color: #f44336;
}
.change-tag.down {
  color: #2196f3;
}
</style>
```

### 案例 5：综合配置

```html
<template>
  <ft-table 
    :data="tableData" 
    :cols="cols"
    :page="{ size: 50, options: [20, 50, 100, 200] }"
    :freeze="{ left: 2, right: 1 }"
    :heatmap="heatmapConfig"
    :resetPage="false"
    emptyText="暂无数据，请稍后重试"
  >
    <template #cell-name="{ value }">
      <strong>{{ value }}</strong>
    </template>
  </ft-table>
</template>

<script>
export default {
  data() {
    return {
      tableData: [],
      cols: [
        { field: 'code', title: '代码', sort: false, width: 100 },
        { field: 'name', title: '名称', sort: false, width: 120 },
        { field: 'open', title: '开盘价', width: 90 },
        { field: 'high', title: '最高价', width: 90 },
        { field: 'low', title: '最低价', width: 90 },
        { field: 'close', title: '收盘价', width: 90 },
        { field: 'volume', title: '成交量', width: 100 },
        { field: 'amount', title: '成交额', width: 120 }
      ],
      heatmapConfig: {
        start: 3,           // 从第 3 列开始
        end: -2,            // 到倒数第 2 列
        colors: ['#2196f3', '#fff', '#f44336'],
        axis: 'column',     // 每列独立归一化
        excludeRows: [-1]   // 排除最后一行（汇总行）
      }
    };
  }
};
</script>
```

---

## 六、样式说明

### 6.1 模板结构

```html
<div class="ft-table-wrapper">
  <div class="ft-table-container">
    <table class="ft-table">
      <thead><tr><th>列标题</th></tr></thead>
      <tbody><tr><td>单元格</td></tr></tbody>
    </table>
  </div>
  <div class="ft-table-pagination">分页器</div>
</div>
```

### 6.2 CSS 类名

| 类名 | 说明 |
|------|------|
| `.ft-table-wrapper` | 表格包装器 |
| `.ft-table-container` | 表格容器 |
| `.ft-table` | 表格主体 |
| `.ft-table-freeze` | 冻结列启用时的容器类 |
| `.freeze-col` | 冻结列单元格 |
| `.freeze-left` | 左侧冻结列 |
| `.freeze-right` | 右侧冻结列 |
| `.heatmap-cell` | 热力图单元格 |
| `.positive` | 正数单元格（非热力图时） |
| `.negative` | 负数单元格（非热力图时） |
| `.sort-indicator` | 排序指示器容器 |
| `.sort-icon` | 排序图标 |
| `.sort-priority` | 排序优先级数字 |
| `.ft-table-pagination` | 分页容器 |
| `.page-btn` | 分页按钮 |
| `.page-btn.active` | 当前页按钮 |
| `.page-info` | 分页信息 |
| `.ft-table-empty` | 空数据提示 |
| `.ft-table-scroll-float` | 悬停滚动按钮容器 |
| `.ft-table-scroll-float.visible` | 按钮可见状态 |

### 6.3 引入样式

组件会自动注入冻结列必需的核心样式，其他样式需要引入外部 CSS 文件：

```html
<!-- 引入完整样式（推荐） -->
<link rel="stylesheet" href="ft-table.css">
```

---

## 七、注意事项

1. **分页参数优先级**: 新版 `page` 参数优先于旧版 `pagination` 参数
2. **热力图优先级**: 列级别热力图配置优先级高于全局热力图配置
3. **冻结列限制**: 冻结列不参与热力图渲染（避免样式冲突）
4. **数据变化**: 默认情况下数据变化会自动重置到第一页，可通过 `resetPage: false` 禁用
5. **空数据处理**: 当 `cols` 为空或无效时，组件会自动从数据推断所有字段

---

## 八、浏览器兼容性

- Chrome 60+
- Firefox 60+
- Safari 12+
- Edge 79+

需要支持 ResizeObserver API（现代浏览器均已支持）。
