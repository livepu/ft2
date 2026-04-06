# core 模块 - AI 快速上手

> 回测引擎核心
>
> **版本：v1.0.0 | 更新日期：2026-04-04**
>
> **AI 助手注意：** 如果发现实际 API 与本文档不一致，说明源码已更新但 AI.md 未同步，请提醒用户更新。

---

## 核心 API

### AccountAnalyzer - 账户分析器

```python
from core.analyzer import AccountAnalyzer
analyzer = AccountAnalyzer(account)
```

### 风险指标

```python
analyzer.sharpe_ratio()      # 夏普比率
analyzer.volatility()        # 年化波动率
analyzer.max_drawdown()      # 最大回撤
analyzer.returns()           # 收益率序列
analyzer.nav()               # 净值序列
analyzer.drawdown()          # 回撤序列
```

### 交易指标

```python
analyzer.win_rate()          # 胜率
analyzer.profit_loss_ratio() # 盈亏比
analyzer.trade_count()       # 交易次数
```

### 时间区间切片

```python
analyzer.getTimeRange('1m')  # 近1月
analyzer.getTimeRange('3m')  # 近3月
analyzer.getTimeRange('1y')  # 近1年
analyzer.getTimeRange('ytd') # 年初至今

# 自定义区间
analyzer.getTimeRange('2024-01-01', '2024-12-31')
```

---

## 完整示例

```python
from core.analyzer import AccountAnalyzer

analyzer = AccountAnalyzer(account)

# 全区间指标
print(f"夏普: {analyzer.sharpe_ratio():.2f}")
print(f"回撤: {analyzer.max_drawdown()*100:.2f}%")

# 近3月指标
analyzer.getTimeRange('3m')
print(f"近3月夏普: {analyzer.sharpe_ratio():.2f}")

# 获取净值序列
nav = analyzer.nav()
returns = analyzer.returns()
```

---

## 其他组件

### Engine - 回测引擎

```python
from core.engine import Engine
engine = Engine(strategy, data)
engine.run()
```

### Account - 账户管理

```python
from core.account import AccountManager
account = AccountManager(initial_cash=1000000)
```

---

> 详细文档：`core/README.md`
