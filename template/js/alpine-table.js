/**
 * Alpine.js 表格组件 v2.3.20260226
 * 版本号说明：主版本.次版本.日期（YYYYMMDD）
 * @author kingf_c@foxmail.com
 *
 * ============================================================================
 * 核心设计理念
 * ============================================================================
 *
 * 【设计原则】
 * - 响应式优先：完全利用Alpine.js的响应式系统
 * - 声明式渲染：避免手动DOM操作，使用Alpine.js指令
 * - 组合式API：将功能拆分为独立的可复用函数
 * - 计算属性：使用getter实现自动计算和更新
 * - 自动渲染：支持一键自动生成表格和分页控件
 *
 * 【核心改进】
 * - 代码量减少：从约930行减少到约350行
 * - 性能提升：利用响应式系统，避免不必要的渲染
 * - 可维护性增强：功能模块化，职责清晰
 * - 用户体验优化：添加加载、错误、空状态
 * - 智能渲染：有自定义模板则用用户的，没有则自动使用内置模板
 * - 冻结列：支持左侧/右侧列冻结，使用 CSS sticky + ResizeObserver
 *
 * ============================================================================
 * 功能特性
 * ============================================================================
 *
 * - 支持多种数据来源（本地数据、远程URL、JSON标签）
 * - 前端分页（所有数据在前端处理）
 * - 前端多列排序（支持单列和多列排序，Ctrl+点击支持多列）
 *   注意：排序是对全部数据进行排序，而非仅当前页
 * - 暂不支持服务端分页（后端返回全部数据，前端处理分页）
 * - 支持不分页（设置 pageSize: null 或 0 显示全部数据）
 * - 支持外部通过 updateParams() 更新服务端参数并触发数据加载
 * - 自定义数据解析（通过 parseData 配置项）
 * - 响应式设计
 * - 多实例独立运行，互不干扰
 * - 加载状态、错误状态、空状态
 * - 自动渲染表格和分页控件（有自定义模板则用用户的，没有则用内置的）
 * - 冻结列（可选）：支持左侧/右侧列冻结，表头固定，自动适配宽度变化
 *
 * 【重要】
 * - 此组件需要挂载到 window.table，供 Alpine.js 通过 x-data="table({...})" 调用
 * - 不支持服务端分页，当前版本仅支持前端分页和前端排序
 * - 冻结列使用 CSS position: sticky 实现，兼容现代浏览器
 *
 * ============================================================================
 * 使用示例
 * ============================================================================
 *
 * 【场景 1：纯本地数据 + 自动渲染】
 * <div x-data="table({
 *   data: [{ id: 1, name: '张三', age: 25 }, ...],
 *   cols: [
 *     { field: 'id', title: 'ID' },
 *     { field: 'name', title: '姓名' },
 *     { field: 'age', title: '年龄' }
 *   ]
 * })">
 *   <!-- 自动渲染表格和分页 -->
 * </div>
 *
 * 【场景 2：冻结列（左侧冻结2列，右侧冻结1列）】
 * <div x-data="table({
 *   data: [{ code: '000001', name: '基金A', type: '股票型', ... }, ...],
 *   cols: [
 *     { field: 'code', title: '代码' },
 *     { field: 'name', title: '名称' },
 *     { field: 'type', title: '类型' },
 *     { field: 'nav', title: '净值' },
 *     { field: 'status', title: '状态' }
 *   ],
 *   freeze: { left: 2, right: 1 }
 * })">
 *   <!-- 自动渲染带冻结列的表格 -->
 * </div>
 *
 * 【场景 3：远程数据 + 外部筛选】
 * <div x-data="table({
 *   id: 'etf-table',
 *   url: '/home/etf/data',
 *   urlParams: {
 *     categories: 'categories',
 *     search: 'search',
 *     max_per_index: 'max_per_index'
 *   },
 *   cols: [
 *     { field: 'name', title: 'ETF名称' },
 *     { field: 'code', title: '代码' },
 *     { field: 'scale', title: '规模' }
 *   ],
 *   page: { limit: 20, limits: [20, 50, 100] }
 * })">
 *   <!-- 加载状态 -->
 *   <div x-show="loading">加载中...</div>
 *   
 *   <!-- 错误状态 -->
 *   <div x-show="error" x-text="error"></div>
 *   
 *   <!-- 表格 -->
 *   <table x-show="!loading && !error">
 *     <!-- 表格内容 -->
 *   </table>
 * </div>
 *
 * 外部控制筛选：
 * <div x-data="{
 *   updateData() {
 *     $refs.etfTable.updateParams({
 *       categories: '规模,行业',
 *       search: 'ETF'
 *     });
 *   }
 * }">
 *   <button @click="updateData()">更新数据</button>
 * </div>
 *
 * 【场景 4：不分页显示全部数据】
 * <div x-data="table({
 *   id: 'all-data-table',
 *   data: [{ id: 1, name: '张三', age: 25 }, ...],
 *   cols: [
 *     { field: 'id', title: 'ID' },
 *     { field: 'name', title: '姓名' },
 *     { field: 'age', title: '年龄' }
 *   ],
 *   page: { limit: null, limits: [10, 20, 50] }
 * })">
 *   <table>
 *     <thead>
 *       <tr>
 *         <template x-for="col in cols">
 *           <th @click="sort(col.field, $event)">
 *             <span x-text="col.title"></span>
 *           </th>
 *         </template>
 *       </tr>
 *     </thead>
 *     <tbody>
 *       <template x-for="row in pageData">
 *         <tr>
 *           <template x-for="col in cols">
 *             <td x-text="getNestedValue(row, col.field)"></td>
 *           </template>
 *         </tr>
 *       </template>
 *     </tbody>
 *   </table>
 * </div>
 *
 * 【场景 5：支持分页和不分页切换】
 * <div x-data="table({
 *   id: 'switch-table',
 *   data: [{ id: 1, name: '张三', age: 25 }, ...],
 *   cols: [
 *     { field: 'id', title: 'ID' },
 *     { field: 'name', title: '姓名' },
 *     { field: 'age', title: '年龄' }
 *   ],
 *   page: { limit: 10, limits: [10, 20, 50] }
 * })">
 *   <!-- 分页控件 -->
 *   <div x-show="needsPagination">
 *     <button @click="prevPage()">上一页</button>
 *     <span x-text="`${page.curr} / ${totalPages}`"></span>
 *     <button @click="nextPage()">下一页</button>
 *     <select x-model.number="page.limit" @change="changeLimit()">
 *       <option :value="10">10 条/页</option>
 *       <option :value="20">20 条/页</option>
 *       <option :value="50">50 条/页</option>
 *       <option :value="null">全部</option>
 *     </select>
 *   </div>
 * </div>
 *
 * ============================================================================
 * 配置项说明
 * ============================================================================
 *
 * 【基础配置】
 * - id: 表格唯一标识（可选）
 * - data: 本地数据数组
 * - url: 远程数据接口地址
 * - urlParams: URL参数映射
 * - cols: 列配置数组 [{ field, title }, ...]
 * - parseData: 自定义数据解析函数
 *
 * 【冻结配置】
 * - freeze: { left: 0, right: 0 }
 *   - left: 左侧冻结列数（默认0）
 *   - right: 右侧冻结列数（默认0）
 *   - 技术实现：CSS sticky + ResizeObserver 自动适配宽度
 *
 * 【分页配置】
 * - page: { curr: 1, limit: 10, limits: [10, 20, 50] }
 *   - limit 为 null 或 0 时显示全部数据
 *
 * ============================================================================
 * 核心方法
 * ============================================================================
 *
 * 【数据管理】
 * - loadData()              加载远程数据
 * - updateParams(newParams) 更新参数并触发数据加载
 *
 * 【排序管理】
 * - sort(field, event)      排序操作
 * - getSortDirection(field) 获取排序方向
 * - getSortPriority(field)  获取排序优先级
 * - clearSort()             清除所有排序规则
 *
 * 【分页管理】
 * - prevPage()              上一页
 * - nextPage()              下一页
 * - goToPage(page)          跳转到指定页
 *
 * 【冻结管理】
 * - applyFreezeStyles()     应用冻结列样式
 * - destroyFreeze()         销毁冻结监听器（组件销毁时调用）
 *
 * 【数据访问】
 * - getNestedValue(obj, path) 获取嵌套属性值
 *
 * 【计算属性】
 * - sortedData              排序后的数据
 * - pageData                当前页数据
 * - totalPages              总页数
 * - needsPagination         是否需要分页
 */

