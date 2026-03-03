/**
 * Notebook Vue3 - Vue 3 组合式 API 版本的 Notebook 应用逻辑
 * 从 notebook.html 分离出来的 JavaScript
 */

const { createApp, ref, computed, onMounted, nextTick } = Vue;

// ========== Cell 渲染组件（组合式 API）==========
const CellRenderer = {
    name: 'CellRenderer',
    props: {
        cell: { type: Object, required: true },
        cellId: { type: [String, Number], required: true },
        level: { type: Number, default: 0 }
    },
    setup(props) {
        const chartRef = ref(null);
        let chartInstance = null;

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
            if (cell.options?.page) opts.page = cell.options.page;
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
                const option = buildChartOption(cell.type, chartType, content.data || content, cell.options);
                chartInstance.setOption(option);
            } else if (cell.type === 'pyecharts') {
                chartInstance = echarts.init(chartRef.value);
                chartInstance.setOption(content);
            }
        };

        // 构建图表配置
        const buildChartOption = (type, chartType, data, options = {}) => {
            const baseOption = {
                tooltip: { trigger: 'axis' },
                grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true }
            };

            if (type === 'chart') {
                const isLine = chartType === 'line';
                const isBar = chartType === 'bar';
                const isArea = chartType === 'area';

                return {
                    ...baseOption,
                    xAxis: {
                        type: 'category',
                        data: data.dates || data.categories || [],
                        boundaryGap: isBar
                    },
                    yAxis: { type: 'value' },
                    series: (data.series || []).map(s => ({
                        name: s.name,
                        type: isArea ? 'line' : chartType,
                        data: s.data,
                        areaStyle: isArea ? { opacity: 0.3 } : undefined,
                        smooth: isLine || isArea
                    }))
                };
            } else if (type === 'heatmap') {
                const years = Object.keys(content);
                const months = Object.keys(content[years[0]]);
                const data = [];
                years.forEach((year, yIndex) => {
                    months.forEach((month, mIndex) => {
                        data.push([mIndex, yIndex, content[year][month]]);
                    });
                });

                return {
                    tooltip: { position: 'top' },
                    grid: { height: '50%', top: '10%' },
                    xAxis: { type: 'category', data: months },
                    yAxis: { type: 'category', data: years },
                    visualMap: {
                        min: -0.1,
                        max: 0.1,
                        calculable: true,
                        orient: 'horizontal',
                        left: 'center',
                        bottom: '15%'
                    },
                    series: [{
                        name: '收益',
                        type: 'heatmap',
                        data: data,
                        label: { show: true }
                    }]
                };
            }

            return baseOption;
        };

        onMounted(() => {
            if (['chart', 'heatmap', 'pyecharts'].includes(props.cell.type)) {
                nextTick(() => initChart());
            }
        });

        return {
            chartRef,
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
             :class="{ 'nested-section': level > 0 }"
             :id="'section-' + cellId">
            <div v-if="cell.title" class="section-title">{{ cell.title }}</div>
            <div class="section-content">
                <cell-renderer 
                    v-for="(subCell, idx) in cell.content" 
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
                <vue-table 
                    :id="'table-' + cellId"
                    :data="cell.content"
                    :cols="getTableCols(cell)"
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
            
            <!-- 图表 -->
            <div v-else-if="['chart', 'heatmap', 'pyecharts'].includes(cell.type)" 
                 class="cell-chart">
                <h3 v-if="cell.title">{{ cell.title }}</h3>
                <div ref="chartRef" 
                     class="chart-container"
                     :style="{'--height': (cell.options?.height || 400) + 'px'}">
                </div>
            </div>
            
            <!-- HTML -->
            <div v-else-if="cell.type === 'html'" class="html-block">
                <div class="html-block-inner" v-html="cell.content"></div>
            </div>
            
            <!-- 分隔线 -->
            <div v-else-if="cell.type === 'divider'" class="cell-divider"></div>
            
            <!-- 可折叠 -->
            <div v-else-if="cell.type === 'collapsible'" class="cell-collapsible">
                <button class="collapse-toggle" @click="cell.options.collapsed = !cell.options.collapsed">
                    <span>{{ cell.title }}</span>
                    <span>{{ cell.options?.collapsed ? '▶' : '▼' }}</span>
                </button>
                <div v-show="!cell.options?.collapsed" class="collapse-content">
                    <cell-renderer 
                        v-for="(subCell, idx) in cell.content" 
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
    return createApp({
        components: {
            CellRenderer,
            VueTable
        },

        setup() {
            // 从全局变量获取配置（由后端渲染时注入）
            const config = window.notebookConfig || {
                title: '未命名 Notebook',
                createdAt: new Date().toLocaleString(),
                cells: []
            };

            const title = ref(config.title);
            const createdAt = ref(config.createdAt);
            const cells = ref(config.cells);
            const selectedIndices = ref(new Set());
            const isScreenshotMode = ref(false);

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

            // 截图功能
            const captureScreenshot = async () => {
                if (selectedIndices.value.size === 0) return;

                isScreenshotMode.value = true;
                await nextTick();

                try {
                    const element = document.querySelector('.notebook-container');
                    const canvas = await snapdom(element, {
                        scale: 2,
                        backgroundColor: '#f5f5f5'
                    });

                    const link = document.createElement('a');
                    link.download = `${title.value || 'notebook'}.png`;
                    link.href = canvas.toDataURL();
                    link.click();
                } catch (err) {
                    console.error('截图失败:', err);
                    alert('截图失败: ' + err.message);
                } finally {
                    isScreenshotMode.value = false;
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
                isSelected,
                toggleSelection,
                selectAll,
                clearSelection,
                scrollToSection,
                captureScreenshot
            };
        }
    });
}

// 导出（如果支持模块系统）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CellRenderer, createNotebookApp };
}
