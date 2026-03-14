/**
 * Notebook Vue3 - Vue 3 组合式 API 版本的 Notebook 应用逻辑
 * 从 notebook.html 分离出来的 JavaScript
 */

const { createApp, ref, computed, onMounted, onUnmounted, nextTick } = Vue;

// ========== Cell 渲染组件（组合式 API）==========
const CellRenderer = {
    name: 'CellRenderer',
    components: {
        // FtTable 会从父组件传递，如果可用
        FtTable: typeof window !== 'undefined' && window.FtTable ? window.FtTable : null
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
                // 支持两种格式：字符串数组 或 对象数组
                return cell.options.columns.map(col => {
                    if (typeof col === 'string') {
                        return { field: col, title: col };
                    }
                    // 已经是对象格式 {field, title}
                    return { field: col.field, title: col.title || col.field };
                });
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
            if (cell.options?.heatmap) opts.heatmap = cell.options.heatmap;
            
            // page 参数：默认启用分页，false 禁用
            if (cell.options?.page !== undefined) {
                opts.page = cell.options.page;
            } else if (cell.options?.pagination !== undefined) {
                opts.pagination = cell.options.pagination;
            }
            
            return opts;
        };

        // 获取图表类型（从 pyecharts 的 charts 配置中提取）
        const getChartType = (content) => {
            return content.charts?.series?.[0]?.type || null;
        };

        // 从 pyecharts 配置中提取核心数据，转换为 buildChartOption 格式
        const extractChartData = (charts) => {
            if (!charts || !charts.series || !charts.series[0]) return null;
            
            const series = charts.series;
            const chartType = series[0].type;
            
            if (chartType === 'line' || chartType === 'bar') {
                const xAxisData = charts.xAxis?.[0]?.data || [];
                const extractedSeries = series.map(s => {
                    let data = s.data || [];
                    if (data.length > 0 && Array.isArray(data[0])) {
                        data = data.map(d => d[1]);
                    }
                    return { name: s.name, data };
                });
                return {
                    chart_type: chartType,
                    xAxis: xAxisData,
                    series: extractedSeries
                };
            }
            
            if (chartType === 'pie') {
                return {
                    chart_type: 'pie',
                    data: series[0].data || []
                };
            }
            
            if (chartType === 'heatmap') {
                const xAxisData = charts.xAxis?.[0]?.data || [];
                const yAxisData = charts.yAxis?.[0]?.data || [];
                const heatmapRawData = series[0].data || [];
                const heatmapDict = {};
                yAxisData.forEach((year, yIdx) => {
                    heatmapDict[year] = {};
                    xAxisData.forEach((month, mIdx) => {
                        const point = heatmapRawData.find(p => p[0] === mIdx && p[1] === yIdx);
                        heatmapDict[year][month] = point ? point[2] : 0;
                    });
                });
                return {
                    chart_type: 'heatmap',
                    data: heatmapDict
                };
            }
            
            return null;
        };

        // 初始化图表
        const initChart = () => {
            if (!chartRef.value || !props.cell.content) {
                console.warn('Chart init skipped: no chartRef or content');
                return;
            }

            const cell = props.cell;
            const content = cell.content;
            chartInstance = echarts.init(chartRef.value);
            
            if (!content.charts) {
                console.warn('Chart init skipped: no charts config');
                return;
            }
            
            // 深拷贝一份配置，避免修改原始数据
            const chartsConfig = JSON.parse(JSON.stringify(content.charts));
            
            const extracted = extractChartData(chartsConfig);
            if (!extracted) {
                // 直接使用原始配置，但已修改了 tooltip
                chartInstance.setOption(chartsConfig);
                return;
            }
            
            // 使用 buildChartOption 处理
            const chartType = extracted.chart_type;
            const data = extracted.data || extracted;
            
            if (chartType === 'pie') {
                pieRawData.value = extracted.data;
            }
            if (chartType === 'heatmap') {
                heatmapRawData.value = extracted.data;
                heatmapMultiplier.value = 1;
            }
            
            const option = buildChartOption(
                chartType === 'heatmap' ? 'heatmap' : 'chart',
                chartType,
                data,
                cell.options,
                heatmapMultiplier.value,
                pieShowValue.value,
                pieShowPercent.value
            );
            chartInstance.setOption(option);
        };
        
        // 更新热力图（当放大倍数改变时）
        const updateHeatmap = () => {
            if (!chartInstance || !heatmapRawData.value) return;
            const option = buildChartOption('heatmap', 'heatmap', heatmapRawData.value, props.cell.options, heatmapMultiplier.value);
            chartInstance.setOption(option, { replaceMerge: ['visualMap'] });
        };
        
        // 更新饼图（当显示选项改变时）
        const updatePie = () => {
            if (!chartInstance || !pieRawData.value) return;
            const option = buildChartOption('chart', 'pie', pieRawData.value, props.cell.options, 1, pieShowValue.value, pieShowPercent.value);
            chartInstance.setOption(option);
        };

        // 获取图表配色
        const getChartColors = (chartType) => {
            const colorPalettes = window.colorPalettes;
            const typeSpecific = colorPalettes.types[chartType];
            const paletteKey = typeSpecific || colorPalettes.global;
            const palette = colorPalettes.palettes[paletteKey];
            return palette ? palette.colors : ['#e74c3c', '#f39c12', '#af7ac5', '#5499c7', '#f4d03f', '#82e0aa', '#d35400', '#9b59b6', '#76d7c4'];
        };

        // 构建图表配置
        const buildChartOption = (type, chartType, data, options = {}, multiplier = 1, showValue = true, showPercent = true) => {
            const baseOption = {
                tooltip: {},
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
                        color: getChartColors('pie'),
                        tooltip: {},
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
                        tooltip: {},
                        legend: {
                            data: (data.series || []).map(s => ({
                                name: s.name,
                                icon: 'rect'
                            })),
                            top: 5,
                            itemStyle: {
                                color: getChartColors('bar')[0]
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
                                    const colors = getChartColors('bar');
                                    const value = params.value;
                                    if (value >= 0) {
                                        return colors[0];
                                    } else {
                                        return colors[1];
                                    }
                                },
                                borderRadius: [4, 4, 0, 0]
                            }
                        }))
                    };
                }

                // 折线图和面积图
                return {
                    color: getChartColors('line'),
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
                                    { offset: 0, color: getChartColors('line')[i % getChartColors('line').length] + '60' },
                                    { offset: 1, color: getChartColors('line')[i % getChartColors('line').length] + '10' }
                                ]
                            }
                        } : undefined,
                        itemStyle: { color: getChartColors('line')[i % getChartColors('line').length] }
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

                // 应用传入的放大倍数（保持为数字类型）
                const displayData = heatmapData.map(d => [d[0], d[1], d[2] * multiplier]);
                
                // 根据放大后的数据范围设置 visualMap（实际最大值最小值）
                const displayValues = displayData.map(d => d[2]);
                const actualMin = Math.min(...displayValues);
                const actualMax = Math.max(...displayValues);
                
                // 根据数值范围确定合适的步长和小数位数
                const valueRange = actualMax - actualMin;
                let step = 0.01;
                let decimalPlaces = 2;
                
                if (valueRange >= 10) {
                    step = 5;
                    decimalPlaces = 0;
                } else if (valueRange >= 1) {
                    step = 0.5;
                    decimalPlaces = 1;
                } else if (valueRange >= 0.1) {
                    step = 0.05;
                    decimalPlaces = 2;
                }
                
                // 向上/向下取整，让边界更美观
                const visualMin = Math.floor(actualMin / step) * step;
                const visualMax = Math.ceil(actualMax / step) * step;

                return {
                    tooltip: {},
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
                        min: visualMin,
                        max: visualMax,
                        range: [visualMin, visualMax],
                        calculable: true,
                        orient: 'vertical',
                        right: '2%',
                        top: 'center',
                        text: [visualMax.toFixed(decimalPlaces) + ' (×' + multiplier + ')', 
                               visualMin.toFixed(decimalPlaces) + ' (×' + multiplier + ')'],
                        inRange: {
                            color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8',
                                    '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026']
                        }
                    },
                    series: [{
                        name: '收益',
                        type: 'heatmap',
                        data: displayData,
                        label: { show: true, formatter: function(params) {
                            return params.value[2].toFixed(2);
                        }},
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
                
                // 监听配色方案变化，更新图表
                window.addEventListener('colorSchemeChanged', initChart);
            }
        });
        
        onUnmounted(() => {
            // 移除resize监听，避免内存泄漏
            window.removeEventListener('resize', handleResize);
            // 移除配色方案变化监听
            window.removeEventListener('colorSchemeChanged', initChart);
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
            getTableOptions,
            getChartType
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
                <ft-table
                    v-else
                    :id="'table-' + cellId"
                    :data="cell.content"
                    :cols="getTableCols(cell)"
                    v-bind="getTableOptions(cell)">
                </ft-table>
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
            <div v-else-if="cell.content?.charts && getChartType(cell.content) === 'pie'"
                 class="cell-chart pie-with-control">
                <h3 v-if="cell.title">{{ cell.title }}</h3>
                <div class="pie-wrapper">
                    <div ref="chartRef"
                         class="chart-container"
                         :style="{
                             width: cell.content?.width || '100%',
                             height: typeof (cell.content?.height || cell.options?.height) === 'string' ? (cell.content?.height || cell.options?.height) : (cell.content?.height || cell.options?.height || 400) + 'px'
                         }">
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
            
            <!-- 热力图（带放大倍数控制） -->
            <div v-else-if="cell.content?.charts && getChartType(cell.content) === 'heatmap'"
                 class="cell-chart heatmap-with-control">
                <h3 v-if="cell.title">{{ cell.title }}</h3>
                <div class="heatmap-wrapper">
                    <div ref="chartRef"
                         class="chart-container"
                         :style="{
                             width: cell.content?.width || '100%',
                             height: typeof (cell.content?.height || cell.options?.height) === 'string' ? (cell.content?.height || cell.options?.height) : (cell.content?.height || cell.options?.height || 400) + 'px'
                         }">
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
            
            <!-- 其他图表（折线图、柱状图等） -->
            <div v-else-if="(cell.type === 'chart' || cell.type === 'pyecharts') && cell.content?.charts" 
                 class="cell-chart">
                <h3 v-if="cell.title">{{ cell.title }}</h3>
                <div ref="chartRef"
                     class="chart-container"
                     :style="{
                         width: cell.content?.width || '100%',
                         height: typeof (cell.content?.height || cell.options?.height) === 'string' ? (cell.content?.height || cell.options?.height) : (cell.content?.height || cell.options?.height || 400) + 'px'
                     }">
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
    // 从全局获取 FtTable 组件（由 ft-table.js 暴露到 window）
    const FtTableComponent = typeof window !== 'undefined' ? window.FtTable : null;
    console.log('FtTableComponent:', FtTableComponent);
    
    return createApp({
        components: {
            CellRenderer,
            FtTable: FtTableComponent
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
            
            // 新版菜单状态 - 简化管理
            const menuCollapsed = ref(false);     // 目录菜单收窄状态（手动）
            const isNarrow = ref(false);          // 是否窄屏（自动检测）
            const showColorPicker = ref(false);   // 配色抽屉开关
            
            // 检测屏幕宽度
            const checkScreenWidth = () => {
                const newIsNarrow = window.innerWidth <= 1200;  // 1200px 以下自动收窄
                // 当从窄屏变回宽屏时，强制展开菜单
                if (!newIsNarrow && isNarrow.value) {
                    menuCollapsed.value = false;
                }
                isNarrow.value = newIsNarrow;
                console.log('Screen width:', window.innerWidth, 'isNarrow:', isNarrow.value);
            };
            
            // 展开菜单（窄屏时点击首字展开）
            const expandMenu = () => {
                if (isNarrow.value) {
                    // 窄屏时临时展开
                    isNarrow.value = false;
                } else {
                    menuCollapsed.value = false;
                }
            };
            
            // 配色方案
            const colorPalettes = Vue.reactive(window.colorPalettes || {
                global: 'warmToCool',
                types: {
                    line: 'warmToCool',
                    bar: 'contrast',
                    pie: 'warmToCool'
                },
                palettes: {
                    warmToCool: {
                        name: '暖冷渐变系',
                        desc: '珊瑚橙粉紫青金绿',
                        colors: ['#e74c3c', '#f39c12', '#af7ac5', '#5499c7', '#f4d03f', '#82e0aa', '#d35400', '#9b59b6', '#76d7c4']
                    },
                    contrast: {
                        name: '高对比度系',
                        desc: '清晰易辨识',
                        colors: ['#e74c3c', '#27ae60', '#f39c12', '#9b59b6', '#3498db', '#e74c3c', '#2ecc71', '#e67e22', '#95a5a6']
                    },
                    dahongdazi: {
                        name: '大红大紫系',
                        desc: '红紫粉金，柔和现代',
                        colors: ['#e74c3c', '#9b59b6', '#f39c12', '#e91e63', '#f1c40f', '#8e44ad', '#ff6b6b', '#af7ac5', '#daa520']
                    },
                    echartsDefault: {
                        name: 'ECharts默认',
                        desc: '官方默认配色',
                        colors: ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc']
                    }
                }
            });
            window.colorPalettes = colorPalettes;
            
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
                tocOpen.value = false; // 点击后关闭抽屉
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
                    // ft-table 是异步渲染，需要给予足够时间
                    await new Promise(resolve => setTimeout(resolve, 300));

                    // 4. 逐个截图
                    const imageBlobs = [];
                    for (const el of elementsToCapture) {
                        // 检查元素内是否有表格，如果有额外等待
                        const hasTable = el.querySelector('ft-table, .ft-table, table');
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
            
            // 切换配色抽屉
            const toggleColorPicker = () => {
                showColorPicker.value = !showColorPicker.value;
            };
            
            // 设置配色方案
            const setColorPalette = (scope, paletteKey) => {
                if (scope === 'global') {
                    colorPalettes.global = paletteKey;
                    // 当选择全局配色时，同步更新所有图表类型的配色
                    Object.keys(colorPalettes.types).forEach(type => {
                        colorPalettes.types[type] = paletteKey;
                    });
                } else if (colorPalettes.types[scope]) {
                    colorPalettes.types[scope] = paletteKey;
                }
                updateChartColors();
            };
            
            // 更新图表配色
            const updateChartColors = () => {
                // 触发自定义事件，通知所有图表更新配色
                window.dispatchEvent(new CustomEvent('colorSchemeChanged'));
            };

            onMounted(() => {
                console.log('Notebook Vue3 应用已加载');
                // 初始化屏幕宽度检测
                checkScreenWidth();
                // 监听窗口大小变化
                window.addEventListener('resize', checkScreenWidth);
            });

            onUnmounted(() => {
                // 移除resize监听
                window.removeEventListener('resize', checkScreenWidth);
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
                captureAll,
                // 新版菜单状态
                menuCollapsed,
                isNarrow,
                expandMenu,
                showColorPicker,
                toggleColorPicker,
                // 配色管理
                colorPalettes,
                setColorPalette,
                updateChartColors
            };
        }
    });
}

// 导出（如果支持模块系统）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CellRenderer, createNotebookApp };
}