// ============================================================================
// 工具函数
// ============================================================================

/**
 * 从JSON脚本标签读取数据
 * @param {string} src - 数据源选择器或全局变量路径
 * @returns {Array} 解析后的数据数组
 */
function getDataFromSrc(src) {
  if (!src) return [];
  
  if (src.startsWith('#')) {
    const elem = document.querySelector(src);
    if (elem && elem.textContent) {
      try {
        return JSON.parse(elem.textContent);
      } catch (e) {
        console.error('Failed to parse JSON data from', src, e);
        return [];
      }
    }
  }
  
  if (src.includes('.')) {
    try {
      const parts = src.split('.');
      let data = window;
      for (const part of parts) {
        data = data[part];
        if (data === undefined) return [];
      }
      return Array.isArray(data) ? data : (data.data || []);
    } catch (e) {
      console.error('Failed to get data from path', src, e);
      return [];
    }
  }
  
  return [];
}

/**
 * 获取嵌套属性值（支持嵌套属性和动态属性名）
 * 
 * 与 row['field'] 的区别：
 * - row['field']：仅支持简单属性，如 row['name']
 * - getNestedValue()：支持更复杂的场景
 * 
 * 场景1：动态日期属性（常见于 ETF/基金 表格）
 *   数据：{ code: '510300', '2026-01-02': 3.85, '2026-01-03': 3.90 }
 *   调用：getNestedValue(row, '2026-01-02') → 3.85
 * 
 * 场景2：嵌套属性
 *   数据：{ stats: { daily: 3.85, weekly: 4.20 } }
 *   调用：getNestedValue(row, 'stats.daily') → 3.85
 *   注意：row['stats.daily'] ❌ 不工作，getNestedValue() ✅ 正常工作
 * 
 * 场景3：安全处理 null/undefined
 *   数据：{ a: null }
 *   调用：getNestedValue(row, 'a.b.c') → 不会报错，返回 null
 * 
 * @param {Object} obj - 目标对象
 * @param {string} path - 属性路径（如 'name'、'2026-01-02'、'stats.daily'）
 * @returns {*} 属性值
 */
