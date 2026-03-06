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
