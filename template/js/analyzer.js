/**
 * Account Analyzer - 账户分析工具类
 * 与 Python 版本的 AccountAnalyzer 保持算法一致
 * 用于前端动态计算指标
 */

class AccountAnalyzer {
    /**
     * @param {Array} dailyAssets - 每日资产数据 [{date: '2024-01-01', assets: 100000}, ...]
     */
    constructor(dailyAssets) {
        this.dailyAssets = dailyAssets || [];
    }

    /**
     * 计算收益率
     * @param {Array} data - 资产数据，默认使用完整数据
     * @returns {number} 收益率
     */
    calc_return_rate(data = this.dailyAssets) {
        if (!data || data.length === 0) return 0;
        
        const startValue = parseFloat(data[0].assets);
        const endValue = parseFloat(data[data.length - 1].assets);
        
        if (startValue === 0) return 0;
        return (endValue - startValue) / startValue;
    }

    /**
     * 计算年化收益率
     * @param {Array} data - 资产数据
     * @returns {number} 年化收益率
     */
    calc_annualized_return(data = this.dailyAssets) {
        if (!data || data.length === 0) return 0;
        
        const totalReturn = this.calc_return_rate(data);
        const startDate = new Date(data[0].date);
        const endDate = new Date(data[data.length - 1].date);
        const days = (endDate - startDate) / (1000 * 60 * 60 * 24);
        
        if (days === 0) return 0;
        if (totalReturn <= -1) return 0;
        
        return Math.pow(1 + totalReturn, 365 / days) - 1;
    }

    /**
     * 计算年化波动率
     * @param {Array} data - 资产数据
     * @returns {number} 年化波动率
     */
    calc_volatility(data = this.dailyAssets) {
        if (!data || data.length < 2) return 0;
        
        const dailyReturns = this._calculateDailyReturns(data);
        const meanReturn = dailyReturns.reduce((a, b) => a + b, 0) / dailyReturns.length;
        const variance = dailyReturns.reduce((sum, r) => sum + Math.pow(r - meanReturn, 2), 0) / dailyReturns.length;
        const dailyVolatility = Math.sqrt(variance);
        
        return dailyVolatility * Math.sqrt(252);
    }

