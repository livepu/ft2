/**
 * Vue 3 Table Component
 * 基于 alpine-table.js 重构，适配 Vue 3 组合式 API
 * 
 * 使用方式：
 * <vue-table :id="'table-1'" :data="tableData" :cols="columns" :freeze="{left: 2}" :page="{limit: 20}"></vue-table>
 */

const VueTable = {
  name: 'VueTable',
  
  props: {
    id: {
      type: String,
      required: true
    },
    data: {
      type: Array,
      default: () => []
    },
    cols: {
      type: Array,
      default: () => []
    },
    freeze: {
      type: Object,
      default: () => ({ left: 0, right: 0 })
    },
    page: {
      type: [Object, Boolean],
      default: false
    }
  },

  setup(props) {
    const { ref, computed, onMounted, onUnmounted, watch, nextTick } = Vue;
    
    // ========== 响应式数据 ==========
    const currentPage = ref(1);
    const pageSize = ref(props.page?.limit || 20);
    const sortField = ref('');
    const sortOrder = ref('asc');
    const multiSort = ref([]);
    const tableContainer = ref(null);
    const resizeObserver = ref(null);

    // ========== 计算属性 ==========
    
    // 排序后的数据
    const sortedData = computed(() => {
      if (!sortField.value && multiSort.value.length === 0) {
        return props.data;
      }
      
      return [...props.data].sort((a, b) => {
        // 优先使用多字段排序
        if (multiSort.value.length > 0) {
          for (const sort of multiSort.value) {
            const v1 = a[sort.field];
            const v2 = b[sort.field];
            if (v1 !== v2) {
              return sort.order === 'asc' ? (v1 > v2 ? 1 : -1) : (v1 < v2 ? 1 : -1);
            }
          }
          return 0;
        }
        
        // 单字段排序
        const v1 = a[sortField.value];
        const v2 = b[sortField.value];
        return sortOrder.value === 'asc' ? (v1 > v2 ? 1 : -1) : (v1 < v2 ? 1 : -1);
      });
    });

    // 分页后的数据
    const paginatedData = computed(() => {
      if (!props.page) return sortedData.value;
      const start = (currentPage.value - 1) * pageSize.value;
      return sortedData.value.slice(start, start + pageSize.value);
    });

    // 总页数
    const totalPages = computed(() => {
      if (!props.page) return 1;
      return Math.ceil(props.data.length / pageSize.value) || 1;
    });

    // 总记录数
    const totalRecords = computed(() => props.data.length);

    // 显示的列（处理 cols 格式）
    const displayCols = computed(() => {
      if (props.cols && props.cols.length > 0) {
        return props.cols;
      }
      // 从数据自动推断列
      if (props.data.length > 0) {
        return Object.keys(props.data[0]).map(key => ({
          field: key,
          title: key
        }));
      }
      return [];
    });

    // 是否有冻结列
    const hasFreeze = computed(() => {
      return props.freeze && (props.freeze.left > 0 || props.freeze.right > 0);
    });

    // 分页选项
    const pageLimits = computed(() => {
      return props.page?.limits || [10, 20, 50, 100];
    });

    // ========== 方法 ==========
    
    // 单字段排序
    const handleSort = (col) => {
      const field = col.field;
      
      if (sortField.value === field) {
        // 切换排序方向
        if (sortOrder.value === 'asc') {
          sortOrder.value = 'desc';
        } else if (sortOrder.value === 'desc') {
          sortOrder.value = '';
          sortField.value = '';
        }
      } else {
        sortField.value = field;
        sortOrder.value = 'asc';
      }
      
      // 重置到第一页
      currentPage.value = 1;
    };

    // 多字段排序（Ctrl+点击）
    const handleMultiSort = (col, event) => {
      if (!event.ctrlKey && !event.metaKey) {
        handleSort(col);
        return;
      }
      
      const field = col.field;
      const existingIndex = multiSort.value.findIndex(s => s.field === field);
      
      if (existingIndex >= 0) {
        const existing = multiSort.value[existingIndex];
        if (existing.order === 'asc') {
          existing.order = 'desc';
        } else {
          multiSort.value.splice(existingIndex, 1);
        }
      } else {
        multiSort.value.push({ field, order: 'asc', priority: multiSort.value.length + 1 });
      }
      
      currentPage.value = 1;
    };

    // 获取排序指示器
    const getSortIndicator = (col) => {
      // 单字段排序
      if (sortField.value === col.field) {
        return sortOrder.value === 'asc' ? '▲' : '▼';
      }
      
      // 多字段排序
      const multiIndex = multiSort.value.findIndex(s => s.field === col.field);
      if (multiIndex >= 0) {
        const sort = multiSort.value[multiIndex];
        const priority = multiSort.value.length > 1 ? `<span class="sort-priority">${sort.priority}</span>` : '';
        return `${priority}${sort.order === 'asc' ? '▲' : '▼'}`;
      }
      
      return '';
    };

    // 判断是否冻结列
    const isFreezeCol = (index) => {
      if (!hasFreeze.value) return false;
      const left = props.freeze.left || 0;
      const right = props.freeze.right || 0;
      const total = displayCols.value.length;
      
      return index < left || index >= total - right;
    };

    // 获取冻结列的 CSS 类
    const getFreezeClass = (index) => {
      if (!isFreezeCol(index)) return '';
      const left = props.freeze.left || 0;
      return index < left ? 'freeze-left' : 'freeze-right';
    };

    // 应用冻结列样式
    const applyFreezeStyles = () => {
      if (!hasFreeze.value || !tableContainer.value) return;
      
      const table = tableContainer.value.querySelector('table');
      if (!table) return;

      const headerCells = table.querySelectorAll('thead th');
      const rows = table.querySelectorAll('tbody tr');
      
      // 计算左侧偏移
      let leftOffset = 0;
      const leftCount = props.freeze.left || 0;
      
      for (let i = 0; i < leftCount && i < headerCells.length; i++) {
        const cell = headerCells[i];
        cell.style.setProperty('--freeze-left', `${leftOffset}px`);
        cell.classList.add('freeze-col', 'freeze-left');
        
        // 同步设置 tbody 单元格
        rows.forEach(row => {
          const td = row.cells[i];
          if (td) {
            td.style.setProperty('--freeze-left', `${leftOffset}px`);
            td.classList.add('freeze-col', 'freeze-left');
          }
        });
        
        leftOffset += cell.offsetWidth;
      }

      // 计算右侧偏移
      let rightOffset = 0;
      const rightCount = props.freeze.right || 0;
      const totalCols = headerCells.length;
      
      for (let i = 0; i < rightCount && i < totalCols; i++) {
        const colIndex = totalCols - 1 - i;
        const cell = headerCells[colIndex];
        cell.style.setProperty('--freeze-right', `${rightOffset}px`);
        cell.classList.add('freeze-col', 'freeze-right');
        
        rows.forEach(row => {
          const td = row.cells[colIndex];
          if (td) {
            td.style.setProperty('--freeze-right', `${rightOffset}px`);
            td.classList.add('freeze-col', 'freeze-right');
          }
        });
        
        rightOffset += cell.offsetWidth;
      }
    };

    // 处理分页变化
    const handlePageChange = (page) => {
      if (page < 1 || page > totalPages.value) return;
      currentPage.value = page;
    };

    // 处理每页条数变化
    const handlePageSizeChange = (size) => {
      pageSize.value = size;
      currentPage.value = 1;
    };

    // 格式化单元格值
    const formatValue = (value) => {
      if (value === null || value === undefined) return '';
      if (typeof value === 'number') {
        // 保留两位小数
        return Number.isInteger(value) ? value : value.toFixed(2);
      }
      return value;
    };

    // 获取单元格样式类
    const getCellClass = (value) => {
      if (typeof value === 'number') {
        return value >= 0 ? 'positive' : 'negative';
      }
      return '';
    };

    // ========== 生命周期 ==========
    
    onMounted(() => {
      // 注入冻结列样式（如果还没有）
      injectFreezeStyles();
      
      // 应用冻结样式
      if (hasFreeze.value) {
        nextTick(() => {
          applyFreezeStyles();
          
          // 监听表格大小变化
          resizeObserver.value = new ResizeObserver(() => {
            applyFreezeStyles();
          });
          
          if (tableContainer.value) {
            resizeObserver.value.observe(tableContainer.value);
          }
        });
      }
    });

    onUnmounted(() => {
      if (resizeObserver.value) {
        resizeObserver.value.disconnect();
      }
    });

    // 监听数据变化，重新应用冻结样式
    watch(() => props.data, () => {
      if (hasFreeze.value) {
        nextTick(() => {
          applyFreezeStyles();
        });
      }
    }, { deep: true });

    // 监听列变化
    watch(() => props.cols, () => {
      if (hasFreeze.value) {
        nextTick(() => {
          applyFreezeStyles();
        });
      }
    });

    // ========== 注入 CSS ==========
    
    const injectFreezeStyles = () => {
      if (document.getElementById('vue-table-freeze-styles')) return;
      
      const style = document.createElement('style');
      style.id = 'vue-table-freeze-styles';
      style.textContent = `
        .vue-table-container {
          overflow-x: auto;
          position: relative;
        }
        
        .vue-table {
          width: 100%;
          border-collapse: separate;
          border-spacing: 0;
          font-size: 14px;
          text-align: left;
        }
        
        .vue-table th,
        .vue-table td {
          white-space: nowrap;
          min-width: 80px;
          background: white;
          padding: 10px 12px;
          border-bottom: 1px solid #eee;
        }
        
        .vue-table th {
          background: #f7f6f3;
          font-weight: 600;
          border-bottom: 2px solid #e9e9e9;
          cursor: pointer;
          user-select: none;
        }
        
        .vue-table th:hover {
          background: #e9e9e9;
        }
        
        .vue-table tbody tr:hover td {
          background: #fafafa;
        }
        
        /* 冻结列 */
        .vue-table-freeze .freeze-col {
          position: sticky;
          background: inherit;
          z-index: 50;
        }
        
        /* 表头冻结 */
        .vue-table-freeze thead th {
          position: sticky;
          top: 0;
          background: #f7f6f3;
          z-index: 100;
        }
        
        .vue-table-freeze thead .freeze-col {
          z-index: 150;
        }
        
        /* 左侧冻结 */
        .vue-table-freeze .freeze-left {
          left: var(--freeze-left, 0);
        }
        
        .vue-table-freeze .freeze-left::after {
          content: '';
          position: absolute;
          right: 0;
          top: 0;
          bottom: 0;
          width: 2px;
          background: linear-gradient(to right, rgba(0,0,0,0.1), transparent);
        }
        
        /* 右侧冻结 */
        .vue-table-freeze .freeze-right {
          right: var(--freeze-right, 0);
        }
        
        .vue-table-freeze .freeze-right::before {
          content: '';
          position: absolute;
          left: 0;
          top: 0;
          bottom: 0;
          width: 2px;
          background: linear-gradient(to left, rgba(0,0,0,0.1), transparent);
        }
        
        /* 排序指示器 */
        .vue-table .sort-indicator {
          margin-left: 5px;
          font-size: 12px;
          color: #e64340;
        }
        
        .vue-table .sort-priority {
          font-size: 10px;
          margin-right: 2px;
        }
        
        /* 正负增长 */
        .vue-table .positive {
          color: #e64340;
        }
        
        .vue-table .negative {
          color: #00b300;
        }
        
        /* 分页 */
        .vue-table-pagination {
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 10px 0;
          gap: 10px;
          flex-wrap: wrap;
        }
        
        .vue-table-pagination button {
          padding: 5px 10px;
          border: 1px solid #e9e9e9;
          background-color: #fff;
          color: #333;
          cursor: pointer;
          border-radius: 3px;
          transition: all 0.2s;
        }
        
        .vue-table-pagination button:hover:not(:disabled) {
          background-color: #f5f5f5;
        }
        
        .vue-table-pagination button:disabled {
          background-color: #f5f5f5;
          color: #999;
          cursor: not-allowed;
        }
        
        .vue-table-pagination select {
          padding: 5px;
          border: 1px solid #e0e0e0;
          border-radius: 3px;
        }
        
        .vue-table-pagination .page-info {
          font-size: 13px;
          color: #666;
        }
      `;
      document.head.appendChild(style);
    };

    return {
      tableContainer,
      displayCols,
      paginatedData,
      currentPage,
      totalPages,
      totalRecords,
      pageSize,
      hasFreeze,
      pageLimits,
      handleSort,
      handleMultiSort,
      getSortIndicator,
      isFreezeCol,
      getFreezeClass,
      handlePageChange,
      handlePageSizeChange,
      formatValue,
      getCellClass
    };
  },

  template: `
    <div class="vue-table-wrapper">
      <div 
        ref="tableContainer"
        class="vue-table-container"
        :class="{ 'vue-table-freeze': hasFreeze }"
      >
        <table class="vue-table">
          <thead>
            <tr>
              <th 
                v-for="(col, index) in displayCols" 
                :key="col.field"
                :class="getFreezeClass(index)"
                @click="handleMultiSort(col, $event)"
              >
                {{ col.title }}
                <span class="sort-indicator" v-html="getSortIndicator(col)"></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in paginatedData" :key="rowIndex">
              <td 
                v-for="(col, colIndex) in displayCols" 
                :key="col.field"
                :class="[getFreezeClass(colIndex), getCellClass(row[col.field])]"
              >
                {{ formatValue(row[col.field]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <!-- 分页 -->
      <div v-if="page" class="vue-table-pagination">
        <button 
          @click="handlePageChange(currentPage - 1)"
          :disabled="currentPage <= 1"
        >
          上一页
        </button>
        
        <span class="page-info">
          第 {{ currentPage }} / {{ totalPages }} 页，共 {{ totalRecords }} 条
        </span>
        
        <button 
          @click="handlePageChange(currentPage + 1)"
          :disabled="currentPage >= totalPages"
        >
          下一页
        </button>
        
        <select v-model="pageSize" @change="handlePageSizeChange(pageSize)">
          <option v-for="limit in pageLimits" :key="limit" :value="limit">
            {{ limit }} 条/页
          </option>
        </select>
      </div>
    </div>
  `
};

// 全局注册（CDN 使用方式）
if (typeof window !== 'undefined' && window.Vue) {
  window.VueTable = VueTable;
}

// ES Module 导出
if (typeof exports !== 'undefined') {
  exports.VueTable = VueTable;
}
