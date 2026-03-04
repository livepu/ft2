/**
 * Notebook Vue3 - Vue 3 组合式 API 版本的 Notebook 应用逻辑
 * 从 notebook.html 分离出来的 JavaScript
 */

const { createApp, ref, computed, onMounted, onUnmounted, nextTick } = Vue;

// ========== Cell 渲染组件（组合式 API）==========
const CellRenderer = {
    name: 'CellRenderer',
    components: {
        // VueTable 会从父组件传递，如果可用
        VueTable: typeof window !== 'undefined' && window.VueTable ? window.VueTable : null
    },
    props: {
        cell: { type: Object, required: true },
        cellId: { type: [String, Number], required: true },
        level: { type: Number, default: 0 }
    },
    setup(props) {
        const chartRef = ref(null);
        let chartInstance = null;
        
        // 热力图放大倍数控制
        const heatmapMultiplier = ref(1);
        const heatmapRawData = ref(null);
        
        // 饼图显示控制
        const pieShowValue = ref(true);
        const pieShowPercent = ref(true);
        const pieRawData = ref(null);

        // 渲染 Markdown
        const renderMarkdown = (content) => {
            if (!content) return '';
            return content
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/`(.*?)`/g, '<code>$1</code>')
                .replace(/\n/g, '<br>');
        };

        // 获取指标样式类
        const getMetricClass = (value) => {
            if (typeof value !== 'string') return '';
            if (value.includes('%')) {
                const num = parseFloat(value);
                if (!isNaN(num)) {
                    return num >= 0 ? 'positive' : 'negative';
                }
            }
            return '';
        };

        // 获取表格列配置
        const getTableCols = (cell) => {
            if (cell.options?.columns) {
                return cell.options.columns.map(col => ({
                    field: col,
                    title: col
                }));
            }
            if (cell.content && cell.content.length > 0) {
                return Object.keys(cell.content[0]).map(key => ({
                    field: key,
                    title: key
                }));
            }
            return [];
        };

        // 获取表格选项
        const getTableOptions = (cell) => {
            const opts = {};
            if (cell.options?.freeze) opts.freeze = cell.options.freeze;
            // 默认开启分页：数据超过10条时自动分页，也可通过 options.pagination 自定义
            if (cell.options?.pagination !== false) {
                const dataLength = cell.content?.length || 0;
                if (dataLength > 10 || cell.options?.pagination) {
                    opts.pagination = cell.options?.pagination || {
                        pageSize: 10,
                        pageSizeOptions: [10, 20, 50, 100]
                    };
                }
            }
            return opts;
        };

        // 初始化图表
        const initChart = () => {
            console.log('initChart called for cell type:', props.cell.type);
            console.log('chartRef.value:', chartRef.value);
            console.log('cell.content:', props.cell.content);
            
            if (!chartRef.value || !props.cell.content) {
                console.warn('Chart init skipped: no chartRef or content');
                return;
            }

            const cell = props.cell;
            const content = cell.content;

            if (cell.type === 'chart' || cell.type === 'heatmap') {
                const chartType = content.chart_type || content.type;
                console.log('Initializing chart with type:', chartType, 'data:', content.data);
                chartInstance = echarts.init(chartRef.value);
                
                // 热力图特殊处理：保存原始数据，默认使用原始数据（×1）
                if (cell.type === 'heatmap') {
                    heatmapRawData.value = content.data || content;
                    // 默认选中原始数据（×1），不自动放大
                    heatmapMultiplier.value = 1;
                }
                
                // 饼图特殊处理：保存原始数据
                if (chartType === 'pie') {
                    pieRawData.value = content.data || content;
                }
                
                const option = buildChartOption(cell.type, chartType, content.data || content, cell.options, heatmapMultiplier.value, pieShowValue.value, pieShowPercent.value);
                chartInstance.setOption(option);
            } else if (cell.type === 'pyecharts') {
                chartInstance = echarts.init(chartRef.value);
                chartInstance.setOption(content);
            }
        };
        
        // 更新热力图（当放大倍数改变时）
        const updateHeatmap = () => {
            if (!chartInstance || !heatmapRawData.value) return;
            const option = buildChartOption('heatmap', 'heatmap', heatmapRawData.value, props.cell.options, heatmapMultiplier.value);
            chartInstance.setOption(option);
        };
        
        // 更新饼图（当显示选项改变时）
        const updatePie = () => {
            if (!chartInstance || !pieRawData.value) return;
            const option = buildChartOption('chart', 'pie', pieRawData.value, props.cell.options, 1, pieShowValue.value, pieShowPercent.value);
            chartInstance.setOption(option);
        };

        // 暖冷渐变系4 配色方案
        const chartColors = ['#e74c3c', '#f39c12', '#af7ac5', '#5499c7', '#f4d03f', '#82e0aa', '#d35400', '#9b59b6', '#76d7c4'];

        // 构建图表配置
        const buildChartOption = (type, chartType, data, options = {}, multiplier = 1, showValue = true, showPercent = true) => {
            const baseOption = {
                tooltip: { trigger: 'axis' },
                grid: { left: 8, right: 8, bottom: 5, top: 28, containLabel: true }
            };

            if (type === 'chart') {
                const isLine = chartType === 'line';
                const isBar = chartType === 'bar';
                const isArea = chartType === 'area';
                const isPie = chartType === 'pie';

                // 饼图特殊处理
                if (isPie) {
                    // 构建 label 格式
                    let labelFormatter = '{b}';
                    if (showValue && showPercent) {
                        labelFormatter = '{b}\n{c} ({d}%)';
                    } else if (showValue) {
                        labelFormatter = '{b}\n{c}';
                    } else if (showPercent) {
                        labelFormatter = '{b}\n({d}%)';
                    }
                    
                    return {
                        color: chartColors,
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
                            data: data,
                            radius: ['40%', '70%'],
                            center: ['45%', '55%'],
                            label: { 
                                show: true, 
                                formatter: labelFormatter 
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

                // 柱状图特殊处理：正负颜色区分
                if (isBar) {
                    return {
                        tooltip: { trigger: 'axis' },
                        legend: { 
                            data: (data.series || []).map(s => ({
                                name: s.name,
                                icon: 'rect'
                            })),
                            top: 5,
                            itemStyle: {
                                color: '#e74c3c'
                            }
                        },
                        grid: { left: 8, right: 8, bottom: 5, top: 28, containLabel: true },
                        xAxis: {
                            type: 'category',
                            data: data.xAxis || data.dates || data.categories || []
                        },
                        yAxis: { 
                            type: 'value',
                            scale: true,
                            boundaryGap: ['10%', '10%']
                        },
                        series: (data.series || []).map(s => ({
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
                }

                // 折线图和面积图
                return {
                    color: chartColors,
                    ...baseOption,
                    legend: { 
                        data: (data.series || []).map(s => s.name), 
                        top: 5 
                    },
                    xAxis: {
                        type: 'category',
                        boundaryGap: false,
                        data: data.xAxis || data.dates || data.categories || []
                    },
                    yAxis: { 
                        type: 'value',
                        scale: true,
                        boundaryGap: ['10%', '10%']
                    },
                    series: (data.series || []).map((s, i) => ({
                        name: s.name,
                        type: isArea ? 'line' : chartType,
                        data: s.data,
                        smooth: true,
                        areaStyle: isArea ? { 
                            color: {
                                type: 'linear',
                                x: 0, y: 0, x2: 0, y2: 1,
                                colorStops: [
                                    { offset: 0, color: chartColors[i % chartColors.length] + '60' },
                                    { offset: 1, color: chartColors[i % chartColors.length] + '10' }
                                ]
                            }
                        } : undefined,
                        itemStyle: { color: chartColors[i % chartColors.length] }
                    }))
                };
            } else if (type === 'heatmap') {
                const years = Object.keys(data);
                const months = Object.keys(data[years[0]]);
                const heatmapData = [];
                let minValue = Infinity;
                let maxValue = -Infinity;
                
                years.forEach((year, yIndex) => {
                    months.forEach((month, mIndex) => {
                        const value = data[year][month];
                        if (value !== undefined) {
                            const numValue = parseFloat(value);
                            heatmapData.push([mIndex, yIndex, numValue]);
                            minValue = Math.min(minValue, numValue);
                            maxValue = Math.max(maxValue, numValue);
                        }
                    });
                });

                // 应用传入的放大倍数
                const displayData = heatmapData.map(d => [d[0], d[1], (d[2] * multiplier).toFixed(2)]);
                
                // 根据放大后的数据范围设置 visualMap（对称）
                const displayValues = displayData.map(d => parseFloat(d[2]));
                const displayMax = Math.max(...displayValues.map(Math.abs));
                const visualMax = Math.ceil(displayMax / 5) * 5 || 5;

                return {
                    tooltip: { 
                        formatter: function(params) {
                            return years[params.value[1]] + '-' + months[params.value[0]] + ': ' + params.value[2];
                        }
                    },
                    grid: { left: '10%', right: '18%', top: '10%', bottom: '12%' },
                    xAxis: { 
                        type: 'category', 
                        data: months, 
                        splitArea: { show: true } 
                    },
                    yAxis: { 
                        type: 'category', 
                        data: years, 
                        splitArea: { show: true } 
                    },
                    visualMap: {
                        min: -visualMax,
                        max: visualMax,
                        calculable: true,
                        orient: 'vertical',
                        right: '2%',
                        top: 'center',
                        text: [visualMax + ' (×' + multiplier + ')', -visualMax + ' (×' + multiplier + ')'],
                        inRange: {
                            color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8',
                                    '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026']
                        }
                    },
                    series: [{
                        name: '收益',
                        type: 'heatmap',
                        data: displayData,
                        label: { show: true, formatter: '{@[2]}' },
                        emphasis: { itemStyle: { shadowBlur: 10 } }
                    }]
                };
            }

            return baseOption;
        };

        onMounted(() => {
            if (['chart', 'heatmap', 'pyecharts'].includes(props.cell.type)) {
                nextTick(() => initChart());
                
                // 监听窗口大小变化，自动调整图表尺寸
                window.addEventListener('resize', handleResize);
            }
        });
        
        onUnmounted(() => {
            // 移除resize监听，避免内存泄漏
            window.removeEventListener('resize', handleResize);
            // 销毁图表实例
            if (chartInstance) {
                chartInstance.dispose();
                chartInstance = null;
            }
        });
        
        // 处理窗口resize
        const handleResize = () => {
            if (chartInstance) {
                chartInstance.resize();
            }
        };

        return {
            chartRef,
            heatmapMultiplier,
            updateHeatmap,
            pieShowValue,
            pieShowPercent,
            updatePie,
            renderMarkdown,
            getMetricClass,
            getTableCols,
            getTableOptions
        };
    },
    template: `
        <!-- Section - 直接渲染，不包裹 .cell -->
        <div v-if="cell.type === 'section'" 
             class="section"
             :class="{ 
                 'nested-section': level > 0,
                 'collapsible-section': cell.options?.collapsed !== undefined
             }"
             :id="'section-' + cellId">
            <div v-if="cell.title" 
                 class="section-title"
                 :class="{ 'collapsible-header': cell.options?.collapsed !== undefined }"
                 @click="cell.options?.collapsed !== undefined && (cell.options.collapsed = !cell.options.collapsed)">
                <span>{{ cell.title }}</span>
                <span v-if="cell.options?.collapsed !== undefined" class="collapse-icon">
                    {{ cell.options?.collapsed ? '▶' : '▼' }}
                </span>
            </div>
            <div class="section-content" v-show="cell.options?.collapsed !== true">
                <cell-renderer 
                    v-for="(subCell, idx) in cell.children" 
                    :key="idx"
                    :cell="subCell"
                    :cell-id="cellId + '-' + idx"
                    :level="level + 1">
                </cell-renderer>
            </div>
        </div>
        
        <!-- 其他类型 - 包裹在 .cell 中 -->
        <div v-else class="cell">
            <!-- 标题 -->
            <div v-if="cell.type === 'title'" class="cell-title">
                <h1 v-if="cell.options?.level === 1">{{ cell.content }}</h1>
                <h2 v-else-if="cell.options?.level === 2">{{ cell.content }}</h2>
                <h3 v-else>{{ cell.content }}</h3>
            </div>
            
            <!-- 文本 -->
            <div v-else-if="cell.type === 'text'" 
                 class="cell-text" 
                 :class="'text-' + (cell.options?.style || 'normal')">
                {{ cell.content }}
            </div>
            
            <!-- Markdown -->
            <div v-else-if="cell.type === 'markdown'" 
                 class="markdown-content" 
                 v-html="renderMarkdown(cell.content)">
            </div>
            
            <!-- 代码 -->
            <div v-else-if="cell.type === 'code'" class="code-block">
                <div class="code-header">{{ cell.content?.lang || 'Python' }}</div>
                <div class="code-input"><pre>{{ cell.content?.code }}</pre></div>
                <div v-if="cell.content?.output" class="code-output">{{ cell.content.output }}</div>
            </div>
            
            <!-- 表格 -->
            <div v-else-if="cell.type === 'table'" class="cell-table">
                <h3 v-if="cell.title">{{ cell.title }}</h3>
                <div v-if="!cell.content || cell.content.length === 0" class="table-empty">
                    暂无数据
                </div>
                <vue-table 
                    v-else
                    :id="'table-' + cellId"
                    :data-source="cell.content"
                    :columns="getTableCols(cell)"
                    v-bind="getTableOptions(cell)">
                </vue-table>
            </div>
            
            <!-- 指标 -->
            <div v-else-if="cell.type === 'metrics'" class="cell-metrics">
                <h3 v-if="cell.title">{{ cell.title }}</h3>
                <div class="metrics-grid" :style="{'--columns': cell.options?.columns || 4}">
                    <div v-for="metric in cell.content" 
                         :key="metric.name"
                         class="metric-card"
                         :class="getMetricClass(metric.value)">
                        <div class="metric-value">{{ metric.value }}</div>
                        <div class="metric-label">{{ metric.name }}</div>
                        <div v-if="metric.desc" class="metric-desc">{{ metric.desc }}</div>
                    </div>
                </div>
            </div>
            
            <!-- 饼图（带显示控制） -->
            <div v-else-if="cell.type === 'chart' && cell.content?.chart_type === 'pie'" 
                 class="cell-chart pie-with-control">
                <h3 v-if="cell.title">{{ cell.title }}</h3>
                <div class="pie-wrapper">
                    <div ref="chartRef" 
                         class="chart-container"
                         :style="{'--height': (cell.options?.height || 400) + 'px'}">
                    </div>
                    <div class="pie-control">
                        <div class="control-label">显示选项</div>
                        <div class="checkbox-group">
                            <label class="checkbox-item">
                                <input 
                                    type="checkbox" 
                                    v-model="pieShowValue"
                                    @change="updatePie">
                                <span>原始数据</span>
                            </label>
                            <label class="checkbox-item">
                                <input 
                                    type="checkbox" 
                                    v-model="pieShowPercent"
                                    @change="updatePie">
                                <span>百分比</span>
                            </label>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 其他图表 -->
            <div v-else-if="cell.type === 'chart' || cell.type === 'pyecharts'" 
                 class="cell-chart">
                <h3 v-if="cell.title">{{ cell.title }}</h3>
                <div ref="chartRef" 
                     class="chart-container"
                     :style="{'--height': (cell.options?.height || 400) + 'px'}">
                </div>
            </div>
            
            <!-- 热力图（带放大倍数控制） -->
            <div v-else-if="cell.type === 'heatmap'" 
                 class="cell-chart heatmap-with-control">
                <h3 v-if="cell.title">{{ cell.title }}</h3>
                <div class="heatmap-wrapper">
                    <div ref="chartRef" 
                         class="chart-container"
                         :style="{'--height': (cell.options?.height || 400) + 'px'}">
                    </div>
                    <div class="heatmap-control">
                        <div class="control-label">数据缩放</div>
                        <div class="current-multiplier">×{{ heatmapMultiplier }}</div>
                        <div class="multiplier-buttons">
                            <button 
                                v-for="m in [1000, 100, 10]" 
                                :key="m"
                                :class="{ active: heatmapMultiplier === m }"
                                @click="heatmapMultiplier = m; updateHeatmap()">
                                ×{{ m }}
                            </button>
                            <button 
                                :class="{ active: heatmapMultiplier === 1 }"
                                @click="heatmapMultiplier = 1; updateHeatmap()">
                                原始
                            </button>
                            <button 
                                v-for="m in [0.1, 0.01]" 
                                :key="m"
                                :class="{ active: heatmapMultiplier === m }"
                                @click="heatmapMultiplier = m; updateHeatmap()">
                                1/{{ m === 0.1 ? 10 : 100 }}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- HTML -->
            <div v-else-if="cell.type === 'html'" class="html-block">
                <div class="html-block-inner" v-html="cell.content"></div>
            </div>
            
            <!-- 分隔线 -->
            <div v-else-if="cell.type === 'divider'" class="cell-divider"></div>
            
            <!-- 可折叠（遗留类型，保持兼容） -->
            <div v-else-if="cell.type === 'collapsible'" class="cell-collapsible">
                <button class="collapse-toggle" @click="cell.options.collapsed = !cell.options.collapsed">
                    <span>{{ cell.title }}</span>
                    <span>{{ cell.options?.collapsed ? '▶' : '▼' }}</span>
                </button>
                <div v-show="!cell.options?.collapsed" class="collapse-content">
                    <cell-renderer 
                        v-for="(subCell, idx) in cell.children" 
                        :key="idx"
                        :cell="subCell"
                        :cell-id="cellId + '-' + idx"
                        :level="level + 1">
                    </cell-renderer>
                </div>
            </div>
        </div>
    `
};

// ========== 创建 Notebook 应用 ==========
function createNotebookApp() {
    // 从全局获取 VueTable 组件（由 vue3-table.js 暴露到 window）
    const VueTableComponent = typeof window !== 'undefined' ? window.VueTable : null;
    console.log('VueTableComponent:', VueTableComponent);
    
    return createApp({
        components: {
            CellRenderer,
            VueTable: VueTableComponent
        },

        setup() {
            // 从全局变量获取配置（由后端渲染时注入）
            const config = window.notebookConfig || {
                title: '未命名 Notebook',
                createdAt: new Date().toLocaleString(),
                children: []
            };

            const title = ref(config.title);
            const createdAt = ref(config.createdAt);
            // 兼容 cells 和 children 两种字段名
            const cells = ref(config.children || config.cells || []);
            const selectedIndices = ref(new Set());
            const isScreenshotMode = ref(false);
            
            // Toast 提示
            const toastMessage = ref('');
            const toastType = ref('info');
            let toastTimer = null;
            
            const showToast = (message, type = 'info', duration = 3000) => {
                toastMessage.value = message;
                toastType.value = type;
                if (toastTimer) clearTimeout(toastTimer);
                toastTimer = setTimeout(() => {
                    toastMessage.value = '';
                }, duration);
            };

            // 计算目录项
            const tocItems = computed(() => {
                const items = [];
                if (title.value) {
                    items.push({ title: title.value, type: 'header', index: -1 });
                }
                cells.value.forEach((cell, index) => {
                    if (cell.type === 'section' && cell.title) {
                        items.push({ title: cell.title, type: 'section', index });
                    }
                });
                return items;
            });

            // 选中数量
            const selectedCount = computed(() => selectedIndices.value.size);

            // 判断是否选中
            const isSelected = (index) => selectedIndices.value.has(index);

            // 切换选择
            const toggleSelection = (index) => {
                const newSet = new Set(selectedIndices.value);
                if (newSet.has(index)) {
                    newSet.delete(index);
                } else {
                    newSet.add(index);
                }
                selectedIndices.value = newSet;
            };

            // 全选
            const selectAll = () => {
                const allIndices = tocItems.value.map(item => item.index);
                selectedIndices.value = new Set(allIndices);
            };

            // 清空选择
            const clearSelection = () => {
                selectedIndices.value = new Set();
            };

            // 滚动到章节
            const scrollToSection = (index) => {
                if (index === -1) {
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                } else {
                    const el = document.getElementById('section-' + index);
                    if (el) el.scrollIntoView({ behavior: 'smooth' });
                }
            };

            // 截图功能 - 逐个元素截图后 Canvas 拼接（保证所见即所得）
            const captureScreenshot = async () => {
                if (selectedIndices.value.size === 0) return;

                const mainContainer = document.querySelector('.notebook-container');

                // 收集需要截图的元素
                const elementsToCapture = [];

                // 1. 头部（如果选中）
                if (selectedIndices.value.has(-1)) {
                    const header = mainContainer.querySelector('.notebook-header');
                    if (header) elementsToCapture.push(header);
                }

                // 2. 按原始顺序收集选中的 sections
                const sortedIndices = [...selectedIndices.value]
                    .filter(index => index !== -1)
                    .sort((a, b) => a - b);

                sortedIndices.forEach(index => {
                    const section = document.getElementById('section-' + index);
                    if (section) elementsToCapture.push(section);
                });

                try {
                    // 3. 等待表格组件渲染完成
                    // vue-table 是异步渲染，需要给予足够时间
                    await new Promise(resolve => setTimeout(resolve, 300));

                    // 4. 逐个截图
                    const imageBlobs = [];
                    for (const el of elementsToCapture) {
                        // 检查元素内是否有表格，如果有额外等待
                        const hasTable = el.querySelector('vue-table, .vue-table, table');
                        if (hasTable) {
                            await new Promise(resolve => setTimeout(resolve, 200));
                        }
                        
                        const result = await snapdom(el, {
                            scale: 2,
                            backgroundColor: '#f5f5f5',
                            cache: 'auto'
                        });
                        const blob = await result.toBlob({ type: 'png' });
                        imageBlobs.push(blob);
                    }

                    // 4. Canvas 拼接
                    const finalBlob = await stitchImages(imageBlobs);

                    // 5. 复制到剪贴板
                    try {
                        window.focus();
                        await navigator.clipboard.write([
                            new ClipboardItem({ 'image/png': finalBlob })
                        ]);
                        showToast(`已复制 ${selectedIndices.value.size} 个选中区域到剪贴板`, 'success');
                    } catch (clipboardErr) {
                        console.error('复制到剪贴板失败:', clipboardErr);
                        // 自动下载图片
                        showToast('复制到剪贴板失败，正在下载图片...', 'info');
                        const reader = new FileReader();
                        reader.onload = function(e) {
                            const link = document.createElement('a');
                            link.download = `${title.value || 'notebook'}-选中部分.png`;
                            link.href = e.target.result;
                            link.click();
                        };
                        reader.readAsDataURL(finalBlob);
                    }

                } catch (err) {
                    console.error('截图失败:', err);
                    showToast('截图失败: ' + err.message, 'error');
                }
            };

            // 图片拼接函数 - 将多个图片 blob 垂直拼接（保留间距、padding和背景）
            const stitchImages = async (imageBlobs) => {
                // 加载所有图片
                const images = await Promise.all(imageBlobs.map(blob => {
                    return new Promise((resolve, reject) => {
                        const img = new Image();
                        img.onload = () => resolve(img);
                        img.onerror = reject;
                        img.src = URL.createObjectURL(blob);
                    });
                }));

                // 配置间距和 padding（与原 CSS 一致）
                const MARGIN_TOP = 12;       // section margin-top
                const MARGIN_BOTTOM = 12;    // section margin-bottom
                const CONTAINER_PADDING = 20; // notebook-container padding

                // 计算总尺寸（包含间距和 container padding）
                const maxContentWidth = Math.max(...images.map(img => img.width));
                const maxWidth = maxContentWidth + CONTAINER_PADDING * 2; // 左右 padding
                const contentHeight = images.reduce((sum, img) => sum + img.height, 0);
                const spacingHeight = (images.length - 1) * (MARGIN_TOP + MARGIN_BOTTOM);
                const totalHeight = contentHeight + spacingHeight + CONTAINER_PADDING * 2; // 上下 padding

                // 创建 Canvas
                const canvas = document.createElement('canvas');
                canvas.width = maxWidth;
                canvas.height = totalHeight;
                const ctx = canvas.getContext('2d');

                // 填充背景色（#f5f5f5 页面背景）
                ctx.fillStyle = '#f5f5f5';
                ctx.fillRect(0, 0, maxWidth, totalHeight);

                // 按顺序绘制图片（添加间距和 padding）
                let currentY = CONTAINER_PADDING; // 顶部 padding
                images.forEach((img, index) => {
                    // 水平居中（包含左右 padding）
                    const x = Math.floor((maxWidth - img.width) / 2);
                    
                    // 为第一个元素之后的每个元素添加上边距背景
                    if (index > 0) {
                        ctx.fillStyle = '#f5f5f5';
                        ctx.fillRect(0, currentY, maxWidth, MARGIN_TOP);
                        currentY += MARGIN_TOP;
                    }
                    
                    // 绘制图片
                    ctx.drawImage(img, x, currentY);
                    currentY += img.height;
                    
                    // 添加下边距背景
                    if (index < images.length - 1) {
                        ctx.fillStyle = '#f5f5f5';
                        ctx.fillRect(0, currentY, maxWidth, MARGIN_BOTTOM);
                        currentY += MARGIN_BOTTOM;
                    }
                    
                    // 释放 blob URL
                    URL.revokeObjectURL(img.src);
                });

                // 转为 Blob
                return new Promise((resolve) => {
                    canvas.toBlob(resolve, 'image/png');
                });
            };

            // 全页截图
            const captureAll = async () => {
                const element = document.querySelector('.notebook-container');
                if (!element) {
                    showToast('未找到截图区域', 'error');
                    return;
                }

                try {
                    // 截图前确保页面有焦点
                    window.focus();
                    document.body.focus();
                    
                    const result = await snapdom(element, {
                        backgroundColor: '#f5f5f5',
                        scale: 1,
                        cache: 'auto'
                    });
                    
                    const blob = await result.toBlob({ type: 'png' });
                    
                    // 再次确保焦点
                    window.focus();
                    
                    try {
                        await navigator.clipboard.write([
                            new ClipboardItem({ 'image/png': blob })
                        ]);
                        showToast('全页截图已复制到剪贴板', 'success');
                    } catch (err) {
                        console.error('复制到剪贴板失败:', err);
                        // 自动下载图片
                        showToast('复制到剪贴板失败，正在下载图片...', 'info');
                        const url = URL.createObjectURL(blob);
                        const link = document.createElement('a');
                        link.download = `截图_${new Date().toLocaleString().replace(/[/:]/g, '-')}.png`;
                        link.href = url;
                        link.click();
                        URL.revokeObjectURL(url);
                    }
                } catch (err) {
                    console.error('截图失败:', err);
                    showToast('截图失败: ' + err.message, 'error');
                }
            };

            onMounted(() => {
                console.log('Notebook Vue3 应用已加载');
            });

            return {
                title,
                createdAt,
                cells,
                tocItems,
                selectedCount,
                isScreenshotMode,
                toastMessage,
                toastType,
                isSelected,
                toggleSelection,
                selectAll,
                clearSelection,
                scrollToSection,
                captureScreenshot,
                captureAll
            };
        }
    });
}

// 导出（如果支持模块系统）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CellRenderer, createNotebookApp };
}
