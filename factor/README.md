# ft2.factor 因子挖掘模块

## 模块概述

ft2.factor 是一个完整的因子挖掘模块，提供了因子定义、计算、检验、组合和管理的完整功能。

## 模块结构

```
ft2/factor/
├── __init__.py          # 模块入口，导出所有公共接口
├── base.py              # 因子基类和注册器
├── calculator.py         # 因子计算引擎
├── validator.py         # 因子检验器
├── combiner.py          # 因子组合器
├── manager.py           # 因子管理器
├── example.py           # 使用示例
├── test_simple.py       # 简单测试脚本
├── requirements.txt     # 依赖文件
└── README.md           # 本文档
```

## 核心功能

### 1. 因子定义 (base.py)
- `Factor`: 因子基类，所有因子必须继承此类
- `FactorRegistry`: 因子注册器，支持因子发现和实例化
- `FactorMetadata`: 因子元数据，包含名称、描述、分类等信息
- `FactorCategory`: 因子分类枚举（价格、成交量、动量等）
- `FactorFrequency`: 因子频率枚举（日频、周频、月频等）

### 2. 因子计算 (calculator.py)
- `FactorCalculator`: 因子计算引擎
  - 批量计算多个因子
  - 自动处理因子依赖关系
  - 支持缓存优化
  - 支持并行计算
- `DataSource`: 数据源抽象类
- `FactorDependencyGraph`: 因子依赖关系图

### 3. 因子检验 (validator.py)
- `FactorValidator`: 因子检验器
  - IC/IR计算
  - 换手率和衰减率
  - 分组收益检验
  - 多空收益检验
  - 单调性检验
  - 命中率检验
  - 稳定性检验
- 支持生成JSON格式的检验报告
- 支持生成可视化图表（IC序列图、分组收益图）

### 4. 因子组合 (combiner.py)
- `FactorCombiner`: 因子组合器
  - 等权组合
  - IC加权组合
  - IR加权组合
  - 最小方差组合
  - 最大夏普比率组合
  - 风险平价组合
  - PCA组合
- `OrthogonalizationMethod`: 正交化方法枚举
  - 残差正交化
  - PCA正交化
  - 格拉姆-施密特正交化

### 5. 因子管理 (manager.py)
- `FactorManager`: 因子管理器
  - 因子注册和发现
  - 因子版本控制
  - 因子标签管理
  - 因子导入导出
  - 因子库统计
- `StorageFormat`: 存储格式枚举（JSON、YAML、Pickle、Parquet）
- `FactorStatus`: 因子状态枚举（草稿、活跃、已弃用、已归档）

## 依赖关系

### 核心依赖（必须）

| 库名称 | 版本要求 | 用途 | 使用位置 |
|--------|---------|------|---------|
| pandas | >=1.5.0 | 数据处理 | 所有模块 |
| numpy | >=1.23.0 | 数值计算 | 所有模块 |
| scipy | >=1.9.0 | 统计计算 | validator.py, combiner.py |

### 可选依赖

| 库名称 | 版本要求 | 用途 | 使用位置 | 功能说明 |
|--------|---------|------|---------|---------|
| matplotlib | >=3.5.0 | 可视化 | validator.py | 生成IC序列图、分组收益图等 |
| scikit-learn | >=1.1.0 | 机器学习 | combiner.py | PCA正交化、标准化处理 |
| PyYAML | >=6.0 | YAML格式 | manager.py | 因子库的YAML格式导入导出 |

### Python标准库

以下模块使用Python标准库，无需额外安装：
- `abc`: 抽象基类
- `dataclasses`: 数据类
- `datetime`: 日期时间处理
- `typing`: 类型注解
- `enum`: 枚举类型
- `functools`: 函数工具
- `collections`: 集合类型
- `concurrent.futures`: 并发执行
- `logging`: 日志记录
- `pathlib`: 路径处理
- `json`: JSON格式处理
- `pickle`: 序列化
- `hashlib`: 哈希计算
- `copy`: 对象复制
- `tempfile`: 临时文件
- `shutil`: 文件操作

## 安装方式

### 最小安装（仅核心功能）

```bash
pip install pandas numpy scipy
```

### 完整安装（包含所有功能）

