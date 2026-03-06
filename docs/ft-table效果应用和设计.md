# FT Table 组件文档

## 简介

基于 Vue 3 的轻量级表格组件，支持数据展示、分页、冻结列等功能。设计目标是**后端友好**（pandas 数据直接输出）和**前端灵活**（插槽模板定制）。

---

## 当前功能

### 1. 基础表格
- 数据展示
- 自动列推断（不传 cols 时自动显示所有字段）
- 自定义列配置

### 2. 分页功能
- 自动分页（数据超过10条）
- 页码切换
- 每页条数选择

### 3. 冻结列
- 左侧冻结
- 右侧冻结

### 4. 单元格插槽
- 自定义渲染
- 操作列支持

---

## 用法规范

### 基础用法

```html
<ft-table 
  :id="'table-1'"
  :data="tableData">
</ft-table>
```

**不传 cols 时**：自动推断所有字段，适合 pandas 数据直接输出

### Props 参数

| 参数 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `id` | String | 是 | 表格唯一标识 |
| `data` | Array | 是 | 表格数据 |
| `cols` | Array | 否 | 列配置，不传时自动推断 |
| `freeze` | Object | 否 | 冻结列配置 |
| `pagination` | Object/Boolean | 否 | 分页配置，false 禁用 |

---

## cols 列配置

### 核心设计

**cols 可选**：
- 不传 → 自动推断所有字段（后端最简，pandas 直接输出）
- 传入有效数组 → 按配置显示指定列

### 格式1：不传（自动推断）

```javascript
// 后端直接输出 pandas 数据
{
  content: [
    { code: '600000', name: '浦发银行', profit: 6.7, amount: 10000 },
    { code: '000001', name: '平安银行', profit: 10.5, amount: 20000 }
  ]
}
```

前端不需要配置 cols，自动显示所有字段。

### 格式2：字符串数组

```javascript
cols: ['代码', '名称', '盈亏']
```

自动从数据中提取对应字段，标题 = 字段名。

### 格式3：对象数组

```javascript
cols: [
  { field: 'code', title: '股票代码' },
  { field: 'name', title: '股票名称' },
  { field: 'profit', title: '收益率' }
]
```

| 属性 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `field` | String | 是 | 数据字段名 |
| `title` | String | 否 | 列标题，默认使用 field |
| `slot` | String | 否 | 插槽名称，默认 `cell-{field}` |

### 格式4：操作列（无 field）

```javascript
cols: [
  { field: 'code', title: '代码' },
  { title: '操作', slot: 'cell-action' }
]
```

操作列不占用数据字段，通过插槽自定义渲染。

---

## freeze 冻结列配置

```javascript
freeze: {
  left: 2,    // 冻结左侧2列
  right: 1    // 冻结右侧1列
}
```

---

## pagination 分页配置

### 自动分页（默认）

数据超过 10 条自动开启分页。

### 自定义分页

```javascript
pagination: {
  pageSize: 20,
  pageSizeOptions: [10, 20, 50, 100]
}
```

### 禁用分页

```javascript
pagination: false
```

---

## 插槽（Slots）

### 单元格模板

通过 `slot` 属性定义插槽名：

```javascript
cols: [
  { field: 'profit', title: '盈亏' },
  { title: '操作', slot: 'cell-action' }
]
```

```html
<ft-table :cols="cols" :data="data">
  <!-- 插槽命名：#cell-{field} -->
  
  <!-- 数据列模板 -->
  <template #cell-profit="{ value, row, index }">
    <span :class="value >= 0 ? 'positive' : 'negative'">
      {{ value }}%
    </span>
  </template>
  
  <!-- 操作列模板 -->
  <template #cell-action="{ row, index }">
    <button @click="edit(row)">编辑</button>
    <button @click="del(row)">删除</button>
  </template>
</ft-table>
```

### 插槽参数

| 参数 | 类型 | 说明 |
|-----|------|------|
| `value` | Any | 当前单元格的值 |
| `row` | Object | 当前行的完整数据 |
| `index` | Number | 当前行索引 |

---

## 完整示例

### 场景1：后端直接输出（最简）

```python
# Python 后端
df = pd.DataFrame(...)
return {'content': df.to_dict(orient='records')}
```

```html
<!-- 前端：不需要配置 cols -->
<ft-table :data="cell.content" />
```

### 场景2：指定显示列

```javascript
{
  type: 'table',
  content: [...],
  options: {
    cols: ['代码', '名称', '盈亏']
  }
}
```

```html
<ft-table :data="cell.content" :cols="cell.options.cols" />
```

### 场景3：自定义渲染

