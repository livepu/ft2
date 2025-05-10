class AssetAnalyzer {
    constructor(netValueData) {
        this.netValueData = netValueData;
        this.dates = [];
        this.assets = [];
        this.peakValues = [];
        this.drawdowns = [];
        this.processData();
    }

    processData() {
        this.dates = this.netValueData.map(item => item.日期);
        this.assets = this.netValueData.map(item => item.资产);
        
        let peak = this.assets[0];
        this.peakValues = [];
        this.drawdowns = [];
        
        for (let i = 0; i < this.assets.length; i++) {
            if (this.assets[i] > peak) {
                peak = this.assets[i];
            }
            this.peakValues.push(peak);
            this.drawdowns.push((peak - this.assets[i]) / peak * 100);
        }
    }

    getDrawdownSeries() {
        return this.dates.map((date, index) => ({
            日期: date,
            回撤: this.drawdowns[index]
        }));
    }

    getPeakSeries() {
        return this.dates.map((date, index) => ({
            日期: date,
            峰值: this.peakValues[index]
        }));
    }
}
