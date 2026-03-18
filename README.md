# FT2 量化回测与报告框架

FT2 是一个轻量级的 Python 量化回测框架，同时提供 Notion 风格的报告生成能力。

## 核心模块

### 1. 回测框架 (core/)

框架的核心部分，目前正在进行重构。提供完整的历史数据管理与策略回测能力，账户分析模块也在重构中。

| 文件 | 说明 |
|------|------|
| [engine.py](core/engine.py) | 回测引擎，按时间轴加载 K 线数据并驱动策略执行 |
| [storage.py](core/storage.py) | Context 上下文管理 + 数据缓存系统 |
| [account.py](core/account.py) | 账户管理，处理下单、持仓、交易记录 |

#### 核心组件

- **Context**：全局上下文，管理数据订阅与历史数据访问
- **Engine**：回测引擎，按时间顺序推送 K 线数据给策略
- **Account**：账户管理器，支持按数量/比例下单，计算手续费、印花税等

#### 快速开始

```python
from ft2 import context, account, engine

class MyStrategy:
    def __init__(self):
        context.mode = 'backtest'
        context.subscribe(['SHSE.000300'], freq='1d', count=200)
    
    def on_bar(self, context, bars):
        df = context.data('SHSE.000300', '1d', count=10)
        # 策略逻辑...
        account.order_volume('SHSE.000300', 100, price=3000)

import datetime
engine.run(MyStrategy, 
    start_time=datetime.datetime(2023, 1, 1),
    end_time=datetime.datetime(2023, 12, 31))
```

---

### 2. Notebook 报告模块 (notebook/)

Notion 风格的交互式报告生成工具，用于在研究分析中替代 Jupyter 的静态输出，输出更丰富的可视化结果。支持多图表显示、内置截图分享功能。

| 文件 | 说明 |
|------|------|
| [notebook.py](notebook/notebook.py) | 主入口，支持链式调用与 Section 容器 |
| [cell.py](notebook/cell.py) | Cell 类型定义与构建器 |

#### 支持的内容类型

- 📝 标题、文本、Markdown
- 📊 表格（支持冻结列、分页、热力图）
- 📈 图表（折线、柱状、饼图、K线、热力图，支持多图联动显示）
- 🔢 指标卡片
- 💻 代码块
- 🧱 Section 容器（可折叠）
- 📸 支持截图分享

#### 快速开始

```python
from ft2 import Notebook

nb = Notebook("策略分析报告")
nb.title("回测结果", level=1)

# 指标卡片
nb.metrics([
    {'name': '年化收益率', 'value': '15.6%'},
    {'name': '夏普比率', 'value': '1.82'},
    {'name': '最大回撤', 'value': '-8.3%'},
])

# 表格
nb.table(data, columns=['code', 'name', 'return'])

# 图表
nb.chart('line', {
    'xAxis': dates,
    'series': [{'name': '净值', 'data': navs}]
}, title='净值曲线')

# Section 容器（可折叠）
with nb.section("详细数据", collapsed=True):
    nb.table(trades)

# 导出 HTML
nb.export_html("report.html")
```

#### 模板渲染

- [template/notebook.html](template/notebook.html) - 主模板
- [template/js/ft-table.js](template/js/ft-table.js) - 表格组件（冻结、分页、热力图）
- [template/js/echarts.min.js](template/js/echarts.min.js) - ECharts 图表库

---

## 依赖

```
pandas
jinja2
pyecharts
```

## 使用场景

| 场景 | 推荐模块 |
|------|----------|
| 量化策略回测 | `core/` 模块 |
| 研究分析报告输出 | `notebook` 模块 |

---

> 📌 当前状态：回测框架正在重构中，Notebook 模块已稳定可用。
