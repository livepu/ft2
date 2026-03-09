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
| `reset-page` | Boolean | `true` | 数据变化时是否自动重置到第一页 |

### pagination 配置

```javascript
// 启用分页，每页 20 条
:pagination="{ pageSize: 20 }"

// 自定义每页条数选项
:pagination="{ pageSize: 20, pageSizeOptions: [10, 20, 50, 100] }"

// 禁用分页
:pagination="false"
```

### freeze 配置

```javascript
// 冻结左侧 2 列
:freeze="{ left: 2 }"

// 冻结右侧 1 列
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

- **当前版本**: ft-table.js v1.2.20260309
- 基于 alpine-table.js 重构，适配 Vue 3 组合式 API

---

## 修订记录

### v1.2.20260309（2026-03-09）

**新功能**：
- ✅ 新增 `reset-page` 参数：控制数据变化时是否自动重置到第一页（默认 `true`）
- ✅ 新增 `resetPage()` 方法：支持通过组件 ref 手动重置分页
- ✅ 修复潜在 Bug：数据变化导致总页数减少时，自动调整当前页到有效范围内

**参数说明**：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `reset-page` | Boolean | `true` | 数据变化时是否自动重置到第一页 |

**使用示例**：
```html
<!-- 默认行为：数据变化时重置到第一页 -->
<ft-table :data="tableData"></ft-table>

<!-- 禁用自动重置 -->
<ft-table :data="tableData" :reset-page="false"></ft-table>

<!-- 手动重置（通过 ref） -->
<ft-table ref="tableRef" :data="tableData" :reset-page="false"></ft-table>
<script>
// 在需要重置的地方
tableRef.value.resetPage();
</script>
```

**技术细节**：
- 当 `reset-page="true"` 时，数据变化自动重置到第 1 页
- 当 `reset-page="false"` 时，数据变化时检查当前页是否超过总页数，超过则自动调整到最后一页
- 彻底解决了"切换分类后当前页无数据"的问题

**升级建议**：
- API 向后兼容，建议所有使用者升级
- 利用新参数可以更灵活地控制分页行为

### v1.1.20260308（2026-03-08）

**改进内容**：
- ✅ 排序指示器优化：从 `v-html` 改为纯模板渲染
- ✅ 性能优化：使用 `v-for` 缓存函数调用结果，避免重复计算
- ✅ 代码质量：HTML 结构更清晰，易于维护
- ✅ 样式定制：支持页面级 CSS 覆盖通用样式

**技术细节**：
- `getSortIndicator()` 函数从返回 HTML 字符串改为返回对象
- 模板中使用 `<template v-for="indicator in [getSortIndicator(col)]">` 缓存结果
- 排序显示顺序可通过 CSS `flex-direction: column-reverse` 自定义

**升级建议**：
- 此次升级为优化版本，API 无破坏性变更
- 建议所有使用者升级到 v1.1 版本

### v1.0.20260226（2026-02-26）

**初始版本**：
- ✅ 基于 alpine-table.js 重构，适配 Vue 3 组合式 API
- ✅ 支持分页功能（首页/末页/页码选择）
- ✅ 支持冻结列（左侧/右侧）
- ✅ 支持作用域插槽自定义列渲染
- ✅ 支持多列排序（点击顺序形成优先级）
- ✅ 自动注入基础样式
