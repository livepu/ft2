//js版本的分析类，最重要的是处理echarts的数据，涉及基准；
// 其他夏普之类的数据，按照输出形式格式需要。因为这里直接html的结果。
class AssetAnalyzer {
    constructor(assetsData) {
        this.assetsData = assetsData;
        this.benchmarkData = null; // 明确初始化为null
        this.processData();
    }


    addbenchmark(benchmarkData) {
        // 添加基准数据，格式和assetsData相同，日期会比assetsData多
        this.benchmarkData = benchmarkData;
        this.processData(); // 重新处理数据
    }

    processData() {
        // 1. 处理资产数据
        this.assetsData.sort((a, b) => new Date(a.日期) - new Date(b.日期));
        this.dates = this.assetsData.map(item => new Date(item.日期));
        this.assets = this.assetsData.map(item => item.资产);

        // 2. 计算策略累计收益率（百分比）
        this.strategyReturns = [];
        if (this.assets.length > 0) {
            const initial = this.assets[0];
            this.strategyReturns = this.assets.map(asset => 
                ((asset - initial) / initial * 100).toFixed(2)
            );
        }

        // 3. 计算策略回撤（百分比）
        this.strategyDrawdowns = [];
        let peak = this.assets[0];
        for (let i = 0; i < this.assets.length; i++) {
            if (this.assets[i] > peak) peak = this.assets[i];
            this.strategyDrawdowns.push(((peak - this.assets[i]) / peak * 100).toFixed(2));
        }

        // 4. 处理基准数据（如果存在）
        if (this.benchmarkData) {
            this.benchmarkData.sort((a, b) => new Date(a.日期) - new Date(b.日期));
            
            // 对齐基准数据到资产数据日期范围
            const startDate = this.dates[0];
            const endDate = this.dates[this.dates.length-1];
            
            this.benchmark = this.benchmarkData
                .filter(item => {
                    const date = new Date(item.日期);
                    return date >= startDate && date <= endDate;
                })
                .map(item => item.基准);
                
            // 5. 计算基准累计收益率（百分比）
            this.benchmarkReturns = [];
            if (this.benchmark.length > 0) {
                const initial = this.benchmark[0];
                this.benchmarkReturns = this.benchmark.map(b => 
                    ((b - initial) / initial * 100).toFixed(2)
                );
            }

            // 6. 计算基准回撤（百分比）
            this.benchmarkDrawdowns = [];
            let benchmarkPeak = this.benchmark[0];
            for (let i = 0; i < this.benchmark.length; i++) {
                if (this.benchmark[i] > benchmarkPeak) benchmarkPeak = this.benchmark[i];
                this.benchmarkDrawdowns.push(((benchmarkPeak - this.benchmark[i]) / benchmarkPeak * 100).toFixed(2));
            }
        }
    }

    getEchartsData() {
        //获取echarts数据
        const result = this.dates.map((date, index) => ({
            日期: date,
            策略收益: parseFloat(this.strategyReturns[index]),
            策略回撤: parseFloat(this.strategyDrawdowns[index]),
        }));

        // 如果有基准数据，添加基准收益和回撤
        if (this.benchmark && this.benchmark.length > 0) {
            this.dates.forEach((date, index) => {
                result[index].基准收益 = parseFloat(this.benchmarkReturns[index]);
                result[index].基准回撤 = parseFloat(this.benchmarkDrawdowns[index]);
            });
        }

        return result;
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
