/**
 * AccountAnalyzer - 账户分析工具类
 * 
 * 设计原则：
 * 1. 初始化传入净值数据
 * 2. 基准通过函数接口传入，支持切换
 * 3. 统计区间：业绩基准日 = 区间前一交易日
 * 4. 输出结构化数据，ECharts 配置由外部构建
 */

class AccountAnalyzer {
    /**
     * @param {Array} dailyAssets - 每日资产数据 [{date: '2024-01-01', assets: 100000}, ...]
     */
    constructor(dailyAssets) {
        this.dailyAssets = dailyAssets || [];
        this.benchmarkData = null;
        this._alignedBenchmark = null;
    }

    // ==================== 基准管理 ====================

    /**
     * 设置基准数据
     * @param {Array} benchmarkData - 基准数据 [{date: '2024-01-01', close: 3500}, ...]
     * @returns {AccountAnalyzer} this - 支持链式调用
     */
    setBenchmark(benchmarkData) {
        this.benchmarkData = benchmarkData;
        this._alignBenchmark();
        return this;
    }

    /**
     * 清除基准数据
     * @returns {AccountAnalyzer} this
     */
    clearBenchmark() {
        this.benchmarkData = null;
        this._alignedBenchmark = null;
        return this;
    }

    /**
     * 是否有基准数据
     * @returns {boolean}
     */
    hasBenchmark() {
        return this.benchmarkData !== null && this._alignedBenchmark !== null;
    }

    /**
     * 对齐基准数据到资产日期
     * @private
     */
    _alignBenchmark() {
        if (!this.benchmarkData || this.dailyAssets.length === 0) {
            this._alignedBenchmark = null;
            return;
        }

        const benchmarkMap = {};
        this.benchmarkData.forEach(item => {
            benchmarkMap[item.date] = parseFloat(item.close);
        });

        const assetDates = this.dailyAssets.map(item => item.date);
        const aligned = [];
        let lastValue = null;

        for (const date of assetDates) {
            if (benchmarkMap[date] !== undefined && benchmarkMap[date] !== 0) {
                lastValue = benchmarkMap[date];
            }
            aligned.push(lastValue);
        }

        this._alignedBenchmark = aligned;
    }

    // ==================== 时间区间 ====================

    /**
     * 获取时间区间索引
     * @param {string|Object} rangeType - 区间类型：'all', '1m', '3m', '6m', '1y', '2y', 'ytd' 或 {start, end}
     * @returns {Object} {startIndex, endIndex, baseIndex, startDate, endDate, baseDate}
     */
    getTimeRange(rangeType = 'all') {
        if (this.dailyAssets.length === 0) {
            return null;
        }

        const dates = this.dailyAssets.map(item => new Date(item.date));
        let startIndex = 0;
        let endIndex = dates.length - 1;

        if (rangeType === 'all') {
            startIndex = 0;
        } else if (typeof rangeType === 'object' && rangeType.start && rangeType.end) {
            startIndex = this._findDateIndex(dates, new Date(rangeType.start));
            endIndex = this._findDateIndex(dates, new Date(rangeType.end), true);
        } else {
            startIndex = this._calcStartIndexByRange(rangeType, dates);
        }

        if (startIndex < 0) startIndex = 0;
        if (endIndex >= dates.length) endIndex = dates.length - 1;
        if (startIndex > endIndex) startIndex = endIndex;

        const baseIndex = startIndex > 0 ? startIndex - 1 : 0;

        return {
            startIndex,
            endIndex,
            baseIndex,
            startDate: this.dailyAssets[startIndex].date,
            endDate: this.dailyAssets[endIndex].date,
            baseDate: this.dailyAssets[baseIndex].date
        };
    }

    /**
     * 根据区间类型计算起始索引
     * @private
     */
    _calcStartIndexByRange(rangeType, dates) {
        const today = dates[dates.length - 1];
        let targetDate;

        switch (rangeType) {
            case '1m':
                targetDate = new Date(today);
                targetDate.setMonth(targetDate.getMonth() - 1);
                break;
            case '3m':
                targetDate = new Date(today);
                targetDate.setMonth(targetDate.getMonth() - 3);
                break;
            case '6m':
                targetDate = new Date(today);
                targetDate.setMonth(targetDate.getMonth() - 6);
                break;
            case '1y':
                targetDate = new Date(today);
                targetDate.setFullYear(targetDate.getFullYear() - 1);
                break;
            case '2y':
                targetDate = new Date(today);
                targetDate.setFullYear(targetDate.getFullYear() - 2);
                break;
            case 'ytd':
                targetDate = new Date(today.getFullYear(), 0, 1);
                break;
            default:
                return 0;
        }

        return this._findDateIndex(dates, targetDate);
    }

