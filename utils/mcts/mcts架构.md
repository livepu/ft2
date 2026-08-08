# MCTS 树搜索引擎（Signal Walker / 信号行者）

> 定位：**价值驱动的路径搜索**，与 GP 互补——GP 宽探索，MCTS 深挖掘。
> 设计阶段：v2 规划稿。当前 v1 实现已偏离本设计（详见末尾修订记录）。

**文献基础**：AlphaJungle (清华, 2505) 首次验证 LLM+MCTS 因子挖掘可行性；AlphaCFG (2601) 引入 CFG 语法约束 + Tree-LSTM 增强 MCTS；AlphaPROBE (2602) 提出 DAG 进化 + 贝叶斯检索。

---

## 一、核心问题：GP 的三个瓶颈

1. **下坡路抛弃**：GP 选择只看当前这一步的 fitness，如果某个变异让 fitness 暂时下降（下坡路），GP 会直接淘汰这个"差"个体，但它可能只需要再变异一步就能反弹到新高。
   - 例子：`ts_predict(ts_kurt(CLOSE,20),10)` fitness 低，但 `neg(ts_predict(ts_kurt(CLOSE,20),10))` 可以反弹

2. **盲目变异**：GP 每代 250 个子代全部评估，其中大量是无效变异

3. **无记忆**：GP 没有路径记忆——`ts_rank(ts_roc(CLOSE,20))` 已经被尝试过 5 次且都差，GP 下一代会继续重新生成它

---

## 二、架构总览

```
utils/mcts/                           # MCTS 搜索包
├── v1/                               # v1 当前实现（未分级）
│   ├── engine.py     MCTSEngine      # 主循环
│   ├── node.py       MCTSNode        # 节点
│   ├── tree.py       MCTSTree        # 树管理器
│   ├── actions.py    动作空间         # 变异操作（6 种本地动作）
│   ├── config.py     ActionConfig    # 搜索空间边界配置
│   ├── constraints.py CFG + 语义     # 合法性过滤
│   ├── ast_utils.py  AST 工具        # 遍历/替换/规范化
│   ├── dedup.py      子树监控        # 同构检测 + 频繁模式
│   └── cache.py      评估缓存        # SQLite 缓存
└── mcts架构.md                        # 本文档
```

---

## 三、核心数据结构

### 3.1 MCTSNode

```python
@dataclass
class MCTSNode:
    expression: str                     # 因子表达式字符串
    tree: ast.Expression                # AST 树
    fitness: float = -999.0             # 评估后的 fitness
    
    # MCTS 统计
    visit_count: int = 0                # 反向传播累计
    total_value: float = 0.0            # 累计价值
    
    # 树结构
    parent: Optional['MCTSNode']        # 父节点
    children: List['MCTSNode']          # 子节点
    edge: Optional[str]                 # 动作描述
    depth: int = 0                      # 树深度
    is_seed: bool = False
    
    # Bayesian 先验（AlphaPROBE）
    prior_quality: float = 1.0          # 归一化质量
    outdegree: int = 0                  # 被选次数（扩展用）
```

### 3.2 MCTSTree

```python
class MCTSTree:
    def select(self, selection_mode) -> MCTSNode: ...
    def expand(self, leaf, n, action_config, ...) -> list: ...
    def backpropagate(self, leaf, fitness): ...
```

---

## 四、核心循环：4 步详解

### Step 1: Selection（选路）

```
当前 v1 实现：Bayesian UCB（论文 §4.1.3）
score = Q_value * (prior_quality * (1-gamma)^depth * (1-beta)^outdegree) + C * sqrt(log(N_parent)/N_node)
```

### Step 2: Expansion（扩路）

v1 当前实现：7 种本地规则动作——change_param / change_variable / change_function / wrap_function / unwrap_function / add_condition / graft

### Step 3: Evaluation（评估）

v1 当前实现：外部注入 evaluator + fitness_calculator（`factor/v5/mcts_engine.py` 28 行桥接层）

### Step 4: Backpropagation（反向传播）

沿路径向上传播 fitness，更新 visit_count 和 total_value。

---

## 五、扩路动作空间（7 种）

| 动作 | 权重 | 说明 |
|:---|:---|:---|
| `change_param` | 30% | 改变函数的数值参数（窗口、阈值） |
| `change_function` | 25% | 换同元数函数 |
| `change_variable` | 15% | 替换变量 |
| `wrap_function` | 15% | 用新函数包裹表达式 |
| `unwrap_function` | 5% | 去掉外层函数 |
| `add_condition` | 5% | 用 IfExp 包裹（阈值条件） |
| `graft` | 5% | 从最优池取子树嫁接到当前树 |

---

## 六、多样性策略

| 机制 | 论文来源 | 当前状态 |
|:---|:---|:---|
| 规则动作驱动的局部变换 | 自研 | ✅ v1 已实现（7 种动作） |
| 贝叶斯增强先验值 | AlphaPROBE | ✅ v1 已实现 |
| CFG 语法约束 | AlphaCFG | ✅ 过滤式（非生成式）|
| 语义约束 | AlphaCFG | ✅ _no_raw_math 保护 |
| 子树同构检测 | AlphaAgent | ✅ FrequentSubtreeMonitor |
| GT-Score 防过拟合 | arXiv 2602.00080 | 文档已写，未启用 |
| 频繁子树回避 FSA | AlphaJungle | ✅ v1 已实现 |
| 计算热启动 | AlphaJungle | 待做（LLM 依赖，低优先级）|