function getNestedValue(obj, path) {
  if (!obj || !path) return null;
  
  const keys = path.split('.');
  let result = obj;
  
  for (const key of keys) {
    if (result == null) return null;
    result = result[key];
  }
  
  return result;
}

/**
 * 注入冻结列所需的 CSS 样式
 * 只设置功能性样式（sticky、z-index），不设置装饰性样式（背景色）
 */
function injectFreezeStyles() {
  const styleId = 'alpine-table-freeze-styles';
  if (document.getElementById(styleId)) return;

  const style = document.createElement('style');
  style.id = styleId;
  style.textContent = `
    /* 冻结容器 */
    .alpine-table-freeze {
      overflow-x: auto;
      position: relative;
    }
    /* 冻结列单元格 - 只设置 sticky 定位 */
    .alpine-table-freeze .freeze-col {
      position: sticky;
    }
    /* 表头整体冻结在顶部（仅冻结模式） */
    .alpine-table-freeze thead th {
      position: sticky;
      top: 0;
      z-index: 10;
    }
    /* 表头中的冻结列需要更高的 z-index */
    .alpine-table-freeze thead .freeze-col {
      z-index: 100;
    }
    .alpine-table-freeze tbody .freeze-col {
      z-index: 50;
    }
    /* 表格边框（仅冻结模式需要 separate） */
    .alpine-table-freeze .alpine-table {
      border-collapse: separate;
      border-spacing: 0;
    }
  `;
  document.head.appendChild(style);
}

