// Alpine.js 表格组件扩展 - 兼容全局作用域
(function () {
  'use strict';

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
        return data;
      } catch (e) {
        console.error('Failed to get data from path', src, e);
        return [];
      }
    }
    
    return [];
  }

  // 定义表格组件工厂函数
  window.table = function table(config = {}) {
    // 处理数据来源
    let data = config.data || [];
    if (config.dataSrc) {
      data = getDataFromSrc(config.dataSrc);
    }
    
    return {
      // 默认配置
      id: config.id || 'table-' + Date.now(),
      data: data,
      cols: config.cols || [],
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
      }
    };
  };
});

// 同时支持 Alpine.js 3.x 的数据组件注册
document.addEventListener('alpine:init', () => {
  // 检查 Alpine 是否存在
  if (window.Alpine) {
    // 注册为 Alpine.js 数据组件，确保使用全局的 table 函数
    window.Alpine.data('table', window.table);
  }
});