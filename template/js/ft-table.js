/**
 * FT Table Component v1.5.20260313-1
 * 版本号说明：主版本。次版本。日期（YYYYMMDD）-修订号
 * 基于 alpine-table.js 重构，适配 Vue 3 组合式 API
 * 
 * v1.3 新增热力图功能（heatmap）
 * v1.3.20260313-1 优化：热力图单元格禁用正负颜色类，避免字体颜色与背景色冲突
 * v1.4 重构分页参数：新增 page 参数，pagination 降级为兼容
 * v1.5 新版 page 参数优先，pagination 后期移除
 * 
 * ============================================
 * 参数说明
 * ============================================
 * data         Array            表格数据源（必需）
 * cols         Array            列配置（必需）
 * page         Object|Boolean   新版分页配置（推荐），false 禁用（默认 false）
 * pagination   Object|Boolean   旧版分页配置（兼容），后期移除
 * freeze       Object           冻结列配置 { left: 0, right: 0 }
 * heatmap      Object           热力图配置（列级别或全局）
 * resetPage    Boolean          数据变化时自动重置到第一页（默认 true）
 * 
 * ============================================
 * 列配置（cols）详解
 * ============================================
 * field        String   字段名（必需）
 * title        String   列标题（必需）
 * sort         Boolean  是否可排序，false 禁用（默认 true）
 * width        Number   列宽度（可选）
 * slot         String   自定义插槽名称（可选，默认 cell-{field}）
 * heatmap      Object   列级别热力图配置（可选）
 * 
 * heatmap 配置（列级别）:
 *   {}                          独立色阶，按列归一化，使用默认颜色
 *   { colors: [...] }           独立色阶 + 自定义颜色
 *   { group: 'name' }           分组色阶 + 默认颜色
 *   { group: 'name', colors: [...] }  分组色阶 + 自定义颜色
 * 
 * colors 说明:
 *   2 色：['#e3f2fd', '#1565c0']  浅蓝→深蓝
 *   3 色：['#2196f3', '#fff', '#f44336']  蓝→白→红（默认，A 股配色：红涨蓝跌）
 * 
 * 列配置示例:
 * { field: 'name', title: '名称', sort: false, width: 120 }
 * { field: 'change', title: '涨跌幅', heatmap: {} }
 * { field: 'c1', title: 'C 列', heatmap: { group: 'g1' } }
 * { field: 'c2', title: 'D 列', heatmap: { group: 'g1' } }  // 与 C 列共享范围
 * { field: 'score', title: '分数', heatmap: { colors: ['#e8f5e9', '#1b5e20'] } }
 * 
 * ============================================
 * 使用示例
 * ============================================
 * 
 * // 1. 定义数据
 * const tableData = [
 *   { code: "001", name: "苹果", price: 5.80 },
 *   { code: "002", name: "香蕉", price: 3.20 }
 * ];
 * 
 * // 2. 定义列（支持两种格式）
 * // 格式 A：字符串数组
 * const cols1 = ["代码", "名称", "价格"];
 * 
 * // 格式 B：对象数组
 * const cols2 = [
 *   { field: "code", title: "代码" },
 *   { field: "name", title: "名称" },
 *   { field: "price", title: "价格", sort: false }
 * ];
 * 
 * // 3. 模板使用
 * &lt;ft-table 
 *   :data="tableData" 
 *   :cols="cols"
 *   :page="{ size: 20 }"
 *   :freeze="{ left: 2 }"
 * &gt;&lt;/ft-table&gt;
 * 
 * ============================================
 * 参数详解
 * ============================================
 * 
 * page 配置（新版，推荐，默认启用分页）:
 *   不传参数                    // 默认分页，每页 10 条
 *   { size: 20 }               // 启用分页，每页 20 条
 *   { size: 20, options: [10, 20, 50, 100] }  // 自定义每页条数选项
 *   false                      // 禁用分页
 * 
 * pagination 配置（旧版，兼容，后期移除）:
 *   { pageSize: 20 }                  // 启用分页，每页 20 条
 *   { pageSize: 20, pageSizeOptions: [10, 20, 50, 100] }
 * 
 * freeze 配置:
 *   { left: 2 }                         // 冻结左侧 2 列
 *   { right: 1 }                        // 冻结右侧 1 列
 *   { left: 2, right: 1 }               // 同时冻结左右
 * 
 * heatmap 配置（全局）:
 *   { start: 2 }                        // 从第 2 列开始应用热力图
 *   { start: 2, end: 5 }                // 第 2-5 列（1-based，包含 end）
 *   { start: 2, end: -2 }               // 第 2 列到倒数第 2 列
 *   { start: 2, exclude: [5, 6] }       // 第 2 列开始，排除第 5、6 列
 *   { columns: ['change', 'volume'] }   // 指定列名（优先于 start/end）
 *   { colors: ['#e8f5e9', '#1b5e20'] }  // 自定义颜色（2 色或 3 色）
 *   { axis: 'column' }                  // 归一化方式：'column'按列 | 'table'全表
 *   { excludeRows: [-1] }               // 排除最后一行（汇总行）
 * 
 * heatmap 全局参数详解:
 *   start        Number    起始列索引（1-based，默认 1）
 *                - 正数: 从左到右第 N 列，如 2 表示第 2 列
 *                - 负数: 从右到左计算，如 -1 表示最后一列
 *   end          Number    结束列索引（1-based，默认 -1 表示最后一列）
 *                - 正数: 从左到右第 N 列
 *                - 负数: 从右到左计算，如 -2 表示倒数第 2 列
 *   exclude      Array     排除的列索引数组（1-based，支持负数）
 *                - [5, 6] 排除第 5、6 列
 *                - [-1]   排除最后一列
 *   columns      Array     直接指定应用热力图的列名（优先于 start/end）
 *                - ['change', 'volume'] 仅对这两列应用热力图
 *                - 优先级: columns > start/end > 默认全表
 *   colors       Array     自定义颜色（2 色或 3 色）
 *                - 2 色: ['#e3f2fd', '#1565c0'] 浅蓝→深蓝（低→高）
 *                - 3 色: ['#2196f3', '#fff', '#f44336'] 蓝→白→红（低→中→高）
 *                - 默认: ['#2196f3', '#fff', '#f44336'] A 股配色（蓝跌 白中立 红涨）
 *   axis         String    归一化方式（决定颜色渐变的范围）
 *                - 'column': 每列独立归一化（默认，每列独立色阶）
 *                - 'table':  全表统一归一化（所有列共享同一色阶）
 *   excludeRows  Array     排除参与热力图计算的行索引（支持负数）
 *                - [-1]     排除最后一行（常用于汇总行/合计行不参与计算）
 *                - [0]      排除第一行
 *                - [-1, -2] 排除最后两行
 *                - 注意: 仅排除计算，不排除渲染
 * 
 * 使用示例:
 *   // 示例 1: 对第 3-10 列应用热力图，排除第 5、6 列
 *   { start: 3, end: 10, exclude: [5, 6] }
 *   
 *   // 示例 2: 对指定列应用热力图，统一色阶（便于跨列比较）
 *   { columns: ['open', 'high', 'low', 'close'], axis: 'table' }
 *   
 *   // 示例 3: 使用自定义双色（绿色渐变）
 *   { start: 2, colors: ['#c8e6c9', '#1b5e20'] }
 *   
 *   // 示例 4: 排除汇总行（最后一行不参与归一化计算）
 *   { columns: ['amount'], excludeRows: [-1] }
 *   
 *   // 示例 5: 综合配置
 *   { 
 *     start: 2, 
 *     exclude: [3], 
 *     colors: ['#2196f3', '#fff', '#f44336'],
 *     axis: 'column',
 *     excludeRows: [-1]
 *   }
 * 
 * 列级别热力图优先级高于全局热力图
 * 
 * colors 说明（全局）:
 *   3 色：['#2196f3', '#fff', '#f44336']  蓝→白→红（默认，A 股配色）
 *   2 色：['#e3f2fd', '#1565c0']  浅蓝→深蓝
 * 
 * ============================================
 * 模板结构
 * ============================================
 * <div class="ft-table-wrapper">
 *   <div class="ft-table-container">
 *     <table class="ft-table">
 *       <thead><tr><th>列标题</th></tr></thead>
 *       <tbody><tr><td>单元格</td></tr></tbody>
 *     </table>
 *   </div>
 *   <div class="ft-table-pagination">分页器</div>
 * </div>
 */