    /**
     * 查找日期索引
     * @private
     */
    _findDateIndex(dates, targetDate, findLast = false) {
        if (findLast) {
            for (let i = dates.length - 1; i >= 0; i--) {
                if (dates[i] <= targetDate) return i;
            }
            return dates.length - 1;
        } else {
            for (let i = 0; i < dates.length; i++) {
                if (dates[i] >= targetDate) return i;
            }
            return 0;
        }
    }

    // ==================== 核心计算方法 ====================

    /**
     * 计算累计收益率序列
     * @param {Object} timeRange - 时间区间对象
     * @returns {Object} {dates, strategy, benchmark}
     */
    calcReturns(timeRange) {
        if (!timeRange) timeRange = this.getTimeRange('all');
        const { startIndex, endIndex, baseIndex } = timeRange;

        const dates = [];
        const strategy = [];
        const assets = this.dailyAssets.map(item => parseFloat(item.assets));
        const baseValue = assets[baseIndex];

        for (let i = startIndex; i <= endIndex; i++) {
            dates.push(this.dailyAssets[i].date);
            strategy.push(baseValue !== 0 ? ((assets[i] - baseValue) / baseValue) * 100 : 0);
        }

        const result = { dates, strategy };

        if (this.hasBenchmark()) {
            const benchmarkBase = this._alignedBenchmark[baseIndex];
            const benchmark = [];
            for (let i = startIndex; i <= endIndex; i++) {
                const value = this._alignedBenchmark[i];
                if (value !== null && benchmarkBase !== null) {
                    benchmark.push(((value - benchmarkBase) / benchmarkBase) * 100);
                } else {
                    benchmark.push(null);
                }
            }
            result.benchmark = benchmark;
        } else {
            result.benchmark = null;
        }

        return result;
    }

    /**
     * 计算回撤序列
     * @param {Object} timeRange - 时间区间对象
     * @returns {Object} {strategy, benchmark, excess}
     */
    calcDrawdowns(timeRange) {
        if (!timeRange) timeRange = this.getTimeRange('all');
        const { startIndex, endIndex } = timeRange;

        const assets = this.dailyAssets.map(item => parseFloat(item.assets));
        
        const strategy = [];
        let peak = assets[startIndex];
        for (let i = startIndex; i <= endIndex; i++) {
            if (assets[i] > peak) peak = assets[i];
            strategy.push(peak !== 0 ? ((assets[i] - peak) / peak) * 100 : 0);
        }

        const result = { strategy };

        if (this.hasBenchmark()) {
            const benchmark = [];
            let benchmarkPeak = this._alignedBenchmark[startIndex];
            for (let i = startIndex; i <= endIndex; i++) {
                const value = this._alignedBenchmark[i];
                if (value !== null) {
                    if (value > benchmarkPeak) benchmarkPeak = value;
                    benchmark.push(((value - benchmarkPeak) / benchmarkPeak) * 100);
                } else {
                    benchmark.push(null);
                }
            }
            result.benchmark = benchmark;
        } else {
            result.benchmark = null;
        }

        result.excess = null;

        return result;
    }

    /**
     * 计算超额收益序列
     * @param {Object} timeRange - 时间区间对象
     * @returns {Object} {returns, drawdowns} 或 null
     */
    calcExcess(timeRange) {
        if (!this.hasBenchmark()) return null;
        if (!timeRange) timeRange = this.getTimeRange('all');

        const returnsData = this.calcReturns(timeRange);
        const excessReturns = [];
        
        for (let i = 0; i < returnsData.strategy.length; i++) {
            if (returnsData.benchmark[i] !== null) {
                excessReturns.push(returnsData.strategy[i] - returnsData.benchmark[i]);
            } else {
                excessReturns.push(null);
            }
        }

        const drawdowns = [];
        let maxValue = excessReturns[0] || 0;
        for (let i = 0; i < excessReturns.length; i++) {
            const value = excessReturns[i];
            if (value !== null) {
                if (value > maxValue) maxValue = value;
                drawdowns.push(value - maxValue);
            } else {
                drawdowns.push(null);
            }
        }

        return { returns: excessReturns, drawdowns };
    }

