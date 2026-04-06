# ft2 AI 索引

> **AI 助手请先阅读此文件**，然后根据任务需求按需加载模块文档
>
> **版本：v1.0.0 | 更新日期：2026-04-04**

---

## 项目概览

ft2 是量化回测框架，核心模块：

| 模块 | 用途 | 何时使用 |
|---|---|---|
| `notebook` | HTML 报告生成 | 需要输出可视化报告 |
| `core` | 回测引擎核心 | 需要运行回测、分析结果 |
| `factor` | 因子挖掘体系 | 需要计算因子、验证 IC |

---

## 模块索引

### notebook - 报告生成器

**快速上手：**
```python
from notebook import Notebook
nb = Notebook("报告标题")
nb.metrics(data)      # 指标卡片
nb.table(data)        # 表格
nb.chart('line', data) # 图表
nb.export_html(path)  # 导出
```

**详细文档：** `notebook/AI.md`

**何时加载：** 需要生成报告、可视化输出时

---

### core - 回测引擎

**快速上手：**
```python
from core.analyzer import AccountAnalyzer
analyzer = AccountAnalyzer(account)
analyzer.sharpe_ratio()  # 夏普比率
analyzer.max_drawdown()  # 最大回撤
```

**详细文档：** `core/AI.md`

**何时加载：** 需要分析回测结果、计算风险指标时

---

### factor - 因子挖掘

**快速上手：**
```python
from factor import Factor, FactorRegistry
# 定义因子
class MyFactor(Factor):
    def calc(self, data):
        return data['close'].pct_change()
```

**详细文档：** `factor/AI.md`

**何时加载：** 需要定义因子、计算 IC、验证因子时

---

## 常见任务索引

| 任务 | 需要加载的模块 | 示例代码 |
|---|---|---|
| 生成回测报告 | `notebook` + `core` | 见下方示例1 |
| 计算风险指标 | `core` | 见下方示例2 |
| 验证因子 IC | `factor` | 见下方示例3 |
| 输出表格报告 | `notebook` | 见下方示例4 |

---

## 快速示例

### 示例1：生成回测报告

```python
from notebook import Notebook
from core.analyzer import AccountAnalyzer

analyzer = AccountAnalyzer(account)
nb = Notebook("回测报告")

nb.metrics({
    '收益率': f"{analyzer.returns().sum()*100:.2f}%",
    '夏普': f"{analyzer.sharpe_ratio():.2f}",
})

nb.export_html("report.html")
```

### 示例2：计算风险指标

```python
from core.analyzer import AccountAnalyzer

analyzer = AccountAnalyzer(account)
print(f"夏普: {analyzer.sharpe_ratio():.2f}")
print(f"回撤: {analyzer.max_drawdown()*100:.2f}%")
```

### 示例3：验证因子 IC

```python
from factor import FactorValidator

validator = FactorValidator(factor_data, returns)
ic_result = validator.calc_ic()
print(f"IC均值: {ic_result['ic_mean']:.4f}")
```

### 示例4：输出表格报告

```python
from notebook import Notebook

nb = Notebook("数据报告")
nb.table(data, columns=['code', 'name', 'value'])
nb.export_html("table.html")
```

---

## 数据约定

**通用约定：**
- DataFrame: `index=日期`, `columns=股票代码`
- 表格数据: `List[Dict]` 或 `DataFrame`
- 图表数据: `{'x': [...], 'series': [...]}`

---

## 按需加载指南

**AI 助手工作流：**

```
1. 读取 AI_INDEX.md（本文件）
2. 判断任务需要哪些模块
3. 按需读取模块的 AI.md：
   - 需要报告 → 读取 notebook/AI.md
   - 需要分析 → 读取 core/AI.md
   - 需要因子 → 读取 factor/AI.md
4. 生成代码
```

**不要一次性加载所有模块文档！**

---

> 最后更新：2026-04-04
> 版本：v1.0
