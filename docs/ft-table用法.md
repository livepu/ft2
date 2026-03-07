# ft-table 用法指南

## 概述

ft-table 是一个基于 Vue 3 组合式 API 的表格组件，专注于数据展示，遵循"原子化"设计原则。

**设计理念**：组件只负责展示，数据由外部传入。远程加载、搜索筛选等逻辑应在组件外部处理。

---

## 引入方式

```html
<script src="vue.global.prod.js"></script>
<script src="ft-table.js"></script>
```

```javascript
const app = Vue.createApp({});
app.component('ft-table', FtTable);
app.mount('#app');
```

---

## 基础用法

### 1. 简单数据

```html
<ft-table :data="tableData" :cols="columns" />
```

```javascript
const tableData = [
  { code: "001", name: "苹果", price: 5.80 },
  { code: "002", name: "香蕉", price: 3.20 }
];

const columns = ["代码", "名称", "价格"];
```

### 2. 指定字段名

```javascript
const columns = [
  { field: "code", title: "代码" },
  { field: "name", title: "名称" },
  { field: "price", title: "价格" }
];
```

---

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `data` | Array | `[]` | 表格数据源 |
| `cols` | Array | `[]` | 列配置 |
| `pagination` | Object/Boolean | `false` | 分页配置，`false` 禁用分页 |
| `freeze` | Object | `{left: 0, right: 0}` | 冻结列配置 |
| `emptyText` | String | `"暂无数据"` | 空数据提示文本 |

### pagination 配置

```javascript
// 启用分页，每页20条
:pagination="{ pageSize: 20 }"

// 自定义每页条数选项
:pagination="{ pageSize: 20, pageSizeOptions: [10, 20, 50, 100] }"

// 禁用分页
:pagination="false"
```

### freeze 配置

```javascript
// 冻结左侧2列
:freeze="{ left: 2 }"

// 冻结右侧1列
:freeze="{ right: 1 }"

// 同时冻结左右
:freeze="{ left: 2, right: 1 }"
```

---

## 插槽用法

ft-table 支持作用域插槽，可以自定义任意列的渲染方式。

### 插槽变量

| 变量 | 说明 |
|------|------|
| `row` | 整行数据对象 |
| `value` | 当前单元格的值 |
| `index` | 行索引（从 0 开始） |

### 自定义列渲染

```html
<ft-table :data="data" :cols="cols">
  <template #cell-price="{ row, value }">
    <span :style="{ color: value > 10 ? 'red' : 'green' }">
      ¥{{ value.toFixed(2) }}
    </span>
  </template>
</ft-table>
```

### 添加操作列

```javascript
const cols = [
  { field: "code", title: "代码" },
  { field: "name", title: "名称" },
  { slot: "cell-actions", title: "操作" }
];
```

```html
<ft-table :data="data" :cols="cols">
  <template #cell-actions="{ row, index }">
    <button @click="edit(row.id)">编辑</button>
    <button @click="del(row.id, index)">删除</button>
  </template>
</ft-table>
```

---

## 完整示例

```html
<div id="app">
  <ft-table
    :data="tableData"
    :cols="columns"
    :pagination="{ pageSize: 20 }"
    :freeze="{ left: 1 }"
  >
    <template #cell-name="{ row, value }">
      <strong>{{ value }}</strong>
    </template>
    <template #cell-price="{ value }">
      <span :class="value >= 0 ? 'positive' : 'negative'">
        {{ value.toFixed(2) }}
      </span>
    </template>
  </ft-table>
</div>

<script src="vue.global.prod.js"></script>
<script src="ft-table.js"></script>
<script>
  const app = Vue.createApp({
    data() {
      return {
        tableData: [
          { code: "001", name: "苹果", price: 5.80 },
          { code: "002", name: "香蕉", price: 3.20 },
          { code: "003", name: "橙子", price: -1.50 }
        ],
        columns: ["代码", "名称", "价格"]
      };
    }
  });
  app.component('ft-table', FtTable);
  app.mount('#app');
</script>

<style>
  .positive { color: green; }
  .negative { color: red; }
</style>
```

---

## 与 alpine-table.js 的区别

| 特性 | ft-table.js | alpine-table.js |
|------|-------------|-----------------|
| 框架 | Vue 3 | Alpine.js |
| 远程加载 | ❌ | ✅（不推荐） |
| 数据解析 | ❌ | ✅（不推荐） |
| 自定义插槽 | ✅（Vue 作用域插槽） | 有限支持 |
| 分页器 | 完整（首页/末页） | 简化 |
| 设计原则 | 原子化，只做展示 | 功能集成在组件内 |

**推荐**：数据获取、搜索筛选等逻辑在组件外部处理，ft-table 只负责展示。

---

## 版本信息

- **ft-table.js**: v1.0.20260226
- 基于 alpine-table.js 重构，适配 Vue 3 组合式 API