```html
<ft-table :data="cell.content" :cols="getTableCols(cell)">
  <!-- 盈亏列红绿显示 -->
  <template #cell-profit="{ value }">
    <span :class="value >= 0 ? 'positive' : 'negative'">
      {{ value }}%
    </span>
  </template>
  
  <!-- 操作列 -->
  <template #cell-action="{ row }">
    <button @click="view(row)">查看</button>
    <button @click="edit(row)">编辑</button>
  </template>
</ft-table>
```

---

## 待实现功能

### 1. 列格式化（Formatters）

```javascript
cols: [
  { field: 'profit', title: '盈亏', format: 'percent', colorize: true },
  { field: 'amount', title: '金额', format: 'currency', precision: 2 }
]
```

### 2. 排序功能

```javascript
cols: [
  { field: 'profit', title: '盈亏', sortable: true }
]
```

### 3. 筛选功能

```javascript
cols: [
  { field: 'status', title: '状态', filters: [...] }
]
```

### 4. 行选择

### 5. 展开行

### 6. 虚拟滚动

---

## 热力图（Heatmap）参考方案

### 需求场景

1. **单列独立色阶**：A 列、B 列各自独立的色阶
2. **多列关联色阶**：关联的几列设置统一色阶

### 现有方案调研

#### 1. Handsontable

- 官网：https://handsontable.com/
- 特点：功能强大的电子表格组件，支持条件格式化
- 实现方式：
  - 使用 `registerRenderer` 自定义渲染器
  - 通过 `cellProperties` 获取行列信息
  - 根据数值计算背景色

```javascript
// Handsontable 自定义热力图渲染器示例
const heatmapRenderer = function(instance, td, row, col, prop, value, cellProperties) {
  if (typeof value === 'number') {
    const color = calculateColor(value, min, max, colorScale);
    td.style.backgroundColor = color;
  }
  Handsontable.renderers.TextRenderer.apply(this, arguments);
};

Handsontable.registerRenderer('heatmap', heatmapRenderer);

// 列配置使用自定义渲染器
columns: [
  { data: 'price', renderer: 'heatmap' },
  { data: 'change', renderer: 'heatmap' }
]
```

#### 2. AG Grid

- 官网：https://www.ag-grid.com/
- 特点：企业级表格组件，通过 cellStyle 或 cellRenderer 实现
- 实现方式：

```javascript
// 方式1：cellStyle 函数
columnDefs: [
  {
    field: 'price',
    cellStyle: params => {
      const value = params.value;
      const color = getHeatmapColor(value, minValue, maxValue);
      return { backgroundColor: color };
    }
  }
]

// 方式2：自定义 cellRenderer
const HeatmapCellRenderer = {
  template: `<div :style="{background: backgroundColor}">{{ value }}</div>`,
  data() {
    return { backgroundColor: '' };
  },
  mounted() {
    this.backgroundColor = getHeatmapColor(this.params.value, this.params.min, this.params.max);
  }
};
```

#### 3. Element Plus / Ant Design Vue（DIY 方案）

通过表格组件的 `cell-style` 属性自定义：

```vue
<!-- Element Plus -->
<el-table :cell-style="tableCellStyle">
</el-table>

<script>
tableCellStyle({ row, column, rowIndex, columnIndex }) {
  const col = column.property;
  if (heatmapFields.includes(col)) {
    const value = row[col];
    return { backgroundColor: getColor(value, col) };
  }
}
</script>
```

### FT-Table 实现思路

参考上述方案，在 cols 列配置中增加 `heatmap` 属性：

```javascript
cols: [
  // 独立色阶：每列根据自己列的 min/max 计算颜色
  { field: 'price', title: '价格', heatmap: { mode: 'self' } },

  // 关联色阶：volume 和 amount 使用同一组 min/max
  { field: 'volume', title: '成交量', heatmap: { group: 'trade' } },
  { field: 'amount', title: '成交额', heatmap: { group: 'trade' } }
]
```

配置参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `mode` | String | `'self'` - 独立色阶 |
| `group` | String | 分组名称，同组列共享色阶 |
| `colors` | Array | 色阶颜色数组，默认 `['#f7fbff', '#08519c']` |
| `reverse` | Boolean | 是否反转颜色（深色表示低值） |

---

## 设计原则

1. **后端优先**：pandas 数据直接输出，无需列配置
2. **渐进增强**：基础功能开箱即用，高级功能按需启用
3. **前端灵活**：插槽机制支持任意自定义
4. **简单可靠**：cols 可选，不传自动推断

---

## 文件位置

- 组件源码：`template/js/ft-table.js`
- 样式文件：`template/js/notebook.css`（.ft-table 相关样式）
- 使用示例：`test_comprehensive.html`
