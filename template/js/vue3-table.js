/**
 * Vue 3 Table Component
 * 基于 alpine-table.js 重构，适配 Vue 3 组合式 API
 * 
 * 使用方式（Ant Design 风格）：
 * <vue-table :id="'table-1'" :data-source="tableData" :columns="columns" :freeze="{left: 2}" :pagination="{pageSize: 20}"></vue-table>
 */

const VueTable = {
  name: 'VueTable',
  
  props: {
    id: {
      type: String,
      required: true
    },
    dataSource: {
      type: Array,
      default: () => []
    },
    columns: {
      type: Array,
      default: () => []
    },
    pagination: {
      type: [Object, Boolean],
      default: false
    },
    freeze: {
      type: Object,
      default: () => ({ left: 0, right: 0 })
    }
  },

  setup(props) {
    const { ref, computed, onMounted, onUnmounted, watch, nextTick } = Vue;
    
    // ========== 响应式数据 ==========
    const currentPage = ref(1);
    const pageSize = ref(props.pagination?.pageSize || 20);
    const sortField = ref('');
    const sortOrder = ref('asc');
    const multiSort = ref([]);
    const tableContainer = ref(null);
    const resizeObserver = ref(null);

    // ========== 计算属性 ==========
    
    // 排序后的数据
    const sortedData = computed(() => {
      if (!sortField.value && multiSort.value.length === 0) {
        return props.dataSource;
      }
      
      return [...props.dataSource].sort((a, b) => {
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
      if (!props.pagination) return sortedData.value;
      const start = (currentPage.value - 1) * pageSize.value;
      return sortedData.value.slice(start, start + pageSize.value);
    });

    // 总页数
    const totalPages = computed(() => {
      if (!props.pagination) return 1;
      return Math.ceil(props.dataSource.length / pageSize.value) || 1;
    });

    // 总记录数
    const totalRecords = computed(() => props.dataSource.length);

    // 显示的列（处理 columns 格式）
    const displayColumns = computed(() => {
      if (props.columns && props.columns.length > 0) {
        return props.columns;
      }
      // 从数据自动推断列
      if (props.dataSource.length > 0) {
        return Object.keys(props.dataSource[0]).map(key => ({
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
    const pageSizeOptions = computed(() => {
      return props.pagination?.pageSizeOptions || [10, 20, 50, 100];
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
      const total = displayColumns.value.length;
      
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
      // 注入表格样式（如果还没有）
      injectTableStyles();
      
      // 应用冻结样式（如果有冻结列）
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
    watch(() => props.dataSource, () => {
      if (hasFreeze.value) {
        nextTick(() => {
          applyFreezeStyles();
        });
      }
    }, { deep: true });

    // 监听列变化
    watch(() => displayColumns.value, () => {
      if (hasFreeze.value) {
        nextTick(() => {
          applyFreezeStyles();
        });
      }
    });

    // ========== 注入 CSS（仅冻结相关核心样式） ==========
    
    const injectTableStyles = () => {
      if (document.getElementById('vue-table-freeze-styles')) return;
      
      const style = document.createElement('style');
      style.id = 'vue-table-freeze-styles';
      style.textContent = `
        /* 冻结容器 */
        .vue-table-freeze {
          overflow-x: auto;
          position: relative;
        }
        
        /* 冻结列单元格 - 只设置 sticky 定位 */
        .vue-table-freeze .freeze-col {
          position: sticky;
        }
        
        /* 表头整体冻结在顶部（仅冻结模式） */
        .vue-table-freeze thead th {
          position: sticky;
          top: 0;
          z-index: 10;
        }
        
        /* 表头中的冻结列需要更高的 z-index */
        .vue-table-freeze thead .freeze-col {
          z-index: 100;
        }
        
        .vue-table-freeze tbody .freeze-col {
          z-index: 50;
        }
        
        /* 表格边框（仅冻结模式需要 separate） */
        .vue-table-freeze .vue-table {
          border-collapse: separate;
          border-spacing: 0;
        }
        
        /* 左侧冻结 - alpine-table.js 无此样式，新增增强 */
        .vue-table-freeze .freeze-left {
          left: var(--freeze-left, 0);
        }
        
        /* 左侧冻结阴影效果 - alpine-table.js 无此样式，新增增强 */
        .vue-table-freeze .freeze-left::after {
          content: '';
          position: absolute;
          right: 0;
          top: 0;
          bottom: 0;
          width: 2px;
          background: linear-gradient(to right, rgba(0,0,0,0.1), transparent);
        }
        
        /* 右侧冻结 - alpine-table.js 无此样式，新增增强 */
        .vue-table-freeze .freeze-right {
          right: var(--freeze-right, 0);
        }
        
        /* 右侧冻结阴影效果 - alpine-table.js 无此样式，新增增强 */
        .vue-table-freeze .freeze-right::before {
          content: '';
          position: absolute;
          left: 0;
          top: 0;
          bottom: 0;
          width: 2px;
          background: linear-gradient(to left, rgba(0,0,0,0.1), transparent);
        }
      `;
      document.head.appendChild(style);
    };

    return {
      tableContainer,
      displayColumns,
      paginatedData,
      currentPage,
      totalPages,
      totalRecords,
      pageSize,
      hasFreeze,
      pageSizeOptions,
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
                v-for="(col, index) in displayColumns" 
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
                v-for="(col, colIndex) in displayColumns" 
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
      <div v-if="pagination !== false" class="vue-table-pagination">
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
          <option v-for="size in pageSizeOptions" :key="size" :value="size">
            {{ size }} 条/页
          </option>
        </select>
      </div>
    </div>
  `
};

// 全局暴露（CDN 使用方式）
if (typeof window !== 'undefined') {
  window.VueTable = VueTable;
}

// ES Module 导出
if (typeof exports !== 'undefined') {
  exports.VueTable = VueTable;
}
