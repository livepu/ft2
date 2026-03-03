/**
 * Notebook JS - Alpine.js 版本的 Notebook 应用逻辑
 * 从 notebook原版.html 分离出来的 JavaScript 算法
 */

// Toast 提示函数
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) {
        console.warn('Toast container not found');
        return;
    }
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    // 触发显示动画
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });
    
    // 自动移除
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (container.contains(toast)) {
                container.removeChild(toast);
            }
        }, 300);
    }, duration);
}

// Notebook 应用主函数
function notebookApp() {
    const dataElement = document.getElementById('notebook-data');
    const config = dataElement ? JSON.parse(dataElement.textContent) : { title: '', createdAt: '', cells: [] };
    
    return {
        title: config.title,
        createdAt: config.createdAt,
        cells: [],
        tocItems: [],
        selectedItems: new Set(),
        chartColors: ['#e74c3c', '#f39c12', '#af7ac5', '#5499c7', '#f4d03f', '#82e0aa', '#d35400', '#9b59b6', '#76d7c4'],
        
        init() {
            this.cells = config.cells;
            this.buildToc();
            
            this.$nextTick(() => {
                this.renderAllComponents();
            });
        },
        
        showToast(message, type, duration) {
            showToast(message, type, duration);
        },
        
        // ========== 选择相关方法 ==========
        toggleItemSelection(index) {
            if (this.selectedItems.has(index)) {
                this.selectedItems.delete(index);
            } else {
                this.selectedItems.add(index);
            }
            // 触发响应式更新
            this.selectedItems = new Set(this.selectedItems);
        },
        
        toggleSelectAll(checked) {
            if (checked) {
                this.tocItems.forEach((_, index) => this.selectedItems.add(index));
            } else {
                this.selectedItems.clear();
            }
            this.selectedItems = new Set(this.selectedItems);
        },
        
        clearSelection() {
            this.selectedItems.clear();
            this.selectedItems = new Set(this.selectedItems);
        },
        
        isAllSelected() {
            return this.tocItems.length > 0 && this.selectedItems.size === this.tocItems.length;
        },
        
        isSelected(cellIndex) {
            // cellIndex: -1 表示 header, >=0 表示 cells 的索引
            const tocIndex = this.tocItems.findIndex(item => item.index === cellIndex);
            if (tocIndex === -1) return false;
            return this.selectedItems.has(tocIndex);
        },
        
        // ========== 截图功能 ==========
        async captureScreenshot() {
            if (this.selectedItems.size === 0) return;

            const screenshotArea = document.getElementById('screenshot-area');
            if (!screenshotArea) {
                showToast('未找到截图区域', 'error');
                return;
            }

            try {
                screenshotArea.classList.add('screenshot-mode');
                await new Promise(resolve => setTimeout(resolve, 100));

                const result = await snapdom(screenshotArea, {
                    backgroundColor: '#f5f5f5',
                    scale: 1,
                    cache: 'auto'
                });

                screenshotArea.classList.remove('screenshot-mode');

                const blob = await result.toBlob({ type: 'png' });

                try {
                    // 确保页面有焦点后再写入剪贴板
                    window.focus();
                    await navigator.clipboard.write([
                        new ClipboardItem({ 'image/png': blob })
                    ]);
                    showToast(`截图已复制到剪贴板 (${this.selectedItems.size}个区域)`);
                } catch (err) {
                    console.error('复制到剪贴板失败:', err);
                    // 降级方案：自动下载图片
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.download = `截图_${new Date().toLocaleString().replace(/[/:]/g, '-')}.png`;
                    link.href = url;
                    link.click();
                    URL.revokeObjectURL(url);
                    showToast('已自动下载截图（剪贴板需要页面焦点）');
                }
            } catch (error) {
                screenshotArea.classList.remove('screenshot-mode');
                console.error('截图失败:', error);
                showToast('截图失败: ' + error.message, 'error');
            }
        },
        
        // ========== 目录相关方法 ==========
        buildToc() {
            const items = [];
            
            // 添加封面标题
            if (this.title) {
                items.push({
                    title: this.title,
                    type: 'header',
                    index: -1
                });
            }
            
            // 添加所有 section（使用 forEach 的 index 而不是 indexOf）
            this.cells.forEach((cell, cellIndex) => {
                if (cell.type === 'section' && cell.title) {
                    items.push({
                        title: cell.title,
                        type: 'section',
                        index: cellIndex
                    });
                }
            });
            
            this.tocItems = items;
        },
        
        scrollToSection(index) {
            const item = this.tocItems[index];
            if (!item) return;
            
            if (item.type === 'header') {
                // 跳转到页面顶部
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                const section = document.querySelector(`#section-${item.index}`);
                if (section) {
                    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        },
        
        // ========== 渲染组件方法 ==========
        renderAllComponents() {
            this.cells.forEach((cell, index) => {
                if (cell.type === 'chart') {
                    this.renderChart('chart-' + index, cell);
                } else if (cell.type === 'heatmap') {
                    this.renderHeatmap('heatmap-' + index, cell);
                } else if (cell.type === 'pyecharts') {
                    this.renderPyecharts('pyecharts-' + index, cell);
                } else if (cell.type === 'section') {
                    this.renderSectionComponents(cell, index);
                }
            });
        },
        
        renderSectionComponents(section, parentIndex, depth = 1) {
            if (!section.content || !Array.isArray(section.content)) return;
            
            section.content.forEach((subCell, subIndex) => {
                const idPrefix = depth === 1 
                    ? parentIndex + '-' + subIndex
                    : parentIndex + '-' + subIndex;
                
                if (subCell.type === 'chart') {
                    this.renderChart('chart-' + idPrefix, subCell);
                } else if (subCell.type === 'heatmap') {
                    this.renderHeatmap('heatmap-' + idPrefix, subCell);
                } else if (subCell.type === 'pyecharts') {
                    this.renderPyecharts('pyecharts-' + idPrefix, subCell);
                } else if (subCell.type === 'section') {
                    if (subCell.content && Array.isArray(subCell.content)) {
                        subCell.content.forEach((deepCell, deepIndex) => {
                            const deepId = idPrefix + '-' + deepIndex;
                            if (deepCell.type === 'chart') {
                                this.renderChart('chart-' + deepId, deepCell);
                            } else if (deepCell.type === 'heatmap') {
                                this.renderHeatmap('heatmap-' + deepId, deepCell);
                            } else if (deepCell.type === 'pyecharts') {
                                this.renderPyecharts('pyecharts-' + deepId, deepCell);
                            } else if (deepCell.type === 'section') {
                                if (deepCell.content && Array.isArray(deepCell.content)) {
                                    deepCell.content.forEach((lv3Cell, lv3Index) => {
                                        const lv3Id = deepId + '-' + lv3Index;
                                        if (lv3Cell.type === 'chart') {
                                            this.renderChart('chart-' + lv3Id, lv3Cell);
                                        } else if (lv3Cell.type === 'heatmap') {
                                            this.renderHeatmap('heatmap-' + lv3Id, lv3Cell);
                                        } else if (lv3Cell.type === 'pyecharts') {
                                            this.renderPyecharts('pyecharts-' + lv3Id, lv3Cell);
                                        }
                                    });
                                }
                            }
                        });
                    }
                }
            });
        },
        
        // ========== 表格相关方法 ==========
        getTableCols(cell) {
            if (cell.options && cell.options.columns) {
                return cell.options.columns.map(col => ({field: col, title: col}));
            }
            if (cell.content && cell.content.length > 0) {
                return Object.keys(cell.content[0]).map(col => ({field: col, title: col}));
            }
            return [];
        },
        
        getTableOptions(cell) {
            const opts = cell.options || {};
            const result = {};
            
            if (opts.freeze) {
                result.freeze = opts.freeze;
            }
            
            if (opts.page) {
                result.page = opts.page;
            }
            
            return result;
        },
        
        // ========== 图表渲染方法 ==========
        renderChart(containerId, cell) {
            const container = document.getElementById(containerId);
            if (!container) return;
            
            const chart = echarts.init(container);
            const chartType = cell.content.chart_type;
            const data = cell.content.data;
            const colors = this.chartColors;
            
            let option = {};
            
            if (chartType === 'line' || chartType === 'area') {
                option = {
                    color: colors,
                    tooltip: { trigger: 'axis' },
                    legend: { data: data.series.map(s => s.name), top: 5 },
                    grid: { left: 8, right: 8, bottom: 5, top: 28, containLabel: true },
                    xAxis: { type: 'category', boundaryGap: false, data: data.dates },
                    yAxis: { 
                        type: 'value',
                        scale: true,
                        boundaryGap: ['10%', '10%']
                    },
                    series: data.series.map((s, i) => ({
                        name: s.name,
                        type: 'line',
                        data: s.data,
                        smooth: true,
                        areaStyle: chartType === 'area' ? { 
                            color: {
                                type: 'linear',
                                x: 0, y: 0, x2: 0, y2: 1,
                                colorStops: [
                                    { offset: 0, color: colors[i] + '60' },
                                    { offset: 1, color: colors[i] + '10' }
                                ]
                            }
                        } : undefined,
                        itemStyle: { color: colors[i] }
                    }))
                };
            } else if (chartType === 'bar') {
                option = {
                    tooltip: { trigger: 'axis' },
                    legend: { 
                        data: data.series.map(s => ({
                            name: s.name,
                            icon: 'rect'
                        })),
                        top: 5,
                        itemStyle: {
                            color: '#e74c3c'
                        }
                    },
                    grid: { left: 8, right: 8, bottom: 5, top: 28, containLabel: true },
                    xAxis: { type: 'category', data: data.categories },
                    yAxis: { 
                        type: 'value',
                        scale: true,
                        boundaryGap: ['10%', '10%']
                    },
                    series: data.series.map((s, i) => ({
                        name: s.name,
                        type: 'bar',
                        data: s.data,
                        itemStyle: { 
                            color: function(params) {
                                const value = params.value;
                                if (value >= 0) {
                                    return '#e74c3c';
                                } else {
                                    return '#5499c7';
                                }
                            },
                            borderRadius: [4, 4, 0, 0]
                        }
                    }))
                };
            } else if (chartType === 'pie') {
                option = {
                    color: colors,
                    tooltip: { 
                        trigger: 'item',
                        formatter: '{b}: {c} ({d}%)'
                    },
                    legend: { 
                        top: 10,
                        left: 'center',
                        orient: 'horizontal'
                    },
                    series: [{
                        type: 'pie',
                        radius: ['40%', '70%'],
                        center: ['50%', '55%'],
                        data: data,
                        label: { 
                            show: true,
                            formatter: '{b}\n{c} ({d}%)'
                        },
                        labelLine: {
                            show: true,
                            length: 15,
                            length2: 10
                        },
                        emphasis: {
                            label: {
                                show: true,
                                fontSize: 14,
                                fontWeight: 'bold'
                            }
                        }
                    }]
                };
            }
            
            option = { ...option, ...cell.options };
            chart.setOption(option);
            
            window.addEventListener('resize', () => chart.resize());
        },
        
        renderHeatmap(containerId, cell) {
            const container = document.getElementById(containerId);
            if (!container) return;
            
            const chart = echarts.init(container);
            const data = cell.content;
            
            const years = Object.keys(data).sort();
            const months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
            
            const heatmapData = [];
            let minValue = Infinity;
            let maxValue = -Infinity;
            
            years.forEach((year, yIndex) => {
                months.forEach((month, mIndex) => {
                    const value = data[year][month];
                    if (value !== undefined) {
                        const percentValue = parseFloat((value * 100).toFixed(2));
                        heatmapData.push([mIndex, yIndex, percentValue]);
                        minValue = Math.min(minValue, percentValue);
                        maxValue = Math.max(maxValue, percentValue);
                    }
                });
            });
            
            // 根据数据范围动态设置 visualMap 范围
            const range = Math.max(Math.abs(minValue), Math.abs(maxValue));
            const visualMax = Math.ceil(range / 5) * 5;  // 向上取整到5的倍数
            
            const option = {
                tooltip: {
                    formatter: function(params) {
                        return years[params.value[1]] + '-' + months[params.value[0]] + ': ' + params.value[2] + '%';
                    }
                },
                grid: { left: '10%', right: '18%', top: '10%', bottom: '12%' },
                xAxis: { type: 'category', data: months, splitArea: { show: true } },
                yAxis: { type: 'category', data: years, splitArea: { show: true } },
                visualMap: {
                    min: -visualMax,
                    max: visualMax,
                    calculable: true,
                    orient: 'vertical',
                    right: '2%',
                    top: 'center',
                    inRange: {
                        color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8',
                                '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026']
                    }
                },
                series: [{
                    type: 'heatmap',
                    data: heatmapData,
                    label: { show: true, formatter: '{@[2]}%' },
                    emphasis: { itemStyle: { shadowBlur: 10 } }
                }]
            };
            
            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        },
        
        renderPyecharts(containerId, cell) {
            const container = document.getElementById(containerId);
            if (!container) return;
            
            const chart = echarts.init(container);
            const option = JSON.parse(cell.content.option);
            chart.setOption(option);
            
            window.addEventListener('resize', () => chart.resize());
        },
        
        // ========== 辅助方法 ==========
        getMetricClass(value) {
            if (typeof value === 'string' && value.includes('%')) {
                const num = parseFloat(value);
                if (num > 0) return 'positive';
                if (num < 0) return 'negative';
            }
            return '';
        },
        
        renderMarkdown(text) {
            if (!text) return '';
            return text
                .replace(/^### (.*$)/gm, '<h3>$1</h3>')
                .replace(/^## (.*$)/gm, '<h2>$1</h2>')
                .replace(/^# (.*$)/gm, '<h1>$1</h1>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .trim()
                .replace(/\n+/g, '\n')
                .replace(/\n/g, '<br>');
        }
    };
}

// 导出函数（如果支持模块系统）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { notebookApp, showToast };
}
