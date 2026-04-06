# factor 模块 - AI 快速上手

> 因子挖掘体系
>
> **版本：v1.0.0 | 更新日期：2026-04-04**
>
> **AI 助手注意：** 如果发现实际 API 与本文档不一致，说明源码已更新但 AI.md 未同步，请提醒用户更新。

---

## 核心 API

### Factor 基类

```python
from factor import Factor

class MyFactor(Factor):
    """自定义因子"""
    
    def calc(self, data):
        """计算因子值"""
        return data['close'].pct_change(20)  # 20日收益率
```

### FactorRegistry - 因子注册表

```python
from factor import FactorRegistry

# 注册因子
registry = FactorRegistry()
registry.register(MyFactor())

# 获取因子
factor = registry.get('MyFactor')
```

### FactorCalculator - 批量计算

```python
from factor import FactorCalculator

calculator = FactorCalculator(data)
factor_values = calculator.calc(['factor1', 'factor2', 'factor3'])
```

---

## 因子验证

### IC 计算

```python
from factor import FactorValidator

validator = FactorValidator(factor_values, returns)
result = validator.calc_ic()

print(f"IC均值: {result['ic_mean']:.4f}")
print(f"IC标准差: {result['ic_std']:.4f}")
print(f"IR: {result['ir']:.4f}")
```

### 分组收益

```python
group_result = validator.group_return(n_groups=5)
# 返回：每组收益、组间差异等
```

### 单调性检验

```python
monotonic = validator.monotonic_test()
# 返回：是否单调、相关系数等
```

---

## 完整示例

```python
from factor import Factor, FactorValidator

# 定义因子
class Momentum(Factor):
    def calc(self, data):
        return data['close'].pct_change(20)

# 计算因子值
momentum = Momentum()
factor_values = momentum.calc(data)

# 验证因子
validator = FactorValidator(factor_values, returns)
ic_result = validator.calc_ic()

print(f"IC均值: {ic_result['ic_mean']:.4f}")
print(f"IR: {ic_result['ir']:.4f}")
```

---

## 数据格式约定

**因子值 DataFrame：**
- `index` = 日期
- `columns` = 股票代码
- `values` = 因子值

**收益率 DataFrame：**
- 格式同上
- 用于计算 IC

---

> 详细文档：`factor/README.md`