## 七、与 GP 分层协作

```
第一层：GP 宽探索     ← v5 GPEngine / v6 AURORA（找种子）
第二层：MCTS 深挖掘   ← 本引擎（对种子深度优化）
第三层：评估          ← factor/v5 FacEngine.backtest
第四层：组合/集成     ← 未来（MCTS 产出的多个方向组合）
```

---

## 八、实施计划

### 已完成

- [x] MCTSNode + MCTSTree 基础数据结构
- [x] SQLite 缓存（评估缓存）
- [x] 7 种变异动作（change_param/function/variable, wrap/unwrap, add_condition, graft）
- [x] ActionConfig（变量池/函数池/参数窗口配置）
- [x] CFG 语法检查 + 语义约束
- [x] 子树同构检测 + FrequentSubtreeMonitor
- [x] Bayesian UCB 选择
- [x] GT-Score fitness（文档）
- [x] 零 LLM 依赖

### 待做

- [ ] 并行评估（多进程评估子节点）
- [ ] 最优路径可视化
- [ ] A/B 测试（MCTS vs GP）


## 九、参考文献

| 论文 | 核心贡献 | 当前采纳 |
|:---|:---|:---|
| AlphaJungle (2505) | LLM+MCTS 因子挖掘，CFG 语法约束，子树同构去重 | 动作设计、CFG、子树监控 |
| AlphaCFG (2601) | CFG 约束 + Tree-LSTM 增强 UCT | CFG 语法+语义 |
| AlphaPROBE (2602) | DAG 进化路径，贝叶斯先验检索 | Bayesian UCB |
| AlphaAgent (2502) | 子树同构、MCTS 搜索空间探索 | AST 同构检测 |

---

=============================================================================
## 修订记录
=============================================================================

### 2026-07-30 — v1 实现验证报告

以下为 v1 实际实现与设计稿的偏离及验证结果：

#### 核心偏离

| 设计稿 | 实际实现 |
|:---|:---|
| MCTS+LLM 混合 | **纯本地 AST 动作**（零 LLM） |
| 7 种动作（含 add_condition） | **6 种动作（禁掉 add_condition，过拟合）** |
| 种子依赖 kb04 手工桥接 | **46 裸变量零先验种子** |
| PUCT + 价值网络 | **Bayesian UCT（优化后的）** |
| 与 GP 对比待验证 | **已验证：MCTS 全面超越 GP v6** |

#### 关键 bug 修复

1. **`_FUNC_META` 漏填 6 个函数**（neg/ts_predict/tsf/linearreg/ts_intercept/ts_resid）
   → `ts_predict(-ts_kurt)` 类结构永远不可达。补完后冠军 Sharpe 从 0.99 跳到 1.17。

2. **最优池重复**：同一个核的表达式的等价包装（cs_rank/cs_scale）占据了 Top-10
   → 新增 `_structural_signature` 剥掉等价包装后哈希去重（12 行代码）
   → Top-15 从 2 种范式 → 9 种范式

3. **评估器 cs_rank 退化**：`_ExpressionFromAST.evaluate()` 逐列求值导致 cs_rank 只能看到单列
   → 改为 `FactorExpression.evaluate_ranked()`

#### 新增多样性机制

| 机制 | 状态 |
|:---|:---|
| 出度感知树选择 | ✅ 低出度树优先被选 |
| 频繁子树回避 FSA | ✅ 概率拒绝（非硬拦截） |
| 结构签名去重归档 | ✅ 剥 cs_rank/cs_scale/abs/sign 等价包装 |
| 相似度折扣 | ❌ 默认关（单变量空间伤浅层结构） |

#### 实测对比（CLOSE 单变量 × 31 行业，seed=42）

| | GP v6 (AURORA) | MCTS v1 |
|:---|:---|:---|
| 冠军 Sharpe | 0.972 | **1.165** |
| 种子 | 303 手工 | 46 裸变量 |
| 评估次数 | ~15,000 | 6,221 |
| 耗时 | 861s | 624s |
| Top-15 范式 | 5 种（8/15 同构） | **9 种** |
| 每千次评估范式产出 | 0.11 | **1.06（10×）** |
| 魔法常数 | ❌ 有 (0.02) | ✅ 无 |

#### 论文对标

MCTS v1 = AlphaJungle(FSA) + AlphaCFG(LLM-free 理念) + AlphaPROBE(出度+签名去重) + 自研 6 种 AST 动作。

**唯一纯本地、零 LLM、零 GPU、有具体实测数字的 MCTS 因子引擎。**

#### 经验教训

1. **零先验可行**：46 裸变量即可自主发现复杂结构
2. **graft 是关键**：没有 graft，许多方向永远不可达
3. **冠军在 18% 预算出现**：后期 82% 预算浪费在冠军上
4. **单变量空间无"下坡路"**：每种操作都是信号的重解释，要么好要么坏
5. **MCTS 缺宽探索**：需要配合 GP 或种子多样性来覆盖更多方向