// ============================================================================
// 主组件定义
// ============================================================================

window.table = function table(config = {}) {
  return {
    // ============================================================================
    // 基础配置
    // ============================================================================
    
    id: config.id || 'table-' + Date.now(),
    url: config.url || null,
    baseUrl: config.url || null,
    urlParams: config.urlParams || {},
    currentParams: {},
    parseData: config.parseData || ((res) => Array.isArray(res) ? res : (res.data || [])),
    
    // 固定列配置 freeze: {left: 1, right: 0}
    freeze: config.freeze || {left: 0, right: 0},
    
    // ============================================================================
    // 数据状态
    // ============================================================================
    
    data: [],
    loading: false,
    error: null,
    
    // ============================================================================
    // 列配置
    // ============================================================================
    
    cols: config.cols || [],
    
    // ============================================================================
    // 排序状态
    // ============================================================================
    
    sortRules: [],
    
    // ============================================================================
    // 分页状态
    // ============================================================================
    
    page: {
      curr: 1,
      limit: config.page?.limit || 10,
      limits: config.page?.limits || [10, 20, 50],
      totalPage: 1,
      count: 0
    },
    
    // ============================================================================
    // 计算属性：排序后的数据
    // ============================================================================
    
    get sortedData() {
      if (this.sortRules.length === 0) {
        return this.data;
      }
      
      const result = [...this.data];
      
      result.sort((a, b) => {
        for (const rule of this.sortRules) {
          const field = rule.field;
          const direction = rule.type;
          
          let aValue = getNestedValue(a, field);
          let bValue = getNestedValue(b, field);
          
          if (aValue == null && bValue == null) continue;
          if (aValue == null) return direction === 'asc' ? -1 : 1;
          if (bValue == null) return direction === 'asc' ? 1 : -1;
          
          const aNum = Number(aValue);
          const bNum = Number(bValue);
          
          if (!isNaN(aNum) && !isNaN(bNum)) {
            aValue = aNum;
            bValue = bNum;
          }
          
          let comparison = 0;
          if (aValue < bValue) comparison = -1;
          else if (aValue > bValue) comparison = 1;
          
          if (comparison !== 0) {
            return direction === 'asc' ? comparison : -comparison;
          }
        }
        
        return 0;
      });
      
      return result;
    },
    
    // ============================================================================
    // 计算属性：当前页数据
    // ============================================================================
    
    get pageData() {
      if (!this.page.limit || this.page.limit === 0) {
        return this.sortedData;
      }
      
      const start = (this.page.curr - 1) * this.page.limit;
      const end = start + this.page.limit;
      return this.sortedData.slice(start, end);
    },

    // ============================================================================
    // 计算属性：总页数
    // ============================================================================
    
    get totalPages() {
      if (!this.page.limit || this.page.limit === 0) {
        return 1;
      }
      return Math.ceil(this.data.length / this.page.limit) || 1;
    },

    // ============================================================================
    // 计算属性：是否需要分页
    // ============================================================================
    
    get needsPagination() {
      if (!this.page.limit || this.page.limit === 0) {
        return false;
      }
      return this.data.length > this.page.limit;
    },
    
    // ============================================================================
    // 生命周期方法
    // ============================================================================
    
    init() {
      injectFreezeStyles();
      this.loadDataFromConfig();
      
      if (this.$cleanup) {
        this.$cleanup(() => this.destroyFreeze());
      }
      
      this.$nextTick(() => {
        this.render();
      });
    },
    
    // ============================================================================
    // 数据加载
    // ============================================================================
    
    loadDataFromConfig() {
      if (config.data) {
        this.data = config.data;
      } else if (config.dataSrc) {
        this.data = getDataFromSrc(config.dataSrc);
      } else if (this.url) {
        this.loadData();
      }
      
      if (!config.cols && !config.colsSrc && this.data.length > 0) {
        this.cols = Object.keys(this.data[0]).map(key => ({
          field: key,
          title: key
        }));
      }
      
      if (config.colsSrc) {
        this.cols = getDataFromSrc(config.colsSrc);
      }
    },
    
    async loadData() {
      if (!this.url) return;
      
      this.loading = true;
      this.error = null;
      
      try {
        const response = await fetch(this.url, {
          headers: {
            'X-Requested-With': 'XMLHttpRequest'
          }
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const rawData = await response.json();
        this.data = this.parseData(rawData);
        
        this.$nextTick(() => {
          this._updateFreezeOffsets();
        });
      } catch (error) {
        this.error = error.message;
        console.error('加载数据失败:', error);
      } finally {
        this.loading = false;
      }
    },
    
    // ============================================================================
    // URL参数管理
    // ============================================================================
    
    buildUrl() {
      if (!this.baseUrl) return null;
      
      const params = new URLSearchParams();
      
      for (const [key, paramName] of Object.entries(this.urlParams)) {
        const value = this.currentParams[key];
        if (value !== null && value !== undefined && value !== '') {
          params.set(paramName, value);
        }
      }
      
      const queryString = params.toString();
      return queryString ? `${this.baseUrl}?${queryString}` : this.baseUrl;
    },
    
    updateParams(newParams) {
      for (const [key, value] of Object.entries(newParams)) {
        if (value === null || value === undefined || value === '') {
          delete this.currentParams[key];
        } else {
          this.currentParams[key] = value;
        }
      }
      
      if (this.urlParams) {
        const newUrl = this.buildUrl();
        this.url = newUrl;
        this.loadData();
      }
    },
    
    // ============================================================================
    // 排序管理
    // ============================================================================
    
    /**
     * 排序操作 - 支持单列和多列排序
     * 
     * 【单列排序】点击列头：none → desc → asc → none
     * 【多列排序】Ctrl+点击：在现有排序基础上累加/切换
     * 
     * @param {string} field - 排序字段名
     * @param {Event} event - 点击事件对象，通过 event.ctrlKey 判断是否多列排序
     * 
     * @example
     * // 单列排序示例：
     * // 第一次点击：添加 desc 排序
     * // 第二次点击：切换为 asc 排序  
     * // 第三次点击：移除该字段排序
     * 
     * @example
     * // 多列排序示例（Ctrl+点击）：
     * // 1. 点击"基金代码" → [{field: 'fcode', type: 'desc'}]
     * // 2. Ctrl+点击"基金名称" → [{field: 'fcode', type: 'desc'}, {field: 'fname', type: 'desc'}]
     * // 3. Ctrl+再次点击"基金代码" → [{field: 'fcode', type: 'asc'}, {field: 'fname', type: 'desc'}]
     */
    sort(field, event) {
      // 判断是否多列排序模式（按住 Ctrl 键）
      const isMultiSort = event.ctrlKey;
      
      // 获取该字段当前的排序方向
      const currentType = this.getSortDirection(field);
      
      // 计算下一次排序方向：none → desc → asc → none
      let nextType = null;
      if (!currentType) {
        nextType = 'desc';      // 首次排序：设为降序
      } else if (currentType === 'desc') {
        nextType = 'asc';       // 再次点击：切换为升序
      }
      // currentType === 'asc' 时，nextType 保持 null，表示取消排序
      
      // 根据是否为多列排序，采用不同的策略
      if (isMultiSort || this.sortRules.length === 0) {
        // 【多列排序模式】或【首个排序规则】
        // 策略：在现有排序规则上累加或切换
        if (nextType) {
          // 有下一个方向（desc 或 asc）
          const existingIndex = this.sortRules.findIndex(rule => rule.field === field);
          
          if (existingIndex >= 0) {
            // 该字段已存在排序规则 → 切换方向
            this.sortRules[existingIndex].type = nextType;
          } else {
            // 该字段不存在 → 新增排序规则
            this.sortRules.push({ field, type: nextType });
          }
        } else {
          // nextType 为 null，表示取消该字段排序
          const index = this.sortRules.findIndex(rule => rule.field === field);
          if (index >= 0) {
            this.sortRules.splice(index, 1);
          }
        }
      } else {
        // 【单列排序模式】（非 Ctrl 点击且已有其他排序规则）
        // 策略：清空其他排序，只保留当前点击的字段
        this.sortRules = [];
        
        if (nextType) {
          this.sortRules.push({ field, type: nextType });
        }
      }
    },
    
    /**
     * 获取指定字段的排序方向
     * 
     * @param {string} field - 字段名
     * @returns {string|null} 排序方向：'asc'（升序）、'desc'（降序）、null（未排序）
     * 
     * @example
     * getSortDirection('fcode') // → 'asc' | 'desc' | null
     */
    getSortDirection(field) {
      const rule = this.sortRules.find(rule => rule.field === field);
      return rule ? rule.type : null;
    },
    
    /**
     * 获取指定字段的排序优先级
     * 
     * 用于多列排序时显示优先级数字（1, 2, 3...）
     * 
     * @param {string} field - 字段名
     * @returns {number} 优先级：1, 2, 3...（已排序）或 0（未排序）
     * 
     * @example
     * // 假设排序规则为：[{field: 'fcode', type: 'desc'}, {field: 'fname', type: 'asc'}]
     * getSortPriority('fcode') // → 1  （第一优先级）
     * getSortPriority('fname') // → 2  （第二优先级）
     * getSortPriority('other') // → 0  （未排序）
     */
    getSortPriority(field) {
      const index = this.sortRules.findIndex(rule => rule.field === field);
      return index >= 0 ? index + 1 : 0;
    },
    
    /**
     * 获取指定字段的排序图标
     * 
     * @param {string} field - 字段名
     * @returns {string} 图标字符：'↑'（升序）、'↓'（降序）、''（未排序）
     * 
     * @example
     * getSortIcon('fcode') // → '↑' | '↓' | ''
     */
    getSortIcon(field) {
      const direction = this.getSortDirection(field);
      if (!direction) return '';
      return direction === 'asc' ? '▲' : '▼';
    },
    
    /**
     * 清除所有排序规则
     * 
     * @example
     * clearSort() // sortRules 重置为 []
     */
    clearSort() {
      this.sortRules = [];
    },
    
    // ============================================================================
    // 分页管理
    // ============================================================================
    
    prevPage() {
      if (this.page.curr > 1) {
        this.page.curr--;
      }
    },
    
    nextPage() {
      if (this.page.curr < this.totalPages) {
        this.page.curr++;
      }
    },
    
    goToPage(page) {
      if (page >= 1 && page <= this.totalPages) {
        this.page.curr = page;
      }
    },
    
    changeLimit() {
      this.page.curr = 1;
    },
    
    // ============================================================================
    // 数据访问
    // ============================================================================
    
    getNestedValue(obj, path) {
      return getNestedValue(obj, path);
    },
    
    // ============================================================================
    // 自动渲染功能
    // ============================================================================
    
    /**
     * 内置模板实现方式
     * 
     * 使用模板字符串 + 动态插入的方式实现内置模板：
     * - 模板字符串：使用 this.cols.map() 遍历生成列
     * - 动态插入：使用 insertAdjacentHTML 插入 DOM
     * - Alpine 初始化：使用 $nextTick + Alpine.initTree() 初始化
     * 
     * 这种方式结合了 Alpine.js 的声明式指令（如 x-text、x-if、x-for）
     * 实现了"开箱即用"的无模板模式
     */
    
    getRootElement() {
      return this.$el || document.getElementById(this.id);
    },
    
    render() {
      this.renderTable();
      this.renderPagination();
    },
    
    renderTable() {
      try {
        const rootElement = this.getRootElement();
        if (!rootElement) return;
        
        const anyTable = rootElement.querySelector('table');
        if (anyTable) return;
        
        const existingTableContainer = rootElement.querySelector('.alpine-table-container');
        if (existingTableContainer) return;
        
        const freezeLeft = (this.freeze?.left || 0);
        const freezeRight = (this.freeze?.right || 0);
        const hasFreeze = freezeLeft > 0 || freezeRight > 0;
        
        const renderCols = (isHeader = false) => {
          return this.cols.map((col, index) => {
            let className = 'sortable';
            let styleAttr = '';
            let dataAttr = '';

            if (index < freezeLeft) {
              // 左侧冻结：越靠左 z-index 越高（100, 99, 98...）
              const zIndex = 100 - index;
              className = 'freeze-col freeze-left ' + className;
              styleAttr = `style="left: var(--freeze-left-${index}, 0); z-index: ${zIndex};"`;
              dataAttr = `data-freeze-index="${index}"`;
            }
            else if (index >= this.cols.length - freezeRight) {
              // 右侧冻结：越靠右 z-index 越高（100, 99, 98...）
              const rightIndex = this.cols.length - index - 1;
              const zIndex = 100 - rightIndex;
              className = 'freeze-col freeze-right ' + className;
              styleAttr = `style="right: var(--freeze-right-${rightIndex}, 0); z-index: ${zIndex};"`;
              dataAttr = `data-freeze-right="${rightIndex}"`;
            }

            if (isHeader) {
              return `<th ${dataAttr} class="${className}" ${styleAttr} @click="sort('${col.field}', $event)">
                <span x-text="'${col.title}'"></span>
                <template x-if="getSortPriority('${col.field}') > 0">
                  <span class="sort-indicator">
                    <span x-text="getSortIcon('${col.field}')" :class="getSortDirection('${col.field}') === 'asc' ? 'sort-asc' : 'sort-desc'"></span>
                    <span class="sort-priority" x-text="getSortPriority('${col.field}')"></span>
                  </span>
                </template>
              </th>`;
            } else {
              return `<td ${dataAttr} class="${className}" ${styleAttr} x-text="getNestedValue(row, '${col.field}')"></td>`;
            }
          }).join('');
        };
        
        const containerClass = hasFreeze ? 'alpine-table-container alpine-table-freeze' : 'alpine-table-container';
        const tableRef = hasFreeze ? 'x-ref="freezeTable"' : '';
        
        const tableHTML = `
          <div class="${containerClass}">
            <table class="alpine-table" ${tableRef}>
              <thead>
                <tr>
                  ${renderCols(true)}
                </tr>
              </thead>
              <tbody>
                <template x-for="(row, rowIndex) in pageData" :key="rowIndex + '-' + (row.id || row[Object.keys(row)[0]] || rowIndex)">
                  <tr>
                    ${renderCols(false)}
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        `;
        
        rootElement.insertAdjacentHTML('afterbegin', tableHTML);
        
        if (window.Alpine && typeof window.Alpine.initTree === 'function') {
          const newTable = rootElement.querySelector('.alpine-table-container');
          if (newTable) {
            window.Alpine.initTree(newTable);
          }
        }
        
        // 如果有冻结列，在渲染完成后计算列宽并设置left值
        if (hasFreeze) {
          this.$nextTick(() => {
            this.applyFreezeStyles();
          });
        }
      } catch (error) {
        console.error('Error in renderTable:', error);
      }
    },
    
    // 应用冻结列样式（CSS变量 + ResizeObserver）
    applyFreezeStyles() {
      const table = this.$refs.freezeTable;
      if (!table) return;
      
      const freezeLeft = this.freeze?.left || 0;
      const freezeRight = this.freeze?.right || 0;
      if (freezeLeft === 0 && freezeRight === 0) return;
      
      this._updateFreezeOffsets();
      
      if (!this._freezeObserver) {
        this._freezeObserver = new ResizeObserver(() => {
          this._updateFreezeOffsets();
        });
        this._freezeObserver.observe(table);
        
        this._freezeResizeHandler = () => this._updateFreezeOffsets();
        window.addEventListener('resize', this._freezeResizeHandler);
      }
    },
    
    _updateFreezeOffsets() {
      const table = this.$refs.freezeTable;
      if (!table) return;
      
      const freezeLeft = this.freeze?.left || 0;
      const freezeRight = this.freeze?.right || 0;
      if (freezeLeft === 0 && freezeRight === 0) return;
      
      const headerCells = table.querySelectorAll('thead th');
      const colWidths = Array.from(headerCells).map(th => th.offsetWidth);
      const root = this.getRootElement();
      if (!root) return;
      
      // 设置左侧冻结列的偏移量
      let accLeft = 0;
      for (let i = 0; i < freezeLeft; i++) {
        root.style.setProperty(`--freeze-left-${i}`, accLeft + 'px');
        accLeft += colWidths[i] || 100;
      }
      
      // 设置右侧冻结列的偏移量
      let accRight = 0;
      for (let i = 0; i < freezeRight; i++) {
        root.style.setProperty(`--freeze-right-${i}`, accRight + 'px');
        accRight += colWidths[colWidths.length - 1 - i] || 100;
      }
    },
    
    destroyFreeze() {
      if (this._freezeObserver) {
        this._freezeObserver.disconnect();
        this._freezeObserver = null;
      }
      if (this._freezeResizeHandler) {
        window.removeEventListener('resize', this._freezeResizeHandler);
        this._freezeResizeHandler = null;
      }
    },
    
    renderPagination() {
      try {
        const rootElement = this.getRootElement();
        if (!rootElement) return;
        
        const existingPagination = rootElement.querySelector('.alpine-table-pagination');
        if (existingPagination) {
          if (!this.needsPagination) {
            existingPagination.remove();
          }
          return;
        }
        
        let hasCustomPagination = false;
        
        if (rootElement.querySelector('.pagination-container')) {
          hasCustomPagination = true;
        }

        if (rootElement.querySelector('[x-text*="page.curr"]')) {
          hasCustomPagination = true;
        }

        if (rootElement.querySelector('select[x-model*="page.limit"]')) {
          hasCustomPagination = true;
        }
        
        if (hasCustomPagination) {
          return;
        }
        
        if (this.needsPagination) {
          const paginationHTML = `
            <div class="alpine-table-pagination">
              <button @click="prevPage()" :disabled="page.curr === 1" class="pagination-btn pagination-prev">
                上一页
              </button>
              <span class="pagination-info" x-text="page.curr + '/' + totalPages"></span>
              <button @click="nextPage()" :disabled="page.curr === totalPages" class="pagination-btn pagination-next">
                下一页
              </button>
              <select x-model.number="page.limit" @change="changeLimit()" class="pagination-select">
                ${this.page.limits.map(limit => `<option value="${limit}" ${limit === this.page.limit ? 'selected' : ''}>${limit} 条/页</option>`).join('')}
              </select>
            </div>
          `;
          
          rootElement.insertAdjacentHTML('beforeend', paginationHTML);
          
          if (window.Alpine && typeof window.Alpine.initTree === 'function') {
            const newPagination = rootElement.querySelector('.alpine-table-pagination');
            if (newPagination) {
              window.Alpine.initTree(newPagination);
            }
          }
        }
      } catch (error) {
        console.error('Error in renderPagination:', error);
      }
    }
  };
};
