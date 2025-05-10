class AssetAnalyzer {
    constructor(netValueData) {
        this.netValueData = netValueData;
        this.processData();
    }

    processData() {
        // 确保数据按日期排序
        this.netValueData.sort((a, b) => new Date(a.日期) - new Date(b.日期));
        
        this.dates = this.netValueData.map(item => new Date(item.日期));
        this.assets = this.netValueData.map(item => item.资产);
    }

    // 获取时间区间（与Python一致）
    _get_start_end_date(time_interval) {
        if (!time_interval) {
            return [this.dates[0], this.dates[this.dates.length-1]];
        }
        
        // 实现与Python相同的时间区间逻辑
        const endDate = this.dates[this.dates.length-1];
        let startDate = new Date(endDate);
        
        if (time_interval.endsWith('y')) {
            startDate.setFullYear(startDate.getFullYear() - parseInt(time_interval));
        } else if (time_interval.endsWith('m')) {
            startDate.setMonth(startDate.getMonth() - parseInt(time_interval));
        }
        
        // 确保开始日期不小于最早日期
        startDate = startDate < this.dates[0] ? this.dates[0] : startDate;
        return [startDate, endDate];
    }

    // 计算收益率（支持时间区间）
    calculate_return_rate(time_interval=null) {
        if (!this.assets.length) return 0;
        const [startDate, endDate] = this._get_start_end_date(time_interval);
        
        const startIndex = this.dates.findIndex(d => d >= startDate);
        const endIndex = this.dates.findIndex(d => d >= endDate);
        
        if (startIndex === -1 || endIndex === -1) return 0;
        
        const initial = this.assets[startIndex];
        const current = this.assets[endIndex];
        return (current - initial) / initial;
    }

    // 计算年化收益率（支持时间区间）
    calculate_annualized_return(time_interval=null) {
        if (this.assets.length < 2) return 0;
        const [startDate, endDate] = this._get_start_end_date(time_interval);
        
        const days = (endDate - startDate) / (1000*60*60*24);
        const totalReturn = this.calculate_return_rate(time_interval);
        return Math.pow(1 + totalReturn, 365/days) - 1;
    }

    // 计算波动率（支持时间区间）
    calculate_volatility(time_interval=null) {
        if (this.assets.length < 2) return 0;
        const [startDate, endDate] = this._get_start_end_date(time_interval);
        
        const startIndex = this.dates.findIndex(d => d >= startDate);
        const endIndex = this.dates.findIndex(d => d >= endDate);
        
        if (startIndex === -1 || endIndex === -1) return 0;
        
        const returns = [];
        for (let i = startIndex+1; i <= endIndex; i++) {
            returns.push((this.assets[i] - this.assets[i-1]) / this.assets[i-1]);
        }
        
        const mean = returns.reduce((sum, r) => sum + r, 0) / returns.length;
        const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length;
        return Math.sqrt(variance) * Math.sqrt(252);
    }

    // 计算夏普比率（支持时间区间）
    calculate_sharpe_ratio(risk_free_rate=0.02, time_interval=null) {
        const annualized_return = this.calculate_annualized_return(time_interval);
        const volatility = this.calculate_volatility(time_interval);
        return (annualized_return - risk_free_rate) / volatility || 0;
    }


    // 获取回撤曲线数据
    getDrawdownSeries() {
        return this.dates.map((date, index) => ({
            日期: date,
            回撤: this.drawdowns[index]
        }));
    }

    // 获取峰值曲线数据
    getPeakSeries() {
        return this.dates.map((date, index) => ({
            日期: date,
            峰值: this.peakValues[index]
        }));
    }

}