    /**
     * 计算区间收益率
     * @param {Object} timeRange - 时间区间对象
     * @returns {number}
     */
    calcReturnRate(timeRange) {
        if (!timeRange) timeRange = this.getTimeRange('all');
        const { endIndex, baseIndex } = timeRange;

        const assets = this.dailyAssets.map(item => parseFloat(item.assets));
        const baseValue = assets[baseIndex];
        const endValue = assets[endIndex];

        return baseValue !== 0 ? (endValue - baseValue) / baseValue : 0;
    }

    /**
     * 计算年化收益率
     * @param {Object} timeRange - 时间区间对象
     * @returns {number}
     */
    calcAnnualizedReturn(timeRange) {
        if (!timeRange) timeRange = this.getTimeRange('all');
        const { startDate, endDate } = timeRange;

        const totalReturn = this.calcReturnRate(timeRange);
        const days = (new Date(endDate) - new Date(startDate)) / (1000 * 60 * 60 * 24);

        if (days === 0 || totalReturn <= -1) return 0;
        return Math.pow(1 + totalReturn, 365 / days) - 1;
    }

    /**
     * 计算年化波动率
     * @param {Object} timeRange - 时间区间对象
     * @returns {number}
     */
    calcVolatility(timeRange) {
        if (!timeRange) timeRange = this.getTimeRange('all');
        const { startIndex, endIndex } = timeRange;

        const assets = this.dailyAssets.map(item => parseFloat(item.assets));
        const returns = [];

        for (let i = startIndex + 1; i <= endIndex; i++) {
            if (assets[i - 1] !== 0) {
                returns.push((assets[i] - assets[i - 1]) / assets[i - 1]);
            }
        }

        if (returns.length < 2) return 0;

        const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
        const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length;
        return Math.sqrt(variance) * Math.sqrt(252);
    }

    /**
     * 计算最大回撤
     * @param {Object} timeRange - 时间区间对象
     * @returns {Object} {drawdown, startDate, endDate}
     */
    calcMaxDrawdown(timeRange) {
        if (!timeRange) timeRange = this.getTimeRange('all');
        const { startIndex, endIndex } = timeRange;

        const assets = this.dailyAssets.map(item => parseFloat(item.assets));
        let peak = assets[startIndex];
        let maxDrawdown = 0;
        let peakDate = this.dailyAssets[startIndex].date;
        let startDate = peakDate;
        let endDate = peakDate;

        for (let i = startIndex; i <= endIndex; i++) {
            const value = assets[i];
            const date = this.dailyAssets[i].date;

            if (value > peak) {
                peak = value;
                peakDate = date;
            }

            const drawdown = (peak - value) / peak;
            if (drawdown > maxDrawdown) {
                maxDrawdown = drawdown;
                startDate = peakDate;
                endDate = date;
            }
        }

        return { drawdown: maxDrawdown, startDate, endDate };
    }

    /**
     * 计算夏普比率
     * @param {Object} timeRange - 时间区间对象
     * @param {number} riskFreeRate - 无风险利率
     * @returns {number}
     */
    calcSharpeRatio(timeRange, riskFreeRate = 0.02) {
        const annualizedReturn = this.calcAnnualizedReturn(timeRange);
        const volatility = this.calcVolatility(timeRange);
        return volatility !== 0 ? (annualizedReturn - riskFreeRate) / volatility : 0;
    }

    /**
     * 计算索提诺比率
     * @param {Object} timeRange - 时间区间对象
     * @param {number} riskFreeRate - 无风险利率
     * @returns {number}
     */
    calcSortinoRatio(timeRange, riskFreeRate = 0.02) {
        if (!timeRange) timeRange = this.getTimeRange('all');
        const { startIndex, endIndex } = timeRange;

        const assets = this.dailyAssets.map(item => parseFloat(item.assets));
        const returns = [];

        for (let i = startIndex + 1; i <= endIndex; i++) {
            if (assets[i - 1] !== 0) {
                returns.push((assets[i] - assets[i - 1]) / assets[i - 1]);
            }
        }

        if (returns.length < 2) return 0;

        const negativeReturns = returns.filter(r => r < 0);
        if (negativeReturns.length === 0) return Infinity;

        const downsideVariance = negativeReturns.reduce((sum, r) => sum + Math.pow(r, 2), 0) / returns.length;
        const downsideDeviation = Math.sqrt(downsideVariance) * Math.sqrt(252);

        const annualizedReturn = this.calcAnnualizedReturn(timeRange);
        return downsideDeviation !== 0 ? (annualizedReturn - riskFreeRate) / downsideDeviation : Infinity;
    }

