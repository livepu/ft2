/**
 * Alpine.js 表格组件
 * 
 * 功能特性:
 * - 支持从本地数据或远程URL加载数据
 * - 分页功能
 * - 多列排序（支持单列和多列排序）
 * - 自定义数据解析
 * - 响应式设计
 * 
 * 使用方法:
 * 
 * 1. 基础用法 - 静态数据:
 * ```html
 * <div x-data="table({
 *   data: [
 *     {id: 1, name: 'John', age: 30},
 *     {id: 2, name: 'Jane', age: 25}
 *   ],
 *   cols: [
 *     {field: 'id', title: 'ID'},
 *     {field: 'name', title: '姓名'},
 *     {field: 'age', title: '年龄'}
 *   ]
 * })">
 *   <!-- 表格和分页控件会自动渲染 -->
 * </div>
 * ```
 * 
 * 2. 远程数据加载:
 * ```html
 * <div x-data="table({
 *   url: '/api/users',
 *   cols: [
 *     {field: 'id', title: 'ID'},
 *     {field: 'name', title: '姓名'},
 *     {field: 'email', title: '邮箱'}
 *   ],
 *   parseData: function(res) {
 *     // 自定义数据解析函数
 *     return res.data.items;
 *   }
 * })">
 *   <!-- 表格和分页控件会自动渲染 -->
 * </div>
 * ```
 * 
 * 3. 从JSON脚本标签加载数据和列配置:
 * ```html
 * <!-- 数据源 -->
 * <script id="table-data" type="application/json">
 * [
 *   {"id": 1, "name": "John", "age": 30},
 *   {"id": 2, "name": "Jane", "age": 25}
 * ]
 * </script>
 *
 * <!-- 列配置源（可选）-->
 * <script id="table-cols" type="application/json">
 * [
 *   {"field": "id", "title": "ID"},
 *   {"field": "name", "title": "姓名"},
 *   {"field": "age", "title": "年龄"}
 * ]
 * </script>
 *
 * <div x-data="table({
 *   dataSrc: '#table-data',
 *   colsSrc: '#table-cols'  // 可选，如果不提供则自动从数据推断列定义
 * })">
 *   <!-- 表格和分页控件会自动渲染 -->
 * </div>
 * ```
 * 
 * 4. 自动列推断（不提供列配置时）:
 * 当不提供cols或colsSrc参数时，组件会自动从数据的第一项中提取所有键作为列定义:
 * ```html
 * <script id="table-data" type="application/json">
 * [
 *   {"员工编号": 1, "姓名": "张三", "部门": "技术部", "年龄": 25},
 *   {"员工编号": 2, "姓名": "李四", "部门": "市场部", "年龄": 30}
 * ]
 * </script>
 * 
 * <!-- 不提供列配置，自动从数据中推断 -->
 * <div x-data="table({ dataSrc: '#table-data' })">
 *   <!-- 表格和分页控件会自动渲染 -->
 *   <!-- 此时会自动生成列: 员工编号, 姓名, 部门, 年龄 -->
 * </div>
 * ```
 * 
 * 5. Python Pandas 数据适配:
 * 当使用 Python 的 Pandas 处理数据时，可以将其转换为如下格式:
 * ```python
 * # Python端
 * data = df.to_dict('records')  # 转换DataFrame为字典列表
 * cols = [{'field': col, 'title': col} for col in df.columns]  # 自动生成列定义
 * 
 * # 然后将data和cols传递给前端
 * ```
 * 
 * 前端使用:
 * ```html
 * <div x-data="table({
 *   data: {{ data|tojson }},  # Flask/Jinja2 模板语法
 *   cols: {{ cols|tojson }}
 * })">
 *   <!-- 表格和分页控件会自动渲染 -->
 * </div>
 * ```
 * 
 * 6. 自定义表格和分页控件:
 * 如果需要自定义表格或分页控件样式，可以在组件内添加.table-container和.pagination-container元素:
 * ```html
 * <div x-data="table({...})">
 *   <div class="table-container">
 *     <!-- 自定义表格 -->
 *   </div>
 *   <div class="pagination-container">
 *     <!-- 自定义分页控件 -->
 *   </div>
 * </div>
 * ```
 * 
 * CSS 样式参考:
 * ```css
 * .alpine-table-container {
 *   overflow-x: auto;
 * }
 * 
 * .alpine-table {
 *   width: 100%;
 *   border-collapse: collapse;
 *   margin: 10px 0;
 *   font-size: 14px;
 *   text-align: left;
 * }
 * 
 * .alpine-table th {
 *   background-color: #f5f5f5;
 *   color: #333;
 *   font-weight: bold;
 *   padding: 12px 8px;
 *   border: 1px solid #e0e0e0;
 *   cursor: pointer;
 * }
 * 
 * .alpine-table th:hover {
 *   background-color: #e8e8e8;
 * }
 * 
 * .alpine-table td {
 *   padding: 10px 8px;
 *   border: 1px solid #e0e0e0;
 * }
 * 
 * .alpine-table tr:nth-child(even) {
 *   background-color: #fafafa;
 * }
 * 
 * .alpine-table tr:hover {
 *   background-color: #f0f0f0;
 * }
 * 
 * .alpine-table .sort-asc, .alpine-table .sort-desc {
 *   margin-left: 5px;
 *   font-size: 12px;
 *   color: #e64340;
 * }
 * 
 * .alpine-table-pagination {
 *   display: flex;
 *   align-items: center;
 *   justify-content: center;
 *   margin: 10px 0;
 *   gap: 10px;
 * }
 * 
 * .alpine-table-pagination .pagination-btn {
 *   padding: 5px 10px;
 *   border: 1px solid #e0e0e0;
 *   background-color: #fff;
 *   color: #333;
 *   cursor: pointer;
 *   border-radius: 3px;
 * }
 * 
 * .alpine-table-pagination .pagination-btn:disabled {
 *   background-color: #f5f5f5;
 *   color: #999;
 *   cursor: not-allowed;
 * }
 * 
 * .alpine-table-pagination .pagination-select {
 *   padding: 5px;
 *   border: 1px solid #e0e0e0;
 *   border-radius: 3px;
 * }
 * ```
 */