```bash
pip install pandas numpy scipy matplotlib scikit-learn PyYAML
```

### 使用requirements.txt安装

```bash
# 核心依赖
pip install -r requirements.txt

# 或使用pip安装所有依赖（包括可选依赖）
pip install pandas numpy scipy matplotlib scikit-learn PyYAML
```

## 使用示例

### 1. 创建自定义因子

```python
from factor import Factor, FactorMetadata, FactorCategory, FactorFrequency

class MomentumFactor(Factor):
    """动量因子"""
    
    def __init__(self, lookback: int = 20):
        metadata = FactorMetadata(
            name=f"Momentum_{lookback}D",
            description=f"{lookback}日动量因子",
            category=FactorCategory.MOMENTUM,
            frequency=FactorFrequency.DAILY
        )
        super().__init__(metadata)
        self.lookback = lookback
    
    def calculate(self, data: dict, symbols: list, dates: list) -> pd.DataFrame:
        """计算动量因子"""
        close_prices = data['close']
        momentum = close_prices / close_prices.shift(self.lookback) - 1
        return momentum
```

### 2. 计算因子

```python
from factor import FactorCalculator, DataSource

# 创建数据源
data_source = DataSource(data)

# 创建计算引擎
calculator = FactorCalculator(data_source=data_source)

# 注册因子
calculator.register_factor(MomentumFactor(lookback=20))

# 计算因子
results = calculator.calculate_batch(
    factor_names=['Momentum_20D'],
    symbols=symbols,
    dates=dates
)
```

### 3. 检验因子

```python
from factor import FactorValidator

# 创建检验器
validator = FactorValidator(
    factor_values=factor_values,
    future_returns=future_returns,
    group_count=10
)

# 计算IC
ic_result = validator.information_coefficient()
print(f"IC均值: {ic_result['mean']:.4f}")
print(f"IR: {ic_result['ir']:.4f}")

# 计算分组收益
group_result = validator.group_returns()
print(f"多空收益: {group_result['spread']:.4f}")
```

### 4. 组合因子

```python
from factor import FactorCombiner, CombinationMethod

# 创建组合器
combiner = FactorCombiner(
    factor_values=factor_values,
    future_returns=future_returns
)

# IC加权组合
result = combiner.combine(
    factor_names=['Momentum_20D', 'Volume_20D'],
    method=CombinationMethod.IC_WEIGHT
)

print(f"组合权重: {result.weights}")
```

### 5. 管理因子库

```python
from factor import FactorManager

# 创建管理器
manager = FactorManager(storage_path='./factor_library')

# 注册因子
manager.register_factor(
    factor=momentum_factor,
    version="1.0.0",
    created_by="User",
    description="20日动量因子"
)

# 列出因子
factors = manager.list_factors()
for factor_info in factors:
    print(f"{factor_info['name']}: {factor_info['description']}")

# 保存因子库
manager.save_library()
```

## 模块特点

### 1. 松耦合设计
- 因子模块独立于回测框架
- 清晰的数据接口
- 易于测试和维护

### 2. 统一接口
- 所有因子遵循相同的计算接口
- 标准化的元数据格式
- 一致的检验指标

### 3. 完整检验
- 丰富的因子检验指标
- 自动生成检验报告
- 可视化支持

### 4. 灵活组合
- 多种组合方法
- 多种正交化方法
- 支持权重优化

### 5. 版本管理
- 完整的因子版本控制
- 因子库管理
- 导入导出功能

## 注意事项

1. **可选依赖处理**：模块对可选依赖进行了优雅处理，如果未安装会给出警告并使用替代方案
2. **数据格式**：因子值DataFrame的index为日期，columns为标的
3. **缓存机制**：计算引擎和检验器都支持缓存，提高重复计算效率
4. **并行计算**：计算引擎支持多线程并行计算，适合大规模因子计算
5. **错误处理**：所有模块都有完善的错误处理和日志记录

## 测试

运行示例程序测试模块功能：

```bash
cd ft2/factor
python example.py
```

运行简单测试：

```bash
cd ft2/factor
python test_simple.py
```

## 许可证

请参考项目根目录的LICENSE文件。

## 联系方式

如有问题或建议，请通过项目issue反馈。