const FtTable = {
  name: 'FtTable',
  
  props: {
    data: {
      type: Array,
      default: () => []
    },
    cols: {
      type: Array,
      default: () => []
    },
    page: {
      type: [Object, Boolean],
      default: () => ({ size: 10, options: [10, 20, 50, 100] })
    },
    pagination: {
      type: [Object, Boolean],
      default: false
    },
    freeze: {
      type: Object,
      default: () => ({ left: 0, right: 0 })
    },
    heatmap: {
      type: [Object, Boolean],
      default: false
    },
    emptyText: {
      type: String,
      default: '暂无数据'
    },
    resetPage: {
      type: Boolean,
      default: true
    }
  },

  setup(props, { slots }) {
    const { ref, computed, onMounted, onUnmounted, watch, nextTick } = Vue;
    
    // ========== 响应式数据 ==========
    // page 参数默认启用分页，设为 false 禁用
    const pageConfig = computed(() => {
      if (props.page === false) return false;
      return props.page || props.pagination;
    });
    
    const currentPage = ref(1);
    const pageSize = ref(pageConfig.value?.size || pageConfig.value?.pageSize || 10);
    const multiSort = ref([]);
    const tableContainer = ref(null);
    const resizeObserver = ref(null);

    // ========== 计算属性 ==========
    
    // 排序后的数据
    const sortedData = computed(() => {
      if (multiSort.value.length === 0) {
        return props.data;
      }
      
      return [...props.data].sort((a, b) => {
        for (const sort of multiSort.value) {
          const v1 = a[sort.field];
          const v2 = b[sort.field];
          if (v1 !== v2) {
            return sort.order === 'asc' ? (v1 > v2 ? 1 : -1) : (v1 < v2 ? 1 : -1);
          }
        }
        return 0;
      });
    });

    // 分页后的数据
    const paginatedData = computed(() => {
      if (!pageConfig.value) return sortedData.value;
      const start = (currentPage.value - 1) * pageSize.value;
      return sortedData.value.slice(start, start + pageSize.value);
    });

    // 总页数
    const totalPages = computed(() => {
      if (!pageConfig.value) return 1;
      return Math.ceil(props.data.length / pageSize.value) || 1;
    });

    // 总记录数
    const totalRecords = computed(() => props.data.length);

    // 显示的列（处理 cols 格式）
    // cols 可选：不传或无效时自动推断所有字段
    const displayCols = computed(() => {
      // 检查 cols 是否有效数组
      const isValidCols = Array.isArray(props.cols) && props.cols.length > 0;
      
      if (isValidCols) {
        // 处理字符串数组格式 ["代码", "名称"] → [{field: "代码", title: "代码", slot: "cell-代码"}]
        return props.cols.map(col => {
          if (typeof col === 'string') {
            return { field: col, title: col, slot: 'cell-' + col };
          }
          // 处理对象格式，自动生成 slot 名称
          const slotName = col.slot || (col.field ? 'cell-' + col.field : null);
          return { ...col, slot: slotName };
        });
      }
      
      // cols 无效或为空：从数据自动推断所有字段
      if (props.data && props.data.length > 0) {
        return Object.keys(props.data[0]).map(key => ({
          field: key,
          title: key,
          slot: 'cell-' + key
        }));
      }
      return [];
    });
    
    // 检查是否有自定义插槽
    const hasSlot = (slotName) => {
      return slotName && slots[slotName];
    };

    // 是否有冻结列
    const hasFreeze = computed(() => {
      return props.freeze && (props.freeze.left > 0 || props.freeze.right > 0);
    });

    // 是否启用热力图（全局或列级别）
    const hasHeatmap = computed(() => {
      if (props.heatmap && typeof props.heatmap === 'object') {
        return true;
      }
      return displayCols.value.some(col => col.heatmap);
    });

    // 解析列的热力图配置
    const parseColHeatmap = (col) => {
      if (!col.heatmap) return null;
      
      if (typeof col.heatmap === 'object') {
        return {
          enabled: true,
          group: col.heatmap.group || col.field,
          colors: col.heatmap.colors || null
        };
      }
      
      return null;
    };

    // 热力图配置（合并默认值）
    const heatmapConfig = computed(() => {
      if (!props.heatmap || props.heatmap === true) {
        return null;
      }
      
      const defaults = {
        start: 1,
        end: -1,
        exclude: [],
        excludeRows: [],
        columns: null,
        colors: ['#2196f3', '#fff', '#f44336'],
        axis: 'column'
      };
      
      return { ...defaults, ...props.heatmap };
    });

    // 热力图范围缓存（支持分组）
    const heatmapRanges = computed(() => {
      const data = paginatedData.value;
      const cols = displayCols.value;
      
      if (data.length === 0) return {};
      
      const ranges = {};
      const groupValues = {};
      
      const hasGlobalHeatmap = props.heatmap && typeof props.heatmap === 'object';
      const hasColHeatmap = cols.some(col => col.heatmap);
      
      if (!hasGlobalHeatmap && !hasColHeatmap) {
        return ranges;
      }
      
      const excludeRowsSet = new Set(
        (heatmapConfig.value?.excludeRows || []).map(idx => idx < 0 ? data.length + idx : idx)
      );
      const validRows = data.filter((_, idx) => !excludeRowsSet.has(idx));
      
      if (hasColHeatmap) {
        cols.forEach(col => {
          const colHeatmap = parseColHeatmap(col);
          if (!colHeatmap) return;
          
          const groupName = colHeatmap.group;
          
          if (!groupValues[groupName]) {
            groupValues[groupName] = [];
          }
          
          validRows.forEach(row => {
            const v = row[col.field];
            if (typeof v === 'number' && !isNaN(v)) {
              groupValues[groupName].push(v);
            }
          });
        });
        
        Object.keys(groupValues).forEach(groupName => {
          const values = groupValues[groupName];
          if (values.length > 0) {
            ranges[groupName] = {
              min: Math.min(...values),
              max: Math.max(...values)
            };
          }
        });
      }
      
      if (hasGlobalHeatmap) {
        const config = heatmapConfig.value;
        
        if (config.columns && config.columns.length > 0) {
          config.columns.forEach(field => {
            const values = validRows
              .map(row => row[field])
              .filter(v => typeof v === 'number' && !isNaN(v));
            
            if (values.length > 0) {
              ranges[field] = {
                min: Math.min(...values),
                max: Math.max(...values)
              };
            }
          });
        } else {
          const config = heatmapConfig.value;
          const totalCols = cols.length;
          const start = config.start > 0 ? config.start - 1 : totalCols + config.start;
          const end = config.end > 0 ? config.end - 1 : totalCols + config.end;
          const excludeSet = new Set((config.exclude || []).map(v => {
            return v > 0 ? v - 1 : totalCols + v;
          }));
          
          const heatmapCols = [];
          for (let i = start; i <= end; i++) {
            if (i >= 0 && i < totalCols && !excludeSet.has(i)) {
              heatmapCols.push(cols[i]);
            }
          }
          
          if (config.axis === 'column') {
            heatmapCols.forEach(col => {
              if (col.heatmap) return;
              
              const values = validRows
                .map(row => row[col.field])
                .filter(v => typeof v === 'number' && !isNaN(v));
              
              if (values.length > 0) {
                ranges[col.field] = {
                  min: Math.min(...values),
                  max: Math.max(...values)
                };
              }
            });
          } else if (config.axis === 'table') {
            const allValues = [];
            heatmapCols.forEach(col => {
              if (col.heatmap) return;
              validRows.forEach(row => {
                const v = row[col.field];
                if (typeof v === 'number' && !isNaN(v)) {
                  allValues.push(v);
                }
              });
            });
            
            if (allValues.length > 0) {
              const globalRange = {
                min: Math.min(...allValues),
                max: Math.max(...allValues)
              };
              heatmapCols.forEach(col => {
                if (!col.heatmap) {
                  ranges[col.field] = globalRange;
                }
              });
            }
          }
        }
      }
      
      return ranges;
    });

    // 分页选项
    const pageSizeOptions = computed(() => {
      return pageConfig.value?.options || pageConfig.value?.pageSizeOptions || [10, 20, 50, 100];
    });

    // 生成显示的页码数组（首页 上一页 1 2 3 4 5 末页）
    const visiblePages = computed(() => {
      const total = totalPages.value;
      const current = currentPage.value;
      const maxVisible = 5; // 显示 5 个页码
      
      if (total <= maxVisible) {
        // 总页数少于 5 个，全部显示
        return Array.from({ length: total }, (_, i) => i + 1);
      }
      
      // 固定显示 5 个页码，当前页居中（如果可能）
      let start = Math.max(1, current - Math.floor(maxVisible / 2));
      let end = start + maxVisible - 1;
      
      // 调整边界
      if (end > total) {
        end = total;
        start = total - maxVisible + 1;
      }
      
      return Array.from({ length: end - start + 1 }, (_, i) => start + i);
    });

    // ========== 方法 ==========
    
    // 排序处理 - 按点击顺序形成优先级
    const handleSort = (col) => {
      const field = col.field;
      const existingIndex = multiSort.value.findIndex(s => s.field === field);
      
      if (existingIndex >= 0) {
        const existing = multiSort.value[existingIndex];
        if (existing.order === 'desc') {
          existing.order = 'asc';
        } else {
          multiSort.value.splice(existingIndex, 1);
          multiSort.value.forEach((item, idx) => {
            item.priority = idx + 1;
          });
        }
      } else {
        multiSort.value.push({ field, order: 'desc', priority: multiSort.value.length + 1 });
      }
      
      currentPage.value = 1;
    };

    // 获取排序指示器（返回对象供模板使用）
    const getSortIndicator = (col) => {
      const multiIndex = multiSort.value.findIndex(s => s.field === col.field);
      if (multiIndex >= 0) {
        const sort = multiSort.value[multiIndex];
        return {
          show: true,
          icon: sort.order === 'asc' ? '▲' : '▼',
          priority: sort.priority
        };
      }
      return { show: false };
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
      return index < left ? 'freeze-col freeze-left' : 'freeze-col freeze-right';
    };

    // 应用冻结列样式
    const applyFreezeStyles = () => {
      if (!hasFreeze.value || !tableContainer.value) return;
      
      const table = tableContainer.value.querySelector('table');
      if (!table) return;

      const headerCells = table.querySelectorAll('thead th');
      const rows = table.querySelectorAll('tbody tr');
      
      // 获取实际列宽
      const colWidths = Array.from(headerCells).map(th => th.offsetWidth);
      
      // 左侧冻结
      let leftOffset = 0;
      const leftCount = props.freeze.left || 0;
      
      for (let i = 0; i < leftCount && i < headerCells.length; i++) {
        headerCells[i].style.left = `${leftOffset}px`;
        rows.forEach(row => {
          if (row.cells[i]) row.cells[i].style.left = `${leftOffset}px`;
        });
        leftOffset += colWidths[i];
      }

      // 右侧冻结
      let rightOffset = 0;
      const rightCount = props.freeze.right || 0;
      const totalCols = colWidths.length;
      
      for (let i = 0; i < rightCount && i < totalCols; i++) {
        const colIndex = totalCols - 1 - i;
        headerCells[colIndex].style.right = `${rightOffset}px`;
        rows.forEach(row => {
          if (row.cells[colIndex]) row.cells[colIndex].style.right = `${rightOffset}px`;
        });
        rightOffset += colWidths[colIndex];
      }
    };

    // 重置分页到第一页
    const resetPage = () => {
      currentPage.value = 1;
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
        return Number.isInteger(value) ? value : value.toFixed(2);
      }
      return value;
    };

    // 获取单元格样式类
    const getCellClass = (value, col, colIndex, rowIndex) => {
      // 如果在热力图范围内，不应用正负颜色类（避免与热力图背景色冲突）
      if (isHeatmapCell(col, colIndex, rowIndex)) {
        return '';
      }
      if (typeof value === 'number') {
        return value >= 0 ? 'positive' : 'negative';
      }
      return '';
    };

    // 颜色插值计算（支持双色/三色）
    const interpolateColor = (colors, ratio) => {
      if (!colors || colors.length < 2) return '#ffffff';
      
      if (colors.length === 2) {
        return interpolateTwoColors(colors[0], colors[1], ratio);
      }
      
      if (ratio <= 0.5) {
        return interpolateTwoColors(colors[0], colors[1], ratio * 2);
      } else {
        return interpolateTwoColors(colors[1], colors[2], (ratio - 0.5) * 2);
      }
    };

    // 双色插值
    const interpolateTwoColors = (color1, color2, ratio) => {
      // 处理 3 位简写颜色 (#fff → #ffffff)
      const expandHex = (hex) => {
        hex = hex.replace('#', '');
        if (hex.length === 3) {
          return hex.split('').map(c => c + c).join('');
        }
        return hex;
      };
      
      const hex1 = expandHex(color1);
      const hex2 = expandHex(color2);
      
      const r1 = parseInt(hex1.substring(0, 2), 16);
      const g1 = parseInt(hex1.substring(2, 4), 16);
      const b1 = parseInt(hex1.substring(4, 6), 16);
      
      const r2 = parseInt(hex2.substring(0, 2), 16);
      const g2 = parseInt(hex2.substring(2, 4), 16);
      const b2 = parseInt(hex2.substring(4, 6), 16);
      
      const r = Math.round(r1 + (r2 - r1) * ratio);
      const g = Math.round(g1 + (g2 - g1) * ratio);
      const b = Math.round(b1 + (b2 - b1) * ratio);
      
      return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
    };

    // 判断单元格是否在热力图范围内
    const isHeatmapCell = (col, colIndex, rowIndex) => {
      if (!hasHeatmap.value) return false;
      
      if (isFreezeCol(colIndex)) return false;
      
      if (col.heatmap) return true;
      
      const hasGlobalHeatmap = props.heatmap && typeof props.heatmap === 'object';
      if (!hasGlobalHeatmap) return false;
      
      const config = heatmapConfig.value;
      if (!config) return false;
      
      const cols = displayCols.value;
      const data = paginatedData.value;
      
      const excludeRowsSet = new Set(
        (config.excludeRows || []).map(idx => idx < 0 ? data.length + idx : idx)
      );
      
      if (excludeRowsSet.has(rowIndex)) return false;
      
      if (config.columns && config.columns.length > 0) {
        return config.columns.includes(col.field);
      }
      
      const totalCols = cols.length;
      const start = config.start > 0 ? config.start - 1 : totalCols + config.start;
      const end = config.end > 0 ? config.end - 1 : totalCols + config.end;
      const excludeSet = new Set((config.exclude || []).map(v => {
        return v > 0 ? v - 1 : totalCols + v;
      }));
      
      if (colIndex < start || colIndex > end) return false;
      if (excludeSet.has(colIndex)) return false;
      
      return true;
    };

    // 获取单元格热力图样式
    const getHeatmapStyle = (value, col, colIndex, rowIndex) => {
      if (!hasHeatmap.value) return {};
      if (!isHeatmapCell(col, colIndex, rowIndex)) return {};
      if (typeof value !== 'number' || isNaN(value)) return {};
      
      const config = heatmapConfig.value;
      const ranges = heatmapRanges.value;
      
      let colors = config?.colors || ['#2196f3', '#fff', '#f44336'];
      let rangeKey = col.field;
      
      const colHeatmap = parseColHeatmap(col);
      if (colHeatmap) {
        if (colHeatmap.colors) {
          colors = colHeatmap.colors;
        }
        rangeKey = colHeatmap.group;
      }
      
      const range = ranges[rangeKey];
      
      if (!range) return {};
      
      const { min, max } = range;
      if (min === max) {
        const midColor = colors.length === 3 ? colors[1] : colors[1];
        return { 
          'background-color': midColor,
          '--heatmap-bg': midColor
        };
      }
      
      const ratio = (value - min) / (max - min);
      const bgColor = interpolateColor(colors, ratio);
      
      return { 
        'background-color': bgColor,
        '--heatmap-bg': bgColor
      };
    };

    // ========== 生命周期 ==========
    
    onMounted(() => {
      injectTableStyles();
      
      if (hasFreeze.value) {
        nextTick(() => {
          applyFreezeStyles();
          
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

    // 监听数据变化
    watch(() => props.data, () => {
      // 如果 resetPage 为 true，数据变化时重置到第一页
      if (props.resetPage) {
        resetPage();
      } else {
        // 即使不重置，也要确保当前页不超过总页数
        nextTick(() => {
          if (currentPage.value > totalPages.value) {
            currentPage.value = totalPages.value;
          }
        });
      }
      if (hasFreeze.value) {
        nextTick(() => {
          applyFreezeStyles();
        });
      }
    }, { deep: true });

    // 监听列变化
    watch(() => displayCols.value, () => {
      if (hasFreeze.value) {
        nextTick(() => {
          applyFreezeStyles();
        });
      }
    });

    // 监听分页变化
    watch(currentPage, () => {
      if (hasFreeze.value) {
        nextTick(() => {
          applyFreezeStyles();
        });
      }
    });

    // 监听 freeze 配置变化
    watch(() => props.freeze, () => {
      if (hasFreeze.value) {
        nextTick(() => {
          applyFreezeStyles();
        });
      }
    }, { deep: true });

    // ========== 注入 CSS ==========
    // 仅注入冻结列必需的最简样式
    // 其他样式（表格基础、分页等）请引入 ft-table.css
    const injectTableStyles = () => {
      const styleId = 'ft-table-freeze-core';
      if (document.getElementById(styleId)) return;
      
      const style = document.createElement('style');
      style.id = styleId;
      style.textContent = `
        /* 冻结列核心样式 - 组件必需 */
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
        /* 排序图标基础样式 - 保证无外部样式时依然可辨识 */
        span.sort-icon {
          font-size: 0.8em;
        }
        span.sort-priority {
          font-size: 0.7em;
        }
        /* 热力图单元格样式 - 确保背景色优先级最高 */
        .ft-table td.heatmap-cell {
          background-color: var(--heatmap-bg) !important;
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
      pageConfig,
      hasFreeze,
      hasHeatmap,
      pageSizeOptions,
      visiblePages,
      handleSort,
      getSortIndicator,
      isFreezeCol,
      getFreezeClass,
      handlePageChange,
      handlePageSizeChange,
      formatValue,
      getCellClass,
      isHeatmapCell,
      getHeatmapStyle,
      hasSlot,
      resetPage
    };
  },

  template: `
    <div class="ft-table-wrapper">
      <div 
        ref="tableContainer"
        class="ft-table-container"
        :class="{ 'ft-table-freeze': hasFreeze }"
      >
        <table class="ft-table">
          <thead>
            <tr>
              <th 
                v-for="(col, index) in displayCols" 
                :key="col.field"
                :class="[getFreezeClass(index), { 'no-sort': col.sort === false }]"
                @click="col.sort !== false && handleSort(col)"
              >
                {{ col.title }}
                <template v-if="col.sort !== false" v-for="indicator in [getSortIndicator(col)]" :key="col.field + '-indicator'">
                  <span v-if="indicator.show" class="sort-indicator">
                    <span class="sort-priority">{{ indicator.priority }}</span>
                    <span class="sort-icon">{{ indicator.icon }}</span>
                  </span>
                </template>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in paginatedData" :key="rowIndex">
              <td 
                v-for="(col, colIndex) in displayCols" 
                :key="col.field"
                :class="[getFreezeClass(colIndex), getCellClass(row[col.field], col, colIndex, rowIndex), { 'heatmap-cell': isHeatmapCell(col, colIndex, rowIndex) }]"
                :style="getHeatmapStyle(row[col.field], col, colIndex, rowIndex)"
              >
                <!-- 有插槽：调用插槽渲染 -->
                <template v-if="col.slot && $slots[col.slot]">
                  <slot :name="col.slot" :row="row" :value="row[col.field]" :index="rowIndex" />
                </template>
                <!-- 无插槽：默认渲染 -->
                <template v-else>
                  {{ formatValue(row[col.field]) }}
                </template>
              </td>
            </tr>
          </tbody>
        </table>
        
        <!-- 空数据提示 -->
        <div v-if="paginatedData.length === 0" class="ft-table-empty">
          {{ emptyText }}
        </div>
      </div>
      
      <!-- 分页 -->
      <div v-if="pageConfig !== false" class="ft-table-pagination">
        <!-- 首页 -->
        <button 
          @click="handlePageChange(1)"
          :disabled="currentPage <= 1"
          class="page-btn"
        >
          首页
        </button>
        
        <!-- 上一页 -->
        <button 
          @click="handlePageChange(currentPage - 1)"
          :disabled="currentPage <= 1"
          class="page-btn"
        >
          上一页
        </button>
        
        <!-- 页码 -->
        <button 
          v-for="page in visiblePages" 
          :key="page"
          @click="handlePageChange(page)"
          :class="['page-btn', { active: page === currentPage }]"
        >
          {{ page }}
        </button>
        
        <!-- 下一页 -->
        <button 
          @click="handlePageChange(currentPage + 1)"
          :disabled="currentPage >= totalPages"
          class="page-btn"
        >
          下一页
        </button>
        
        <!-- 末页 -->
        <button 
          @click="handlePageChange(totalPages)"
          :disabled="currentPage >= totalPages"
          class="page-btn"
        >
          末页
        </button>
        
        <!-- 分隔 -->
        <span class="page-info">
          第 {{ currentPage }} / {{ totalPages }} 页
        </span>
        
        <!-- 每页条数 -->
        <select v-model="pageSize" @change="handlePageSizeChange(pageSize)">
          <option v-for="size in pageSizeOptions" :key="size" :value="size">
            {{ size }}条/页
          </option>
        </select>
      </div>
    </div>
  `
};

// 全局暴露（CDN 使用方式）
if (typeof window !== 'undefined') {
  window.FtTable = FtTable;
  // 保留旧名称兼容
  window.VueTable = FtTable;
}

// ES Module 导出
if (typeof exports !== 'undefined') {
  exports.FtTable = FtTable;
  exports.VueTable = FtTable;
}