    /**
     * 计算 VaR
     * @param {Object} timeRange - 时间区间对象
     * @param {number} confidence - 置信水平
     * @returns {number}
     */
    calcVar(timeRange, confidence = 0.95) {
        if (!timeRange) timeRange = this.getTimeRange('all');
        const { startIndex, endIndex } = timeRange;

        const assets = this.dailyAssets.map(item => parseFloat(item.assets));
        const returns = [];

        for (let i = startIndex + 1; i <= endIndex; i++) {
            if (assets[i - 1] !== 0) {
                returns.push((assets[i] - assets[i - 1]) / assets[i - 1]);
            }
        }

        if (returns.length < 2) return 0;

        const sorted = [...returns].sort((a, b) => a - b);
        const index = Math.floor((1 - confidence) * sorted.length);
        return -sorted[index] || 0;
    }

    /**
     * 计算 CVaR
     * @param {Object} timeRange - 时间区间对象
     * @param {number} confidence - 置信水平
     * @returns {number}
     */
    calcCvar(timeRange, confidence = 0.95) {
        if (!timeRange) timeRange = this.getTimeRange('all');
        const { startIndex, endIndex } = timeRange;

        const assets = this.dailyAssets.map(item => parseFloat(item.assets));
        const returns = [];

        for (let i = startIndex + 1; i <= endIndex; i++) {
            if (assets[i - 1] !== 0) {
                returns.push((assets[i] - assets[i - 1]) / assets[i - 1]);
            }
        }

        if (returns.length < 2) return 0;

        const sorted = [...returns].sort((a, b) => a - b);
        const index = Math.max(1, Math.floor((1 - confidence) * sorted.length));
        const tail = sorted.slice(0, index);
        return -tail.reduce((a, b) => a + b, 0) / tail.length;
    }

    /**
     * 计算 Ulcer Index
     * @param {Object} timeRange - 时间区间对象
     * @returns {number}
     */
    calcUlcerIndex(timeRange) {
        if (!timeRange) timeRange = this.getTimeRange('all');
        const { startIndex, endIndex } = timeRange;

        const assets = this.dailyAssets.map(item => parseFloat(item.assets));
        let peak = assets[startIndex];
        const squaredDrawdowns = [];

        for (let i = startIndex; i <= endIndex; i++) {
            if (assets[i] > peak) peak = assets[i];
            const drawdownPct = ((peak - assets[i]) / peak) * 100;
            squaredDrawdowns.push(Math.pow(drawdownPct, 2));
        }

        return Math.sqrt(squaredDrawdowns.reduce((a, b) => a + b, 0) / squaredDrawdowns.length);
    }

    /**
     * 计算 UPI
     * @param {Object} timeRange - 时间区间对象
     * @param {number} riskFreeRate - 无风险利率
     * @returns {number}
     */
    calcUpi(timeRange, riskFreeRate = 0.02) {
        const annualizedReturn = this.calcAnnualizedReturn(timeRange);
        const ulcerIndex = this.calcUlcerIndex(timeRange);
        return ulcerIndex !== 0 ? (annualizedReturn - riskFreeRate) / (ulcerIndex / 100) : 0;
    }

    // ==================== 基准相关计算 ====================

    /**
     * 计算基准区间收益率
     * @param {Object} timeRange - 时间区间对象
     * @returns {number|null}
     */
    calcBenchmarkReturnRate(timeRange) {
        if (!this.hasBenchmark()) return null;
        if (!timeRange) timeRange = this.getTimeRange('all');
        const { endIndex, baseIndex } = timeRange;

        const baseValue = this._alignedBenchmark[baseIndex];
        const endValue = this._alignedBenchmark[endIndex];

        if (baseValue === null || endValue === null || baseValue === 0) return null;
        return (endValue - baseValue) / baseValue;
    }

