/**
 * Notebook Vue3 - Vue 3 组合式 API 版本的 Notebook 应用逻辑
 * 从 notebook.html 分离出来的 JavaScript
 */

const { createApp, ref, computed, onMounted, onUnmounted, nextTick } = Vue;

// =============================================================================
// 第一部分：CellRenderer 组件 - 核心渲染组件
// =============================================================================

const CellRenderer = {
    name: 'CellRenderer',
    components: {
        FtTable: typeof window !== 'undefined' && window.FtTable ? window.FtTable : null
    },
    props: {
        cell: { type: Object, required: true },
        cellId: { type: [String, Number], required: true },
        level: { type: Number, default: 0 }
    },
    setup(props) {
        // -----------------------------------------------------------------------------
        // 1. 响应式状态定义
        // -----------------------------------------------------------------------------
        const chartRef = ref(null);
        let chartInstance = null;
        const heatmapMultiplier = ref(1);
        const heatmapRawData = ref(null);
        const pieShowValue = ref(true);
        const pieShowPercent = ref(true);
        const pieRawData = ref(null);
        const stackNormalize = ref(false);
        const stackShowRaw = ref(true);
        const stackShowPercent = ref(false);
        const stackRawData = ref(null);

        // -----------------------------------------------------------------------------
        // 2. 工具函数
        // -----------------------------------------------------------------------------
        const renderMarkdown = (content) => {
            if (!content) return '';
            return content
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/`(.*?)`/g, '<code>$1</code>')
                .replace(/\n/g, '<br>');
        };

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

        const getTableCols = (cell) => {
            if (cell.options?.columns) {
                return cell.options.columns.map(col => {
                    if (typeof col === 'string') {
                        return { field: col, title: col };
                    }
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

        const getTableOptions = (cell) => {
            const opts = {};
            if (cell.options?.freeze) opts.freeze = cell.options.freeze;
            if (cell.options?.heatmap) opts.heatmap = cell.options.heatmap;
            if (cell.options?.page !== undefined) {
                opts.page = cell.options.page;
            }
            return opts;
        };

        const getChartType = (content) => {
            return content.charts?.series?.[0]?.type || null;
        };

        const isStackedChart = (content) => {
            const chartType = getChartType(content);
            if (!['bar', 'line'].includes(chartType)) return false;
            const series = content.charts?.series || [];
            return series.some(s => s.stack);
        };

        // -----------------------------------------------------------------------------
        // 3. 图表数据提取与配色
        // -----------------------------------------------------------------------------
        const extractChartData = (charts) => {
            if (!charts?.series?.[0]) return null;
            return {
                chart_type: charts.series[0].type,
                series: charts.series,
                xAxis: charts.xAxis?.[0]?.data || [],
                yAxis: charts.yAxis?.[0]?.data || [],
                raw: charts  // 保留原始配置，供特殊类型使用
            };
        };

        const getChartColors = (chartType) => {
            const colorPalettes = window.colorPalettes;
            const group = colorPalettes.typeToGroup[chartType] || 'chart';
            const paletteKey = colorPalettes.groups[group] || colorPalettes.global;
            const palette = colorPalettes.palettes[paletteKey];
            return palette ? palette.colors : ['#e74c3c', '#f39c12', '#af7ac5', '#5499c7', '#f4d03f', '#82e0aa', '#d35400', '#9b59b6', '#76d7c4'];
        };

        // -----------------------------------------------------------------------------
        // 4. 图表处理插件
        // -----------------------------------------------------------------------------

        // 特殊类型插件（无差异化处理，直接适配基础配置）
        const gaugePlugin = (extracted) => ({
            series: extracted.series
        });

        const radarPlugin = (extracted) => ({
            ...extracted.raw  // 保留原始 radar/indicator 配置
        });

        const funnelPlugin = (extracted) => ({
            series: extracted.series
        });

        const chartPlugins = {
            pie: (extracted, options) => processPie(extracted, options),
            heatmap: (extracted, options) => processHeatmap(extracted, options),
            gauge: gaugePlugin,
            radar: radarPlugin,
            funnel: funnelPlugin
        };

        const processChart = (extracted, options = {}) => {
            const chartType = extracted.chart_type;
            const plugin = chartPlugins[chartType];
            
            if (chartType !== 'heatmap') {
                options.colors = getChartColors(chartType);
            }
            
            const isStacked = extracted.series.some(s => s.stack);
            if (['bar', 'line'].includes(chartType) && isStacked) {
                const option = processStackedChart(extracted, options);
                if (!option.tooltip) {
                    option.tooltip = {};
                }
                return option;
            }
            
            const option = plugin ? plugin(extracted, options) : buildGenericOption(extracted, options);
            
            if (!option.tooltip) {
                option.tooltip = {};
            }
            
            return option;
        };

        // -----------------------------------------------------------------------------
        // 5. 通用图表配置构建
        // -----------------------------------------------------------------------------
        const buildGenericOption = (extracted, options = {}) => {
            const colors = options.colors || getChartColors(extracted.chart_type);
            const chartType = extracted.chart_type;
            const series = extracted.series || [];

            const option = {
                color: colors,
                series: series
            };

            if (['line', 'bar', 'area'].includes(chartType)) {
                const isBarChart = chartType === 'bar';
                
                option.xAxis = {
                    type: 'category',
                    boundaryGap: isBarChart,
                    data: extracted.xAxis
                };
                option.yAxis = {
                    type: 'value',
                    scale: true,
                    boundaryGap: ['10%', '10%']
                };
                option.grid = { left: 8, right: 8, bottom: 5, top: 28, containLabel: true };
                option.legend = {
                    data: series.map(s => ({ name: s.name, icon: 'rect' })),
                    top: 5
                };

                option.series = series.map((s, i) => {
                    const baseOption = {
                        name: s.name,
                        type: chartType === 'area' ? 'line' : chartType,
                        data: s.data
                    };
                    
                    if (s.stack) {
                        baseOption.stack = s.stack;
                    }

                    if (chartType === 'line' || chartType === 'area') {
                        baseOption.smooth = true;
                        if (chartType === 'area') {
                            baseOption.areaStyle = {
                                color: {
                                    type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                                    colorStops: [
                                        { offset: 0, color: colors[i % colors.length] + '60' },
                                        { offset: 1, color: colors[i % colors.length] + '10' }
                                    ]
                                }
                            };
                        }
                    }

                    if (isBarChart) {
                        const isSingleSeries = series.length === 1 && !s.stack;
                        baseOption.itemStyle = {
                            color: isSingleSeries ? function(params) {
                                return params.value >= 0 ? colors[0] : colors[1];
                            } : colors[i % colors.length],
                            borderRadius: [4, 4, 0, 0]
                        };
                    }

                    return baseOption;
                });
            } else if (chartType === 'scatter') {
                if (extracted.xAxis.length) option.xAxis = { type: 'category', data: extracted.xAxis };
                if (extracted.yAxis.length) option.yAxis = { type: 'category', data: extracted.yAxis };
            }

            return option;
        };

        // -----------------------------------------------------------------------------
        // 6. Pie 图表插件
        // -----------------------------------------------------------------------------
        const processPie = (extracted, options) => {
            const colors = options.colors || getChartColors('pie');
            const data = extracted.series[0]?.data || [];
            const { showValue = true, showPercent = true } = options;

            let labelFormatter = '{b}';
            if (showValue && showPercent) labelFormatter = '{b}\n{c} ({d}%)';
            else if (showValue) labelFormatter = '{b}\n{c}';
            else if (showPercent) labelFormatter = '{b}\n({d}%)';

            return {
                color: colors,
                legend: {
                    data: data.map((item, i) => ({
                        name: item.name,
                        itemStyle: { color: colors[i % colors.length] }
                    })),
                    top: 10, left: 'center', orient: 'horizontal'
                },
                series: [{
                    type: 'pie',
                    data: data,
                    radius: ['40%', '70%'],
                    center: ['45%', '55%'],
                    label: { show: true, formatter: labelFormatter },
                    labelLine: { show: true, length: 15, length2: 10 },
                    emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } }
                }]
            };
        };

        // -----------------------------------------------------------------------------
        // 7. Heatmap 图表插件
        // -----------------------------------------------------------------------------
        const HEATMAP_COLORS = [
            '#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8',
            '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'
        ];

        const processHeatmap = (extracted, options) => {
            const rawData = extracted.series[0]?.data || [];
            const { multiplier = 1 } = options;

            let minValue = Infinity, maxValue = -Infinity;
            const displayData = rawData.map(d => {
                const scaled = d[2] * multiplier;
                if (scaled < minValue) minValue = scaled;
                if (scaled > maxValue) maxValue = scaled;
                return [d[0], d[1], scaled];
            });

            const valueRange = maxValue - minValue;
            let step = 0.01, decimalPlaces = 2;
            if (valueRange >= 10) { step = 5; decimalPlaces = 0; }
            else if (valueRange >= 1) { step = 0.5; decimalPlaces = 1; }
            else if (valueRange >= 0.1) { step = 0.05; decimalPlaces = 2; }
            const visualMin = Math.floor(minValue / step) * step;
            const visualMax = Math.ceil(maxValue / step) * step;

            return {
                grid: { left: '10%', right: '18%', top: '10%', bottom: '12%' },
                xAxis: { type: 'category', data: extracted.xAxis, splitArea: { show: true } },
                yAxis: { type: 'category', data: extracted.yAxis, splitArea: { show: true } },
                visualMap: {
                    min: visualMin, max: visualMax,
                    range: [visualMin, visualMax],
                    calculable: true, orient: 'vertical', right: '2%', top: 'center',
                    text: [visualMax.toFixed(decimalPlaces) + ' (×' + multiplier + ')',
                           visualMin.toFixed(decimalPlaces) + ' (×' + multiplier + ')'],
                    inRange: { color: HEATMAP_COLORS }
                },
                series: [{
                    type: 'heatmap',
                    data: displayData,
                    label: { show: true, formatter: params => params.value[2].toFixed(2) },
                    emphasis: { itemStyle: { shadowBlur: 10 } }
                }]
            };
        };

        const calculateStackTotals = (series) => {
            const rawData = series.map(s => [...(s.data || [])]);
            const dataLength = rawData[0]?.length || 0;
            const totals = new Array(dataLength).fill(0);
            rawData.forEach(sData => {
                sData.forEach((v, i) => {
                    totals[i] = (totals[i] || 0) + (v || 0);
                });
            });
            return { rawData, totals };
        };

        const buildStackLabelFormatter = (rawData, totals, showRaw, showPercent) => {
            return function(seriesIndex) {
                return function(params) {
                    const rawValue = rawData[seriesIndex][params.dataIndex];
                    const total = totals[params.dataIndex];
                    const percent = total > 0 ? (rawValue / total * 100).toFixed(1) : 0;
                    
                    if (showRaw && showPercent) {
                        return `${rawValue}\n(${percent}%)`;
                    } else if (showRaw) {
                        return String(rawValue);
                    } else if (showPercent) {
                        return `${percent}%`;
                    }
                    return '';
                };
            };
        };

        const buildStackTooltipFormatter = (rawData, totals, showRaw, showPercent) => {
            return function(params) {
                const xValue = params[0].axisValue;
                const total = totals[params[0].dataIndex];
                let result = `<strong>${xValue}</strong><br/>`;
                result += `<div style="color:#666;margin-bottom:4px;">总计: ${total}</div>`;
                params.forEach(p => {
                    const rawValue = rawData[p.seriesIndex][p.dataIndex];
                    const percent = total > 0 ? (rawValue / total * 100).toFixed(1) : 0;
                    let label = `${p.seriesName}: `;
                    if (showRaw && showPercent) {
                        label += `${rawValue} (${percent}%)`;
                    } else if (showRaw) {
                        label += rawValue;
                    } else if (showPercent) {
                        label += `${percent}%`;
                    } else {
                        label += rawValue;
                    }
                    result += `${p.marker} ${label}<br/>`;
                });
                return result;
            };
        };

        const processStackedChart = (extracted, options) => {
            const colors = options.colors || getChartColors(extracted.chart_type);
            const chartType = extracted.chart_type;
            const series = extracted.series || [];
            const { normalize = false, showRaw = true, showPercentStack = false } = options;

            const { rawData, totals } = calculateStackTotals(series);
            const labelFormatter = buildStackLabelFormatter(rawData, totals, showRaw, showPercentStack);
            const tooltipFormatter = buildStackTooltipFormatter(rawData, totals, showRaw, showPercentStack);

            let displaySeries;
            let yAxisConfig;

            if (normalize) {
                displaySeries = series.map((s, i) => ({
                    ...s,
                    data: rawData[i].map((v, j) => totals[j] > 0 ? (v / totals[j] * 100) : 0),
                    type: chartType === 'area' ? 'line' : chartType
                }));
                yAxisConfig = {
                    type: 'value',
                    min: 0,
                    max: 100,
                    axisLabel: {
                        formatter: '{value}%'
                    }
                };
            } else {
                displaySeries = series.map((s, i) => ({
                    ...s,
                    data: [...rawData[i]],
                    type: chartType === 'area' ? 'line' : chartType
                }));
                yAxisConfig = {
                    type: 'value',
                    scale: true,
                    boundaryGap: ['10%', '10%']
                };
            }

            const isBarChart = chartType === 'bar';
            
            const option = {
                color: colors,
                xAxis: {
                    type: 'category',
                    boundaryGap: isBarChart,
                    data: extracted.xAxis
                },
                yAxis: yAxisConfig,
                grid: { left: 8, right: 8, bottom: 5, top: 28, containLabel: true },
                legend: {
                    data: series.map(s => ({ name: s.name, icon: 'rect' })),
                    top: 5
                },
                tooltip: {
                    trigger: 'axis',
                    axisPointer: { type: 'shadow' },
                    formatter: tooltipFormatter
                },
                series: displaySeries.map((s, i) => {
                    const baseOption = {
                        name: s.name,
                        type: chartType === 'area' ? 'line' : chartType,
                        data: s.data,
                        stack: s.stack,
                        label: {
                            show: showRaw || showPercentStack,
                            position: 'inside',
                            formatter: labelFormatter(i)
                        }
                    };
                    if (chartType === 'line' || chartType === 'area') {
                        baseOption.smooth = true;
                        if (chartType === 'area') {
                            baseOption.areaStyle = {
                                color: {
                                    type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                                    colorStops: [
                                        { offset: 0, color: colors[i % colors.length] + '60' },
                                        { offset: 1, color: colors[i % colors.length] + '10' }
                                    ]
                                }
                            };
                        }
                    }
                    if (isBarChart) {
                        baseOption.itemStyle = {
                            color: colors[i % colors.length],
                            borderRadius: [4, 4, 0, 0]
                        };
                    }
                    return baseOption;
                })
            };

            return option;
        };

        // -----------------------------------------------------------------------------
        // 8. 图表初始化与更新
        // -----------------------------------------------------------------------------
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

            const chartsConfig = JSON.parse(JSON.stringify(content.charts));
            const extracted = extractChartData(chartsConfig);
            if (!extracted) {
                chartInstance.setOption(chartsConfig);
                return;
            }

            const chartType = extracted.chart_type;

            if (chartType === 'pie') {
                pieRawData.value = extracted;
            }
            if (chartType === 'heatmap') {
                heatmapRawData.value = extracted;
                heatmapMultiplier.value = 1;
            }
            
            const isStacked = extracted.series.some(s => s.stack);
            if (['bar', 'line'].includes(chartType) && isStacked) {
                stackRawData.value = extracted;
                stackNormalize.value = false;
                stackShowRaw.value = true;
                stackShowPercent.value = false;
                lastNormalizeState = false;
            }

            const options = {
                multiplier: heatmapMultiplier.value,
                showValue: pieShowValue.value,
                showPercent: pieShowPercent.value,
                normalize: stackNormalize.value,
                showRaw: stackShowRaw.value,
                showPercentStack: stackShowPercent.value
            };
            const option = processChart(extracted, options);
            chartInstance.setOption(option);
        };

        const updateHeatmap = () => {
            if (!chartInstance || !heatmapRawData.value) return;
            const option = processChart(heatmapRawData.value, { multiplier: heatmapMultiplier.value });
            chartInstance.setOption(option, { replaceMerge: ['visualMap'] });
        };

        const updatePie = () => {
            if (!chartInstance || !pieRawData.value) return;
            const option = processChart(pieRawData.value, {
                showValue: pieShowValue.value,
                showPercent: pieShowPercent.value
            });
            chartInstance.setOption(option);
        };

        let lastNormalizeState = false;

        const updateStack = () => {
            if (!chartInstance || !stackRawData.value) return;
            
            const normalizeChanged = lastNormalizeState !== stackNormalize.value;
            lastNormalizeState = stackNormalize.value;
            
            if (!normalizeChanged) {
                const { rawData, totals } = calculateStackTotals(stackRawData.value.series);
                const showRaw = stackShowRaw.value;
                const showPercent = stackShowPercent.value;
                const labelFormatter = buildStackLabelFormatter(rawData, totals, showRaw, showPercent);
                const tooltipFormatter = buildStackTooltipFormatter(rawData, totals, showRaw, showPercent);
                
                const series = stackRawData.value.series.map((s, i) => ({
                    label: {
                        show: showRaw || showPercent,
                        position: 'inside',
                        formatter: labelFormatter(i)
                    }
                }));
                
                chartInstance.setOption({
                    series: series,
                    tooltip: {
                        trigger: 'axis',
                        axisPointer: { type: 'shadow' },
                        formatter: tooltipFormatter
                    }
                });
            } else {
                const option = processChart(stackRawData.value, {
                    normalize: stackNormalize.value,
                    showRaw: stackShowRaw.value,
                    showPercentStack: stackShowPercent.value
                });
                chartInstance.setOption(option, { replaceMerge: ['yAxis', 'series'] });
            }
        };

        const handleResize = () => {
            if (chartInstance) {
                chartInstance.resize();
            }
        };

        // -----------------------------------------------------------------------------
        // 9. 生命周期钩子
        // -----------------------------------------------------------------------------
        onMounted(() => {
            if (['chart', 'heatmap', 'pyecharts'].includes(props.cell.type)) {
                nextTick(() => initChart());
                window.addEventListener('resize', handleResize);
                window.addEventListener('colorSchemeChanged', initChart);
            }
        });

        onUnmounted(() => {
            window.removeEventListener('resize', handleResize);
            window.removeEventListener('colorSchemeChanged', initChart);
            if (chartInstance) {
                chartInstance.dispose();
                chartInstance = null;
            }
        });

        // -----------------------------------------------------------------------------
        // 10. 暴露给模板的属性和方法
        // -----------------------------------------------------------------------------
        return {
            chartRef,
            heatmapMultiplier,
            updateHeatmap,
            pieShowValue,
            pieShowPercent,
            updatePie,
            stackNormalize,
            stackShowRaw,
            stackShowPercent,
            updateStack,
            renderMarkdown,
            getMetricClass,
            getTableCols,
            getTableOptions,
            getChartType,
            isStackedChart
        };
    },

    // -----------------------------------------------------------------------------
    // 11. 模板
    // -----------------------------------------------------------------------------
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

            <!-- 堆叠图（带显示模式控制） -->
            <div v-else-if="cell.content?.charts && isStackedChart(cell.content)"
                 class="cell-chart stack-with-control">
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
                        <div class="control-label">归一化</div>
                        <div class="checkbox-group">
                            <label class="checkbox-item">
                                <input
                                    type="checkbox"
                                    v-model="stackNormalize"
                                    @change="updateStack">
                                <span>启用</span>
                            </label>
                        </div>
                        <div class="control-label" style="margin-top: 12px;">显示选项</div>
                        <div class="checkbox-group">
                            <label class="checkbox-item">
                                <input
                                    type="checkbox"
                                    v-model="stackShowRaw"
                                    @change="updateStack">
                                <span>原始数据</span>
                            </label>
                            <label class="checkbox-item">
                                <input
                                    type="checkbox"
                                    v-model="stackShowPercent"
                                    @change="updateStack">
                                <span>百分比</span>
                            </label>
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

// =============================================================================
// 第二部分：ColorPicker 组件 - 配色选择器
// =============================================================================

const ColorPicker = {
    name: 'ColorPicker',
    setup() {
        const showColorPicker = ref(false);
        const colorPalettes = window.colorPalettes;

        const toggleColorPicker = () => {
            showColorPicker.value = !showColorPicker.value;
        };

        const setColorPalette = (scope, paletteKey) => {
            if (scope === 'global') {
                colorPalettes.global = paletteKey;
                Object.keys(colorPalettes.groups).forEach(group => {
                    colorPalettes.groups[group] = paletteKey;
                });
            } else if (colorPalettes.groups[scope] !== undefined) {
                colorPalettes.groups[scope] = paletteKey;
            }
            window.dispatchEvent(new CustomEvent('colorSchemeChanged'));
        };

        return {
            showColorPicker,
            colorPalettes,
            toggleColorPicker,
            setColorPalette
        };
    },
    template: `
        <div>
            <div class="color-float-btn" @click="toggleColorPicker" :class="{ active: showColorPicker }" title="配色">
                <span>🎨</span>
            </div>

            <div class="drawer-overlay" v-if="showColorPicker" @click="showColorPicker = false"></div>
            <aside class="color-drawer" :class="{ open: showColorPicker }">
                <div class="drawer-header">
                    <span>🎨 配色方案</span>
                    <button class="close-btn" @click="showColorPicker = false">✕</button>
                </div>
                <div class="drawer-body">
                    <div class="palette-group">
                        <h5>全局配色</h5>
                        <div class="palette-options">
                            <button v-for="(palette, key) in colorPalettes.palettes" :key="key"
                                    class="palette-btn"
                                    :class="{ active: colorPalettes.global === key }"
                                    @click="setColorPalette('global', key)">
                                <div class="palette-preview">
                                    <span v-for="(color, idx) in palette.colors.slice(0, 5)"
                                          :key="idx"
                                          class="palette-color-dot"
                                          :style="{ backgroundColor: color }"></span>
                                </div>
                                <span class="palette-name">{{ palette.name }}</span>
                            </button>
                        </div>
                    </div>
                    <div class="palette-group">
                        <h5>按图表类型</h5>
                        <div class="palette-options">
                            <div class="chart-type-picker">
                                <label>通用类:</label>
                                <select :value="colorPalettes.groups.chart" @change="setColorPalette('chart', $event.target.value)">
                                    <option v-for="(palette, key) in colorPalettes.palettes" :key="key" :value="key">
                                        {{ palette.name }}
                                    </option>
                                </select>
                            </div>
                            <div class="chart-type-picker">
                                <label>占比类:</label>
                                <select :value="colorPalettes.groups.pie" @change="setColorPalette('pie', $event.target.value)">
                                    <option v-for="(palette, key) in colorPalettes.palettes" :key="key" :value="key">
                                        {{ palette.name }}
                                    </option>
                                </select>
                            </div>
                        </div>
                    </div>
                </div>
            </aside>
        </div>
    `
};

// =============================================================================
// 第三部分：TocMenu 组件 - 目录菜单组件
// =============================================================================

const TocMenu = {
    name: 'TocMenu',
    props: {
        title: { type: String, default: '' },
        createdAt: { type: String, default: '' },
        cells: { type: Array, default: () => [] }
    },
    setup(props) {
        // -----------------------------------------------------------------------------
        // 1. 响应式状态
        // -----------------------------------------------------------------------------
        const selectedIndices = ref(new Set());
        const menuExpanded = ref(false);
        const isNarrow = ref(false);

        // -----------------------------------------------------------------------------
        // 2. 计算属性
        // -----------------------------------------------------------------------------
        const tocItems = computed(() => {
            const items = [];
            if (props.title) {
                items.push({ title: props.title, type: 'header', index: -1 });
            }
            props.cells.forEach((cell, index) => {
                if (cell.type === 'section' && cell.title) {
                    items.push({ title: cell.title, type: 'section', index });
                }
            });
            return items;
        });

        const selectedCount = computed(() => selectedIndices.value.size);

        // -----------------------------------------------------------------------------
        // 3. 方法
        // -----------------------------------------------------------------------------
        const isSelected = (index) => selectedIndices.value.has(index);

        const toggleSelection = (index) => {
            const newSet = new Set(selectedIndices.value);
            if (newSet.has(index)) {
                newSet.delete(index);
            } else {
                newSet.add(index);
            }
            selectedIndices.value = newSet;
        };

        const selectAll = () => {
            const allIndices = tocItems.value.map(item => item.index);
            selectedIndices.value = new Set(allIndices);
        };

        const clearSelection = () => {
            selectedIndices.value = new Set();
        };

        const scrollToSection = (index) => {
            if (index === -1) {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                const el = document.getElementById('section-' + index);
                if (el) el.scrollIntoView({ behavior: 'smooth' });
            }
        };

        const toggleMenu = () => {
            menuExpanded.value = !menuExpanded.value;
            setTimeout(() => {
                window.dispatchEvent(new Event('resize'));
            }, 350);
        };

        const checkScreenWidth = () => {
            const width = window.innerWidth;
            const wasNarrow = isNarrow.value;
            isNarrow.value = width <= 1200;

            if (!isNarrow.value) {
                menuExpanded.value = true;
            } else if (!wasNarrow && isNarrow.value) {
                menuExpanded.value = false;
            }
        };

        // -----------------------------------------------------------------------------
        // 4. 截图功能
        // -----------------------------------------------------------------------------
        const stitchImages = async (imageBlobs) => {
            const images = await Promise.all(imageBlobs.map(blob => {
                return new Promise((resolve, reject) => {
                    const img = new Image();
                    img.onload = () => resolve(img);
                    img.onerror = reject;
                    img.src = URL.createObjectURL(blob);
                });
            }));

            const MARGIN_TOP = 12;
            const MARGIN_BOTTOM = 12;
            const CONTAINER_PADDING = 20;

            const maxContentWidth = Math.max(...images.map(img => img.width));
            const maxWidth = maxContentWidth + CONTAINER_PADDING * 2;
            const contentHeight = images.reduce((sum, img) => sum + img.height, 0);
            const spacingHeight = (images.length - 1) * (MARGIN_TOP + MARGIN_BOTTOM);
            const totalHeight = contentHeight + spacingHeight + CONTAINER_PADDING * 2;

            const canvas = document.createElement('canvas');
            canvas.width = maxWidth;
            canvas.height = totalHeight;
            const ctx = canvas.getContext('2d');

            ctx.fillStyle = '#f5f5f5';
            ctx.fillRect(0, 0, maxWidth, totalHeight);

            let currentY = CONTAINER_PADDING;
            images.forEach((img, index) => {
                const x = Math.floor((maxWidth - img.width) / 2);

                if (index > 0) {
                    ctx.fillStyle = '#f5f5f5';
                    ctx.fillRect(0, currentY, maxWidth, MARGIN_TOP);
                    currentY += MARGIN_TOP;
                }

                ctx.drawImage(img, x, currentY);
                currentY += img.height;

                if (index < images.length - 1) {
                    ctx.fillStyle = '#f5f5f5';
                    ctx.fillRect(0, currentY, maxWidth, MARGIN_BOTTOM);
                    currentY += MARGIN_BOTTOM;
                }

                URL.revokeObjectURL(img.src);
            });

            return new Promise((resolve) => {
                canvas.toBlob(resolve, 'image/png');
            });
        };

        const showToast = (message, type = 'info', duration = 3000) => {
            if (typeof window !== 'undefined' && window.showToast) {
                window.showToast(message, type, duration);
            }
        };

        const captureScreenshot = async () => {
            if (selectedIndices.value.size === 0) return;

            const mainContainer = document.querySelector('.notebook-container');
            const elementsToCapture = [];

            if (selectedIndices.value.has(-1)) {
                const header = mainContainer.querySelector('.notebook-header');
                if (header) elementsToCapture.push(header);
            }

            const sortedIndices = [...selectedIndices.value]
                .filter(index => index !== -1)
                .sort((a, b) => a - b);

            sortedIndices.forEach(index => {
                const section = document.getElementById('section-' + index);
                if (section) elementsToCapture.push(section);
            });

            try {
                await new Promise(resolve => setTimeout(resolve, 300));

                const imageBlobs = [];
                for (const el of elementsToCapture) {
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

                const finalBlob = await stitchImages(imageBlobs);

                try {
                    window.focus();
                    await navigator.clipboard.write([
                        new ClipboardItem({ 'image/png': finalBlob })
                    ]);
                    showToast(`已复制 ${selectedIndices.value.size} 个选中区域到剪贴板`, 'success');
                } catch (clipboardErr) {
                    console.error('复制到剪贴板失败:', clipboardErr);
                    showToast('复制到剪贴板失败，正在下载图片...', 'info');
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const link = document.createElement('a');
                        link.download = `${props.title || 'notebook'}-选中部分.png`;
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

        const captureAll = async () => {
            const element = document.querySelector('.notebook-container');
            if (!element) {
                showToast('未找到截图区域', 'error');
                return;
            }

            try {
                window.focus();
                document.body.focus();

                const result = await snapdom(element, {
                    backgroundColor: '#f5f5f5',
                    scale: 1,
                    cache: 'auto'
                });

                const blob = await result.toBlob({ type: 'png' });

                window.focus();

                try {
                    await navigator.clipboard.write([
                        new ClipboardItem({ 'image/png': blob })
                    ]);
                    showToast('全页截图已复制到剪贴板', 'success');
                } catch (err) {
                    console.error('复制到剪贴板失败:', err);
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

        // -----------------------------------------------------------------------------
        // 5. 生命周期钩子
        // -----------------------------------------------------------------------------
        onMounted(() => {
            checkScreenWidth();
            window.addEventListener('resize', checkScreenWidth);
        });

        onUnmounted(() => {
            window.removeEventListener('resize', checkScreenWidth);
        });

        // -----------------------------------------------------------------------------
        // 6. 暴露给模板
        // -----------------------------------------------------------------------------
        return {
            tocItems,
            selectedCount,
            isSelected,
            toggleSelection,
            selectAll,
            clearSelection,
            scrollToSection,
            captureScreenshot,
            captureAll,
            menuExpanded,
            toggleMenu,
            isNarrow
        };
    },

    // -----------------------------------------------------------------------------
    // 7. 模板
    // -----------------------------------------------------------------------------
    template: `
        <nav class="toc-float-menu" :class="{ expanded: menuExpanded }" v-if="tocItems.length > 0">
            <div class="menu-wide">
                <div class="menu-header">
                    <span>📑 目录</span>
                    <button v-if="isNarrow" class="collapse-btn" @click="toggleMenu" title="收起">✕</button>
                </div>
                <ul class="menu-list">
                    <li v-for="(item, index) in tocItems" :key="index"
                        class="menu-item"
                        :class="{ selected: isSelected(item.index) }"
                        @click="scrollToSection(item.index)">
                        <input type="checkbox" :checked="isSelected(item.index)"
                               @click.stop="toggleSelection(item.index)">
                        <span class="menu-title">{{ item.title }}</span>
                    </li>
                </ul>
                <div class="menu-footer">
                    <button @click="selectAll">全选</button>
                    <button @click="clearSelection">清空</button>
                    <button @click="captureScreenshot" :disabled="selectedCount === 0">截图选中</button>
                    <button @click="captureAll" class="full-btn">📋 全页</button>
                </div>
            </div>

            <div class="menu-narrow">
                <div class="collapsed-header" @click="toggleMenu" title="展开目录">📑</div>
                <ul class="collapsed-list">
                    <li v-for="(item, index) in tocItems" :key="index"
                        class="collapsed-item"
                        :class="{ selected: isSelected(item.index) }"
                        @click="scrollToSection(item.index)"
                        :title="item.title">
                        {{ item.title.charAt(0) }}
                    </li>
                </ul>
            </div>
        </nav>
    `
};

// =============================================================================
// 第四部分：Toast 组件 - 提示消息组件
// =============================================================================

const Toast = {
    name: 'Toast',
    setup() {
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

        if (typeof window !== 'undefined') {
            window.showToast = showToast;
        }

        return {
            toastMessage,
            toastType
        };
    },
    template: `
        <div class="toast-container" v-if="toastMessage">
            <div class="toast" :class="toastType">{{ toastMessage }}</div>
        </div>
    `
};

// =============================================================================
// 第五部分：createNotebookApp - 创建 Notebook 应用
// =============================================================================

function createNotebookApp() {
    const FtTableComponent = typeof window !== 'undefined' ? window.FtTable : null;

    return createApp({
        components: {
            CellRenderer,
            ColorPicker,
            TocMenu,
            Toast,
            FtTable: FtTableComponent
        },

        setup() {
            // -----------------------------------------------------------------------------
            // 1. 配置与状态
            // -----------------------------------------------------------------------------
            const config = window.notebookConfig || {
                title: '未命名 Notebook',
                createdAt: new Date().toLocaleString(),
                children: []
            };

            const title = ref(config.title);
            const createdAt = ref(config.createdAt);
            const cells = ref(config.children || config.cells || []);
            const isScreenshotMode = ref(false);

            // -----------------------------------------------------------------------------
            // 2. 配色方案配置
            // -----------------------------------------------------------------------------
            const defaultPalettes = {
                global: 'warmToCool',
                typeToGroup: {
                    line: 'chart',
                    bar: 'chart',
                    area: 'chart',
                    scatter: 'chart',
                    radar: 'chart',
                    pie: 'pie',
                    doughnut: 'pie',
                    funnel: 'pie',
                    gauge: 'pie'
                },
                groups: {
                    chart: 'warmToCool',
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
            };

            if (!window.colorPalettes || !window.colorPalettes.groups) {
                window.colorPalettes = Vue.reactive(defaultPalettes);
            }
            const colorPalettes = window.colorPalettes;

            // -----------------------------------------------------------------------------
            // 3. Toast 方法（供内部使用）
            // -----------------------------------------------------------------------------
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

            // -----------------------------------------------------------------------------
            // 4. 暴露给模板
            // -----------------------------------------------------------------------------
            return {
                title,
                createdAt,
                cells,
                isScreenshotMode
            };
        }
    });
}

// =============================================================================
// 第六部分：导出
// =============================================================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CellRenderer, ColorPicker, TocMenu, Toast, createNotebookApp };
}