// 提前定义并暴露table函数到全局作用域
window.table = function table(config = {}) {
  // 辅助函数：从JSON脚本标签读取数据
  function getDataFromSrc(src) {
    if (!src) return [];
    
    // 支持选择器
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
    
    // 支持全局变量路径
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

  // 处理数据来源
  let data = config.data || [];
  if (config.dataSrc) {
    data = getDataFromSrc(config.dataSrc);
  }
  
  // 处理列配置来源
  let cols = config.cols || [];
  if (config.colsSrc) {
    cols = getDataFromSrc(config.colsSrc);
  }
  
  // 如果没有提供列配置，则根据数据自动推断列定义
  if ((!config.cols || config.cols.length === 0) && 
      (!config.colsSrc || cols.length === 0) && 
      data.length > 0) {
    // 获取第一条数据的所有键作为列
    const firstItem = data[0];
    cols = Object.keys(firstItem).map(key => ({
      field: key,
      title: key
    }));
  }
    
    return {
      // 默认配置
      id: config.id || 'table-' + Date.now(),
      data: data,
      cols: cols,
      url: config.url || null,
      sortRules: [],
      page: {
        curr: 1,
        limit: config.page?.limit || 10,
        limits: config.page?.limits || [10, 20, 50],
        totalPage: 1,
        count: 0
      },
      skin: config.skin || 'line',
      even: config.even || false,
      loading: false,
      // 默认数据处理函数
      parseData: config.parseData || function(res) {
        return Array.isArray(res) ? res : (res.data || []);
      },

      // 初始化
      init() {
        this.updatePageInfo();
        // 如果配置了URL，则加载数据
        if (this.url) {
          this.loadData();
        }
        
        // 添加延迟检测机制，确保自定义表格有足够时间渲染
        // 第一次尝试
        setTimeout(() => {
          this.renderTable();
          this.renderPagination();
        }, 0);
        
        // 第二次尝试，确保自定义表格已经渲染完成
        setTimeout(() => {
          this.renderTable();
          this.renderPagination();
        }, 100);
      },

      // 通过AJAX加载数据
      async loadData() {
        if (!this.url) return;
        
        this.loading = true;
        try {
          const response = await fetch(this.url);
          if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
              }
              const rawData = await response.json();
              
              // 使用自定义数据处理函数处理数据
              this.data = this.parseData(rawData);
              
              // 更新分页信息
              this.updatePageInfo();
              
              // 移除直接调用，因为Alpine.js会自动响应数据变化
              // this.renderTable();
              // this.renderPagination();
            } catch (error) {
              console.error('加载数据失败:', error);
              alert('数据加载失败: ' + error.message);
            } finally {
              this.loading = false;
            }
          },

      // 更新分页信息
      updatePageInfo() {
        const data = this.data || [];
        this.page.totalPage = Math.ceil(data.length / this.page.limit) || 1;
        this.page.count = data.length;
        
        // 确保当前页不超过总页数
        if (this.page.curr > this.page.totalPage) {
          this.page.curr = this.page.totalPage;
        }
        
        // 确保当前页不小于1
        if (this.page.curr < 1) {
          this.page.curr = 1;
        }
      },

      // 获取当前页数据
      getPageData() {
        let result = this.data || [];
        
        // 如果有排序规则，则进行排序
        if (this.sortRules.length > 0) {
          // 创建数据副本以避免修改原始数据
          result = [...result];

          // 按照排序规则优先级进行排序
          result.sort((a, b) => {
            // 遍历所有排序规则
            for (let i = 0; i < this.sortRules.length; i++) {
              const rule = this.sortRules[i];
              const field = rule.field;
              const type = rule.type;

              // 获取要比较的值
              let aValue = a[field];
              let bValue = b[field];

              // 处理 null 或 undefined 值
              if (aValue == null && bValue == null) {
                continue; // 如果都为空，比较下一个规则
              }

              if (aValue == null) {
                return type === 'asc' ? -1 : 1;
              }

              if (bValue == null) {
                return type === 'asc' ? 1 : -1;
              }

              // 尝试转换为数字进行比较
              const aNum = Number(aValue);
              const bNum = Number(bValue);

              if (!isNaN(aNum) && !isNaN(bNum)) {
                aValue = aNum;
                bValue = bNum;
              }

              // 执行比较
              let comparison = 0;
              if (aValue < bValue) {
                comparison = -1;
              } else if (aValue > bValue) {
                comparison = 1;
              }

              // 根据排序方向调整结果
              if (comparison !== 0) {
                return type === 'asc' ? comparison : -comparison;
              }
            }

            // 所有规则都相等，保持原有顺序
            return 0;
          });
        }

        // 应用分页
        const start = (this.page.curr - 1) * this.page.limit;
        const end = start + this.page.limit;
        return result.slice(start, end);
      },
      
      // 检查是否需要分页（数据量超过每页限制才需要分页）
      needsPagination() {
        return this.data && this.data.length > this.page.limit;
      },
      
      // 渲染表格
      renderTable() {
        try {
          // 查找组件根元素（简化逻辑，优先使用ID选择器）
          const rootElement = this.$el || document.getElementById(this.id);
          if (!rootElement) return;
          
          // 检查是否存在任何表格元素（无论是否为内置或自定义）
          const anyTable = rootElement.querySelector('table');
          if (anyTable) return; // 如果已经存在表格元素，则不自动渲染
          
          // 查找是否已存在内置表格容器
          const existingTableContainer = rootElement.querySelector('.alpine-table-container');
          if (existingTableContainer) return; // 如果已存在内置表格容器，则不重复创建
          
          // 创建表格HTML
          const tableHTML = `
            <div class="alpine-table-container">
              <table class="alpine-table">
                <thead>
                  <tr>
                    ${this.cols.map(col => `
                      <th @click="sort('${col.field}', $event)">
                        <span x-text="getColumnLabel('${col.field}')"></span>
                        <span x-show="getSortDirection('${col.field}') === 'asc'" class="sort-asc">↑</span>
                        <span x-show="getSortDirection('${col.field}') === 'desc'" class="sort-desc">↓</span>
                      </th>
                    `).join('')}
                  </tr>
                </thead>
                <tbody>
                  <template x-for="(row, index) in getPageData()" :key="index + '-' + (row.id || JSON.stringify(row))">
                    <tr>
                      ${this.cols.map(col => `<td x-text="row['${col.field}']"></td>`).join('')}
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          `;
          
          // 将表格添加到根元素开头
          rootElement.insertAdjacentHTML('afterbegin', tableHTML);
          
          // 如果使用 Alpine 3.x，需要重新处理新添加的元素
          if (window.Alpine && typeof window.Alpine.initTree === 'function') {
            const newTable = rootElement.querySelector('.alpine-table-container');
            if (newTable) {
              window.Alpine.initTree(newTable);
            }
          }
        } catch (error) {
          console.error('Error in renderTable:', error);
        }
      },
      
      // 渲染分页控件
      renderPagination() {
        try {
          // 查找组件根元素
          const rootElement = this.$el || document.getElementById(this.id);
          if (!rootElement) return;
          
          // 检查是否已存在内置分页控件
          const existingPagination = rootElement.querySelector('.alpine-table-pagination');
          if (existingPagination) {
            // 如果已存在且不需要分页，则移除
            if (!this.needsPagination()) {
              existingPagination.remove();
            }
            return;
          }
          
          // 简化检测：只检查是否存在自定义分页容器或任何包含分页相关内容的元素
          let hasCustomPagination = false;
          
          // 检查1：是否存在分页容器
          if (rootElement.querySelector('.pagination-container')) {
            hasCustomPagination = true;
          }
          
          // 检查2：是否存在包含page.curr或page.limit的元素
          const allElements = rootElement.querySelectorAll('[x-text], [x-model]');
          for (let i = 0; i < allElements.length; i++) {
            const element = allElements[i];
            const xText = element.getAttribute('x-text');
            const xModel = element.getAttribute('x-model');
            if ((xText && (xText.includes('page.curr') || xText.includes('page.totalPage'))) ||
                (xModel && xModel.includes('page.limit'))) {
              hasCustomPagination = true;
              break;
            }
          }
          
          // 如果有自定义分页元素，则不自动渲染
          if (hasCustomPagination) {
            return;
          }
          
          // 如果需要分页且没有自定义分页结构，则自动创建
          if (this.needsPagination()) {
            const paginationHTML = `
              <div class="alpine-table-pagination">
                <button @click="prevPage()" :disabled="page.curr === 1" class="pagination-btn pagination-prev">
                  上一页
                </button>
                <span class="pagination-info" x-text="'第 ' + page.curr + ' 页 / 共 ' + page.totalPage + ' 页'"></span>
                <button @click="nextPage()" :disabled="page.curr === page.totalPage" class="pagination-btn pagination-next">
                  下一页
                </button>
                <select x-model="page.limit" @change="changeLimit()" class="pagination-select">
                  <template x-for="limit in page.limits" :key="limit">
                    <option :value="limit" x-text="limit + ' 条/页'"></option>
                  </template>
                </select>
              </div>
            `;
            
            // 将分页控件添加到根元素末尾
            rootElement.insertAdjacentHTML('beforeend', paginationHTML);
            
            // 如果使用 Alpine 3.x，需要重新处理新添加的元素
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
      },

      // 排序方法
      sort(field, event) {
        // 检查是否按住 Ctrl 键以支持多列排序
        const isCtrlPressed = event.ctrlKey;

        // 获取当前列的排序状态
        const currentDirection = this.getSortDirection(field);

        // 确定下一步的排序状态：无排序 -> 升序 -> 降序 -> 无排序
        let nextDirection = null;
        if (!currentDirection) {
          nextDirection = 'asc';
        } else if (currentDirection === 'asc') {
          nextDirection = 'desc';
        }

        // 如果是多列排序模式（按住Ctrl键）或当前列还没有排序规则
        if (isCtrlPressed || this.sortRules.length === 0) {
          // 如果有下一步排序方向，则更新或添加排序规则
          if (nextDirection) {
            // 检查是否已经存在该列的排序规则
            const existingIndex = this.sortRules.findIndex(rule => rule.field === field);

            if (existingIndex >= 0) {
              // 更新现有规则
              this.sortRules[existingIndex].type = nextDirection;
            } else {
              // 添加新规则
              this.sortRules.push({
                field: field,
                type: nextDirection
              });
            }
          } else {
            // 移除排序规则（从有排序状态切换到无排序状态）
            const index = this.sortRules.findIndex(rule => rule.field === field);
            if (index >= 0) {
              this.sortRules.splice(index, 1);
            }
          }
        } else {
          // 单列排序模式，清除所有其他排序规则
          this.sortRules = [];

          // 如果有下一步排序方向，则设置新的排序规则
          if (nextDirection) {
            this.sortRules.push({
              field: field,
              type: nextDirection
            });
          }
        }

        // 更新分页信息
        this.updatePageInfo();
      },

      // 获取指定列的排序方向
      getSortDirection(field) {
        const rule = this.sortRules.find(rule => rule.field === field);
        return rule ? rule.type : null;
      },

      // 获取指定列的排序优先级（1表示最高优先级）
      getSortPriority(field) {
        const index = this.sortRules.findIndex(rule => rule.field === field);
        return index >= 0 ? index + 1 : 0;
      },

      // 获取列标签
      getColumnLabel(field) {
        const column = this.cols.find(col => col.field === field);
        return column ? column.title : field;
      },

      // 移除指定的排序规则
      removeSortRule(index) {
        this.sortRules.splice(index, 1);
        this.updatePageInfo();
      },

      // 清除所有排序规则
      clearSort() {
        this.sortRules = [];
        this.updatePageInfo();
      },

      // 上一页
      prevPage() {
        if (this.page.curr > 1) {
          this.page.curr--;
          this.updatePageInfo();
        }
      },

      // 下一页
      nextPage() {
        if (this.page.curr < this.page.totalPage) {
          this.page.curr++;
          this.updatePageInfo();
        }
      },

      // 改变每页显示条数
      changeLimit() {
        this.page.curr = 1; // 重置到第一页
        this.updatePageInfo();
      },

      // 添加随机数据
      addRandomData() {
        // 根据不同的表格添加不同类型的数据
        if (this.id && this.id.includes('employee')) {
          const newData = {
            id: this.data.length + 1,
            name: '员工' + (this.data.length + 1),
            age: Math.floor(Math.random() * 30 + 20)
          };
          this.data = [...this.data, newData];
        } else if (this.id && this.id.includes('product')) {
          const categories = ['电子产品', '家具', '办公用品', '服装', '食品'];
          const newData = {
            id: this.data.length + 100,
            name: '产品' + (this.data.length + 1),
            price: Math.floor(Math.random() * 1000 + 50),
            category: categories[Math.floor(Math.random() * categories.length)]
          };
          this.data = [...this.data, newData];
        } else {
          // 默认数据结构
          const newData = {
            id: this.data.length + 1,
            name: '项目' + (this.data.length + 1)
          };
          this.data = [...this.data, newData];
        }
        this.updatePageInfo();
        this.renderTable();
        this.renderPagination();
      },

      // 重载数据
      reload(options) {
        if (options && options.data) {
          this.data = options.data;
          this.url = null; // 清除URL配置
        }
        if (options && options.cols) {
          this.cols = options.cols;
        }
        if (options && options.url) {
          this.url = options.url;
          this.loadData(); // 加载新URL的数据
          return;
        }
        // 重置分页
        this.page.curr = 1;
        // 强制更新
        this.sortRules = [...this.sortRules];
        this.updatePageInfo();
        this.renderTable();
        this.renderPagination();
      }
    };
}

// 确保在Alpine.js可用时注册组件
if (window.Alpine) {
  window.Alpine.data('table', window.table);
}

// 同时监听alpine:init事件以兼容不同版本的Alpine.js
document.addEventListener('alpine:init', () => {
  if (window.Alpine) {
    window.Alpine.data('table', window.table);
  }
});

// 返回table函数以支持AMD/CommonJS模块系统
if (typeof define === 'function' && define.amd) {
  // AMD
  define([], function () {
    return window.table;
  });
} else if (typeof module === 'object' && module.exports) {
  // CommonJS
  module.exports = window.table;
}