    /**
     * 计算基准最大回撤
     * @param {Object} timeRange - 时间区间对象
     * @returns {Object|null} {drawdown, startDate, endDate}
     */
    calcBenchmarkMaxDrawdown(timeRange) {
        if (!this.hasBenchmark()) return null;
        if (!timeRange) timeRange = this.getTimeRange('all');
        const { startIndex, endIndex } = timeRange;

        let peak = this._alignedBenchmark[startIndex];
        let maxDrawdown = 0;
        let peakDate = this.dailyAssets[startIndex].date;
        let startDate = peakDate;
        let endDate = peakDate;

        for (let i = startIndex; i <= endIndex; i++) {
            const value = this._alignedBenchmark[i];
            const date = this.dailyAssets[i].date;

            if (value === null) continue;

            if (value > peak) {
                peak = value;
                peakDate = date;
            }

            const drawdown = (peak - value) / peak;
            if (drawdown > maxDrawdown) {
                maxDrawdown = drawdown;
                startDate = peakDate;
                endDate = date;
            }
        }

        return { drawdown: maxDrawdown, startDate, endDate };
    }

    // ==================== 输出方法 ====================

    /**
     * 获取收益数据
     * @param {string|Object} rangeType - 区间类型
     * @returns {Object} {dates, strategy, benchmark}
     */
    getReturns(rangeType = 'all') {
        const timeRange = this.getTimeRange(rangeType);
        return this.calcReturns(timeRange);
    }

    /**
     * 获取回撤数据
     * @param {string|Object} rangeType - 区间类型
     * @returns {Object} {strategy, benchmark, excess}
     */
    getDrawdowns(rangeType = 'all') {
        const timeRange = this.getTimeRange(rangeType);
        const drawdowns = this.calcDrawdowns(timeRange);
        
        if (this.hasBenchmark()) {
            const excess = this.calcExcess(timeRange);
            drawdowns.excess = excess ? excess.drawdowns : null;
        }
        
        return drawdowns;
    }

    /**
     * 获取超额收益数据
     * @param {string|Object} rangeType - 区间类型
     * @returns {Object|null} {returns, drawdowns}
     */
    getExcess(rangeType = 'all') {
        if (!this.hasBenchmark()) return null;
        const timeRange = this.getTimeRange(rangeType);
        return this.calcExcess(timeRange);
    }

    /**
     * 获取区间统计
     * @param {string|Object} rangeType - 区间类型
     * @returns {Object}
     */
    getStats(rangeType = 'all') {
        const timeRange = this.getTimeRange(rangeType);
        if (!timeRange) return null;

        const maxDrawdown = this.calcMaxDrawdown(timeRange);

        const stats = {
            startDate: timeRange.startDate,
            endDate: timeRange.endDate,
            baseDate: timeRange.baseDate,
            periodReturn: this.calcReturnRate(timeRange),
            annualizedReturn: this.calcAnnualizedReturn(timeRange),
            volatility: this.calcVolatility(timeRange),
            maxDrawdown: maxDrawdown.drawdown,
            maxDrawdownStart: maxDrawdown.startDate,
            maxDrawdownEnd: maxDrawdown.endDate,
            sharpeRatio: this.calcSharpeRatio(timeRange),
            sortinoRatio: this.calcSortinoRatio(timeRange),
            var95: this.calcVar(timeRange, 0.95),
            cvar95: this.calcCvar(timeRange, 0.95),
            ulcerIndex: this.calcUlcerIndex(timeRange),
            upi: this.calcUpi(timeRange)
        };

        if (this.hasBenchmark()) {
            const benchmarkMaxDrawdown = this.calcBenchmarkMaxDrawdown(timeRange);
            stats.benchmarkReturn = this.calcBenchmarkReturnRate(timeRange);
            stats.benchmarkMaxDrawdown = benchmarkMaxDrawdown ? benchmarkMaxDrawdown.drawdown : null;
            stats.relativeReturn = stats.periodReturn - stats.benchmarkReturn;
        } else {
            stats.benchmarkReturn = null;
            stats.benchmarkMaxDrawdown = null;
            stats.relativeReturn = null;
        }

        return stats;
    }

    /**
     * 获取完整结果
     * @param {string|Object} rangeType - 区间类型
     * @returns {Object}
     */
    getResult(rangeType = 'all') {
        const timeRange = this.getTimeRange(rangeType);
        if (!timeRange) return null;

        return {
            range: timeRange,
            returns: this.calcReturns(timeRange),
            drawdowns: this.getDrawdowns(rangeType),
            excess: this.calcExcess(timeRange),
            stats: this.getStats(rangeType),
            hasBenchmark: this.hasBenchmark()
        };
    }
}

// 全局暴露
if (typeof window !== 'undefined') {
    window.AccountAnalyzer = AccountAnalyzer;
}

// ES Module 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AccountAnalyzer;
}
