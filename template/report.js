class AssetAnalyzer {
    constructor(assetsData) {
        this.assetsData = assetsData;
        this.processData();
    }
    
    addbenchmark(benchmarkData) {
        //添加基准数据，格式和assetsData相同，日期会比assetsData多
        this.benchmarkData = benchmarkData;
    }
    processData() {
        // 确保数据按日期排序
        this.assetsData.sort((a, b) => new Date(a.日期) - new Date(b.日期));
        
        this.dates = this.assetsData.map(item => new Date(item.日期));
        this.assets = this.assetsData.map(item => item.资产);
        
        // 计算累计收益率数组（百分比形式）
        this.cumulativeReturns = [];
        if (this.assets.length > 0) {
            const initial = this.assets[0];
            this.cumulativeReturns = this.assets.map(asset => 
                ((asset - initial) / initial * 100).toFixed(2)
            );
        }
    }

    // 新增：获取累计收益率数据（用于ECharts）
    getCumulativeReturnSeries() {
        return this.dates.map((date, index) => ({
            日期: date,
            策略收益: parseFloat(this.cumulativeReturns[index])
        }));
    }

    // 获取回撤曲线数据
    getDrawdownSeries() {
        return this.dates.map((date, index) => ({
            日期: date,
            策略回撤: this.drawdowns[index]
        }));
    }

    // 获取时间区间（与Python一致，考虑交易日历）
    _get_start_end_date(time_interval) {
        if (!time_interval) {
            return [this.dates[0], this.dates[this.dates.length-1]];
        }
        
        const endDate = this.dates[this.dates.length-1];
        let startDate = new Date(endDate);
        
        if (time_interval.endsWith('y')) {
            startDate.setFullYear(startDate.getFullYear() - parseInt(time_interval));
        } else if (time_interval.endsWith('m')) {
            startDate.setMonth(startDate.getMonth() - parseInt(time_interval));
        }
        
        // 找到第一个大于等于计算日期的交易日
        const findNearestTradeDate = (targetDate) => {
            for (let i = 0; i < this.dates.length; i++) {
                if (this.dates[i] >= targetDate) {
                    return this.dates[i];
                }
            }
            return this.dates[this.dates.length-1];
        };
        
        // 确保开始日期是交易日且不小于最早日期
        startDate = findNearestTradeDate(startDate);
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




}