    /**
     * 计算最大回撤
     * @param {Array} data - 资产数据
     * @returns {Object} {drawdown: 回撤比例，startDate: 开始日期，endDate: 结束日期}
     */
    calc_max_drawdown(data = this.dailyAssets) {
        if (!data || data.length === 0) {
            return { drawdown: 0, startDate: null, endDate: null };
        }
        
        let peak = parseFloat(data[0].assets);
        let maxDrawdown = 0;
        let startDate = data[0].date;
        let endDate = data[0].date;
        let peakDate = data[0].date;
        
        for (let i = 0; i < data.length; i++) {
            const value = parseFloat(data[i].assets);
            const date = data[i].date;
            
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
        
        return {
            drawdown: maxDrawdown,
            startDate: startDate,
            endDate: endDate
        };
    }

    /**
     * 计算 VaR (Value at Risk)
     * @param {Array} data - 资产数据
     * @param {number} confidence - 置信水平，默认 0.95
     * @returns {number} VaR 值
     */
    calc_var(data = this.dailyAssets, confidence = 0.95) {
        if (!data || data.length < 2) return 0;
        
        const dailyReturns = this._calculate_daily_returns(data);
        const sortedReturns = [...dailyReturns].sort((a, b) => a - b);
        const index = Math.floor((1 - confidence) * sortedReturns.length);
        
        return -sortedReturns[index] || 0;
    }

    /**
     * 计算 CVaR (Conditional Value at Risk)
     * @param {Array} data - 资产数据
     * @param {number} confidence - 置信水平，默认 0.95
     * @returns {number} CVaR 值
     */
    calc_cvar(data = this.dailyAssets, confidence = 0.95) {
        if (!data || data.length < 2) return 0;
        
        const dailyReturns = this._calculate_daily_returns(data);
        const sortedReturns = [...dailyReturns].sort((a, b) => a - b);
        const index = Math.max(1, Math.floor((1 - confidence) * sortedReturns.length));
        const tailReturns = sortedReturns.slice(0, index);
        
        return -tailReturns.reduce((a, b) => a + b, 0) / tailReturns.length;
    }

    /**
     * 计算夏普比率
     * @param {Array} data - 资产数据
     * @param {number} riskFreeRate - 无风险利率，默认 0.02
     * @returns {number} 夏普比率
     */
    calc_sharpe_ratio(data = this.dailyAssets, riskFreeRate = 0.02) {
        const annualizedReturn = this.calc_annualized_return(data);
        const volatility = this.calc_volatility(data);
        
        if (volatility === 0) return 0;
        return (annualizedReturn - riskFreeRate) / volatility;
    }

    /**
     * 计算索提诺比率
     * @param {Array} data - 资产数据
     * @param {number} riskFreeRate - 无风险利率，默认 0.02
     * @returns {number} 索提诺比率
     */
    calc_sortino_ratio(data = this.dailyAssets, riskFreeRate = 0.02) {
        const annualizedReturn = this.calc_annualized_return(data);
        if (!data || data.length < 2) return 0;
        
        const dailyReturns = this._calculate_daily_returns(data);
        const negativeReturns = dailyReturns.filter(r => r < 0);
        
        if (negativeReturns.length === 0) return Infinity;
        
        const downsideVariance = negativeReturns.reduce((sum, r) => sum + Math.pow(r, 2), 0) / dailyReturns.length;
        const downsideDeviation = Math.sqrt(downsideVariance) * Math.sqrt(252);
        
        if (downsideDeviation === 0) return Infinity;
        return (annualizedReturn - riskFreeRate) / downsideDeviation;
    }

    /**
     * 计算 Ulcer Index
     * @param {Array} data - 资产数据
     * @returns {number} Ulcer Index
     */
    calc_ulcer_index(data = this.dailyAssets) {
        if (!data || data.length < 2) return 0;
        
        let peak = parseFloat(data[0].assets);
        const squaredDrawdowns = [];
        
        for (let item of data) {
            const value = parseFloat(item.assets);
            if (value > peak) {
                peak = value;
            }
            const drawdownPct = ((peak - value) / peak) * 100;
            squaredDrawdowns.push(Math.pow(drawdownPct, 2));
        }
        
        const sumSquared = squaredDrawdowns.reduce((a, b) => a + b, 0);
        return Math.sqrt(sumSquared / squaredDrawdowns.length);
    }

    /**
     * 计算 UPI (Ulcer Performance Index)
     * @param {Array} data - 资产数据
     * @param {number} riskFreeRate - 无风险利率，默认 0.02
     * @returns {number} UPI
     */
    calc_upi(data = this.dailyAssets, riskFreeRate = 0.02) {
        const annualizedReturn = this.calc_annualized_return(data);
        const ulcerIndex = this.calc_ulcer_index(data);
        
        if (ulcerIndex === 0) return 0;
        return (annualizedReturn - riskFreeRate) / (ulcerIndex / 100);
    }

    /**
     * 获取 ECharts 图表数据
     * @returns {Array} [{date: '2024-01-01', '策略收益': 0.15, '回撤': -0.08}, ...]
     */
    get_echarts_data() {
        if (!this.dailyAssets || this.dailyAssets.length === 0) return [];
        
        let peak = parseFloat(this.dailyAssets[0].assets);
        const startValue = peak;
        
        return this.dailyAssets.map(item => {
            const value = parseFloat(item.assets);
            const cumulativeReturn = (value - startValue) / startValue;
            
            if (value > peak) {
                peak = value;
            }
            const drawdown = (peak - value) / peak;
            
            return {
                date: item.date,
                '策略收益': cumulativeReturn * 100,
                '回撤': -drawdown * 100
            };
        });
    }

    /**
     * 计算日收益率序列
     * @private
     * @param {Array} data - 资产数据
     * @returns {Array} 日收益率数组
     */
    _calculate_daily_returns(data) {
        const returns = [];
        for (let i = 1; i < data.length; i++) {
            const prevValue = parseFloat(data[i - 1].assets);
            const currentValue = parseFloat(data[i].assets);
            returns.push((currentValue - prevValue) / prevValue);
        }
        return returns;
    }

    /**
     * 格式化百分比
     * @param {number} value - 数值
     * @param {number} decimals - 小数位数
     * @returns {string} 格式化后的百分比字符串
     */
    static formatPercent(value, decimals = 2) {
        return (value * 100).toFixed(decimals) + '%';
    }

    /**
     * 格式化数值
     * @param {number} value - 数值
     * @param {number} decimals - 小数位数
     * @returns {string} 格式化后的字符串
     */
    static formatNumber(value, decimals = 2) {
        return parseFloat(value).toFixed(decimals);
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
