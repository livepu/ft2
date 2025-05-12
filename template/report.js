//js版本的分析类，最重要的是处理echarts的数据，涉及基准；
// 其他夏普之类的数据，按照输出形式格式需要。因为这里直接html的结果。
class AssetAnalyzer {
    constructor(assetsData, transactionData = []) {
        this.assetsData = assetsData;
        this.benchmarkData = null;
        this._trade_profits = this._calculateTradeProfits(transactionData); // 新增交易盈亏计算
        this.processData();
    }

    // 计算每笔交易的盈亏（与Python版本逻辑一致）
    _calculateTradeProfits(transactions) {
        if (!Array.isArray(transactions) || transactions.length === 0) {
            return [];
        }

        // 按标的分组持仓
        const positions = {};
        const processedTrades = [];

        transactions.forEach(trade => {
            const symbol = trade.标的;
            const volume = trade.数量;
            const absVolume = Math.abs(volume);
            const price = trade.价格;
            const side = trade.方向;
            const time = new Date(trade.时间);
            const fee = trade.手续费;

            if (!positions[symbol]) {
                positions[symbol] = {
                    volume: 0,
                    cost: 0,
                    openTime: null,
                    openPrice: 0,
                    openFee: 0
                };
            }

            if (side === '买入') {
                positions[symbol].volume += absVolume;
                positions[symbol].cost += absVolume * price + fee;
                if (positions[symbol].openTime === null) {
                    positions[symbol].openTime = time;
                    positions[symbol].openPrice = price;
                    positions[symbol].openFee += fee;
                }
            } else if (side === '卖出') {
                if (positions[symbol].volume === 0) {
                    return; // 跳过没有持仓的卖出
                }

                const sellAmount = absVolume * price;
                const costRatio = absVolume / positions[symbol].volume;
                const cost = costRatio * positions[symbol].cost;
                const profit = sellAmount - cost - fee;
                const openFeePortion = costRatio * positions[symbol].openFee;

                processedTrades.push({
                    symbol: symbol,
                    profit: profit,
                    openTime: positions[symbol].openTime,
                    closeTime: time,
                    openPrice: positions[symbol].openPrice,
                    openFee: openFeePortion,
                    closeFee: fee,
                    closePrice: price,
                    volume: volume,
                    originalTrade: trade
                });

                // 更新持仓
                positions[symbol].volume -= absVolume;
                positions[symbol].cost -= cost;
                positions[symbol].openFee -= openFeePortion;

                if (positions[symbol].volume === 0) {
                    positions[symbol].openTime = null;
                    positions[symbol].openPrice = 0;
                    positions[symbol].openFee = 0;
                }
            }
        });

        return processedTrades;
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
            this.strategyDrawdowns.push(((this.assets[i] - peak) / peak * 100).toFixed(2));
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
                this.benchmarkDrawdowns.push(((this.benchmark[i] - benchmarkPeak) / benchmarkPeak * 100).toFixed(2));
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

    // 计算最大回撤（返回回撤值和时间段）
    calculate_max_drawdown() {
        if (this.strategyDrawdowns.length === 0) {
            return [0, null, null]; // 返回默认值
        }

        let maxDrawdown = 0;
        let startDate = null;
        let endDate = null;
        let currentPeakIndex = 0;

        for (let i = 0; i < this.strategyDrawdowns.length; i++) {
            const drawdown = this.strategyDrawdowns[i];
            
            // 找到新的峰值点
            if (this.assets[i] > this.assets[currentPeakIndex]) {
                currentPeakIndex = i;
            }
            
            // 计算当前回撤
            const currentDrawdown = (this.assets[i] - this.assets[currentPeakIndex]) / this.assets[currentPeakIndex];
            
            // 更新最大回撤
            if (currentDrawdown < maxDrawdown) {
                maxDrawdown = currentDrawdown;
                startDate = this.dates[currentPeakIndex];
                endDate = this.dates[i];
            }
        }

        return [
            maxDrawdown * 100, // 转换为百分比
            startDate,
            endDate
        ];
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


    // 计算平均持仓周期（交易日）
    calculate_average_holding_period() {
        if (!this._trade_profits || this._trade_profits.length === 0) {
            return "0.00";
        }
        
        let totalDays = 0;
        this._trade_profits.forEach(trade => {
            // 确保日期是有效的Date对象
            const openTime = trade.openTime instanceof Date ? trade.openTime : new Date(trade.openTime);
            const closeTime = trade.closeTime instanceof Date ? trade.closeTime : new Date(trade.closeTime);
            
            // 检查日期有效性
            if (isNaN(openTime.getTime()) || isNaN(closeTime.getTime())) {
                console.error('无效的日期:', trade);
                return;
            }
            
            const days = (closeTime - openTime) / (1000 * 60 * 60 * 24);
            totalDays += days;
        });
        
        // 确保计算结果有效
        const avgDays = totalDays / this._trade_profits.length;
        return isNaN(avgDays) ? "0.00" : avgDays;
    }


    calculate_win_rate() {
        if (!this._trade_profits || this._trade_profits.length === 0) {
            return null;
        }

        const profitableTrades = this._trade_profits.filter(trade => trade.profit > 0);
        return (profitableTrades.length / this._trade_profits.length) * 100;
    }


    calculate_avg_profit(mode = 'amount') {
        const profitable_trades = this._trade_profits.filter(t => t.profit > 0);
        if (profitable_trades.length === 0) return null;

        let profits;
        if (mode === 'amount') {
            profits = profitable_trades.map(t => t.profit);
        } else if (mode === 'percentage') {
            profits = profitable_trades.map(t => 
                t.profit / (Math.abs(t.volume) * t.open_price)
            );
        } else {
            throw new Error("mode 必须是 'amount' 或 'percentage'");
        }

        return profits.reduce((sum, p) => sum + p, 0) / profits.length;
    }

    calculate_avg_loss(mode = 'amount') {
        const loss_trades = this._trade_profits.filter(t => t.profit < 0);
        if (loss_trades.length === 0) return null;

        let losses;
        if (mode === 'amount') {
            losses = loss_trades.map(t => t.profit);
        } else if (mode === 'percentage') {
            losses = loss_trades.map(t => 
                t.profit / (Math.abs(t.volume) * t.open_price)
            );
        } else {
            throw new Error("mode 必须是 'amount' 或 'percentage'");
        }

        return losses.reduce((sum, l) => sum + l, 0) / losses.length;
    }

    calculate_avg_profit_loss_ratio(mode = 'amount') {
        const avg_profit = this.calculate_avg_profit(mode);
        const avg_loss = this.calculate_avg_loss(mode);
        
        if (avg_profit === null || avg_loss === null) {
            return null;
        }
        
        return Math.abs(avg_profit / avg_loss);
    }

    // 获取最大盈利交易数据（格式与HTML模板一致）
    get_largest_profit_trades(n = 5) {
        if (!this._trade_profits || this._trade_profits.length === 0) {
            return [];
        }
        
        return [...this._trade_profits]
            .sort((a, b) => b.profit - a.profit)
            .slice(0, n)
            .map(trade => ({
                symbol: trade.symbol,
                profit: trade.profit.toFixed(2),
                open_time: trade.openTime.toISOString().split('T')[0],
                open_price: trade.openPrice.toFixed(2),
                open_fee: trade.openFee.toFixed(2),
                close_time: trade.closeTime.toISOString().split('T')[0],
                close_price: trade.closePrice.toFixed(2),
                close_fee: trade.closeFee.toFixed(2),
                volume: Math.abs(trade.volume).toString()
            }));
    }

    // 获取最大亏损交易数据（格式与HTML模板一致）
    get_largest_loss_trades(n = 5) {
        if (!this._trade_profits || this._trade_profits.length === 0) {
            return [];
        }
        
        return [...this._trade_profits]
            .sort((a, b) => a.profit - b.profit)
            .slice(0, n)
            .map(trade => ({
                symbol: trade.symbol,
                profit: trade.profit.toFixed(2),
                open_time: trade.openTime.toISOString().split('T')[0],
                open_price: trade.openPrice.toFixed(2),
                open_fee: trade.openFee.toFixed(2),
                close_time: trade.closeTime.toISOString().split('T')[0],
                close_price: trade.closePrice.toFixed(2),
                close_fee: trade.closeFee.toFixed(2),
                volume: Math.abs(trade.volume).toString()
            }));
    }        
    // 生成关键指标数据
    getMetrics() {
        const [maxDrawdown, startDate, endDate] = this.calculate_max_drawdown();
        const drawdownPeriod = startDate && endDate 
            ? `${startDate.toISOString().split('T')[0]} 至 ${endDate.toISOString().split('T')[0]}` 
            : "N/A";
        const avgProfit = this.calculate_avg_profit();
        const avgLoss = this.calculate_avg_loss();
        const avgHoldingPeriod = this.calculate_average_holding_period();
        const winRate = this.calculate_win_rate();
        const profitLossRatio = this.calculate_avg_profit_loss_ratio();
        return [
            {name: '回测区间', value: `${this.dates[1].toISOString().split('T')[0]} 至 ${this.dates[this.dates.length-1].toISOString().split('T')[0]}`, desc: '区间开始前一交易日，作为基准日'},
            {name: '初始资金', value: this.assets[0].toFixed(2)},
            {name: '最终资产', value: this.assets[this.assets.length-1].toFixed(2)},
            {name: '累计收益率', value: `${(this.calculate_return_rate() * 100).toFixed(2)}%`},
            {name: '年化收益率', value: `${(this.calculate_annualized_return() * 100).toFixed(2)}%`},
            {name: '年化波动率', value: `${(this.calculate_volatility() * 100).toFixed(2)}%`},
            {name: '夏普比率', value: this.calculate_sharpe_ratio().toFixed(2)},
            {name: '最大回撤', value: `${maxDrawdown.toFixed(2)}%，时段：${drawdownPeriod}`},
            {name: '平均盈亏比', value: profitLossRatio !== null ? `${profitLossRatio.toFixed(2)}` : 'N/A'},
            {name: '平均持仓时间(天)', value: avgHoldingPeriod !== null ? `${avgHoldingPeriod.toFixed(2)}` : 'N/A'}
        ];
    }


}


// 渲染关键指标表格
function renderMetricsTable(data) {
    layui.use(['table'], function() {
        const table = layui.table;
        table.render({
            elem: '#metricsTable',
            data: data,
            cols: [[
                {field: 'name', title: '指标名称'},
                {field: 'value', title: '指标值'},
                {field: 'desc', title: '备注'}
            ]],
            skin: 'line',
            page: false,
            even: true  // 开启隔行变色
        });
    });
}