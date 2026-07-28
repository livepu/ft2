# MCTS 树搜索引擎（Signal Walker / 信号行者）

> 定位：**价值驱动的路径搜索**，与 GP 互补——GP 宽探索，MCTS 深挖掘。
> 当前版本：**v1（已验证）** — 零 LLM 依赖、纯本地 AST 动作、因子+择时通用。
> 验证基准：CLOSE 单变量 × 31 申万行业，Sharpe=1.17（零先验种子），12× GP 范式产出效率。

**文献基础**：AlphaJungle (清华, 2505) 首次验证 MCTS 因子挖掘；AlphaCFG (2601) CFG 语法约束；AlphaPROBE (2602) 贝叶斯检索+DAG。本方案取三家多样性机制 + 自研 6 种本地动作，全部 LLM-free。

---

## 一、核心问题

### GP 的瓶颈（已被 MCTS 实测证实）

```
GP 每代：250 个随机变异 → 全部评估 → 淘汰差的
  → 盲目：不知道往哪走（15,000 次评估中 80%+ 在死路上）
  → 无记忆：每代从零开始（无路径信用分配）
  → 预算均分：300 个种子每人都有预算，299 个是死路也照投
  → 效率低：15,000 次评估 → Sharpe=0.97，56 eval/千次产出
```

### MCTS 的解决（v1 实测验证）

```
MCTS 路径：只走最有希望的一条路 → 深度探索
  → 有方向：Bayesian UCB 告诉你哪条路最有希望
  → 有记忆：树结构记录所有走过的路径
  → 集中预算：死路种子自然淘汰，好方向获得压倒性预算
  → 高效：8,500 次评估 → 9 种范式，1.06 范式/千次（12× GP）
```

---

## 二、架构总览

```
utils/mcts/v1/                      ← 纯搜索算法（零 factor 依赖）
├── engine.py      MCTSEngine + MCTSConfig    主循环 + 配置
├── node.py        MCTSNode                   树节点（含贝叶斯字段）
├── tree.py        MCTSTree                   select/expand/backprop
├── actions.py     6 种本地动作               变异算子（LLM-free）
├── config.py      ActionConfig               搜索空间配置
├── constraints.py CFG 语法 + 语义检查        合法性过滤
├── ast_utils.py   AST 工具函数               遍历/替换
├── dedup.py       子树同构 + 频繁子树监控     去重
├── cache.py       SimpleFitnessCache         评估缓存
└── __init__.py

factor/v5/mcts_engine.py            ← 桥接层（28 行，对标 gp_engine.py）
  注入 _ExpressionFromAST evaluator

k01/                                ← 编排层（对标 kb05）
├── common.py      MCTS 工厂 + 种子 + 评估器
├── 01-a-CLOSE_单变量_MCTS.py      CLOSE 单变量探索
├── 01-b-HIGH_单变量_MCTS.py       HIGH 单变量探索
├── 01-c-REL_CLOSE_单变量_MCTS.py  REL_CLOSE 单变量探索
└── output/                         搜索结果

拆分模式（对齐 utils/gp/v5 + factor/v5）:
  utils/mcts/v1/       ← 纯搜索算法（零评估依赖）
  factor/v5/mcts_engine.py ← 桥接层（注入因子 evaluator）
  factor/v5/           ← 纯评估引擎（FacEngine.backtest）
  k01/                 ← 编排层（数据+种子+运行）
```

---

## 三、核心数据结构

### 3.1 MCTSNode

```python
@dataclass
class MCTSNode:
    """MCTS 树节点 = 一个表达式"""
    expression: str                    # 表达式字符串
    tree: ast.Expression               # AST 树
    fitness: float = -999.0            # 评估后的 fitness
    
    # MCTS 统计
    visit_count: int = 0               # 被访问次数（反向传播累计）
    total_value: float = 0.0           # 累计价值总和
    
    # 树结构
    parent: Optional['MCTSNode'] = None
    children: List['MCTSNode'] = []
    edge: Optional[str] = None         # 变异操作描述
    depth: int = 0                     # 树深度（根=0）
    is_seed: bool = False
    
    # Bayesian 先验（AlphaPROBE）
    prior_quality: float = 1.0         # 归一化质量
    outdegree: int = 0                 # 出度（被用作父节点的次数）
```

### 3.2 MCTSTree

```python
class MCTSTree:
    """MCTS 树：管理节点、路径、统计"""
    
    def select(self, mode='bayesian_ucb') -> MCTSNode:
        """UCB 选路：从根开始沿最优子节点走到叶节点"""
    
    def expand(self, node, n_branches, action_config, ...) -> list:
        """扩路：对叶节点执行 6 种变异动作，生成子节点
        约束链：CFG 语法 → 语义检查 → 去重 → 频繁子树回避 → 深度检查"""
    
    def backpropagate(self, node, fitness):
        """反向传播：从叶到根更新 visit_count 和 total_value"""
```

---

## 四、核心循环：4 步详解

### Step 1: Selection — Bayesian UCB

```python
# 贝叶斯增强 UCB（AlphaPROBE 方案）
Q = node.total_value / node.visit_count
explore = C * sqrt(ln(N_parent) / N_node)
prior = prior_quality * (1-gamma)^depth * (1-beta)^outdegree
score = Q * prior + explore
```

- `(1-gamma)^depth`：深度惩罚——越深越容易过拟合
- `(1-beta)^outdegree`：出度惩罚——被频繁选为父节点 → 该方向已充分探索

### Step 2: Expansion — 6 种本地动作 + 约束链

| 动作 | 操作 | 风险 |
|:---|:---|:---|
| `change_param` | 改窗口/常数参数 | 低 — 精调 |
| `change_variable` | 替换变量 | 低 |
| `change_function` | 替换同元数函数 | 低 |
| `wrap_function` | 外包一层函数 | 中 — 增深度 |
| `unwrap_function` | 去掉外层函数 | 低 — 简化 |
| `graft` | 嫁接最优池子树 | 中 — 方向跳跃 |

> 所有动作均为纯 AST 操作，不依赖 LLM。动作元数据在 `_FUNC_META` 中定义，
> `allowed_functions` 中的函数必须同步加入 `_FUNC_META` 才能被动作引用。

**约束链**（按序过滤）：
1. CFG 语法检查 — 算子元数、类型匹配
2. 语义检查 — 过滤冗余表达式（x+0, x*1, cs_rank(cs_rank(...)))
3. 签名去重 — 表达式字面相同 → 拒绝
4. 频繁子树回避（FSA） — 含高频子树 → 概率拒绝
5. 深度检查 — 超 max_depth → 拒绝

### Step 3: Evaluation — 外部注入

```python
# evaluator(data, tree) → ndarray   # 表达式求值
# fitness_calculator.compute(ndarray) → float  # fitness 计算
```

评估器完全由外部注入，MCTS 引擎不感知领域（因子/择时均可用同一引擎）。

### Step 4: Backpropagation — 信用分配

叶节点 fitness 沿路径向上传播，更新所有祖先的 visit_count 和 total_value。
GP 做不到的"下坡路保护"——差节点 B(fit=0.1) 的子孙 C(fit=0.9) 被发现后，
B 的 Q 值会被 C 拉高，继续吸引探索预算。

---

## 五、多样性机制（v1 实测有效）

### 5.1 出度感知树选择（AlphaPROBE）

```
主循环中不再 round-robin，而是出度低的树优先被选：
weights = [max_outdegree - od + 1 for od in outdegrees]
```

效果：被频繁探索的树自动退避，其他 45 棵树获得预算。

### 5.2 频繁子树回避 FSA（AlphaJungle）

```
expand 阶段：新表达式含高频子树 → 概率拒绝
概率随频率上升而衰减：1 / (1 + log(1+count-threshold))
```

### 5.3 结构签名去重归档（自研）

```
最优池更新时：剥掉 cs_rank/cs_scale/abs/sign 等等价包装
→ 提取核心调用链哈希 → 同签名只保留 fitness 最高的
```

效果：Top-15 从单一范式 9 个重复 → 9 种不同范式。

### 5.4 相似度折扣（AlphaCFG，默认关闭）

```
fitness × (1 - alpha × max_similarity)
```

默认关闭原因：单变量搜索空间中，浅层好结构天然相似度高，折扣会误杀有潜力路径。

---

## 六、对比 GP v6（同条件实测）

| | GP v6 (AURORA) | MCTS v1 |
|:---|:---|:---|
| 搜索范式 | 种群进化（广撒网） | 树搜索（深挖掘） |
| 种子 | 303 手工 | 46 裸变量 |
| 评估次数 | ~15,000 | 8,498 |
| 耗时 | 861s | 566s |
| 冠军 Sharpe | 0.972 | 0.924~1.165 |
| 冠军结构 | `0.02/ts_kurt(ts_mean(CLOSE,20),60)` | `ts_predict(tsf(ts_skew(ts_std(...))))` |
| 魔法常数 | ❌ 有 (0.02) | ✅ 无 |
| Top-15 范式 | 5 种（8/15 同构） | 9 种 |
| 范式/千次评估 | 0.11 | 1.06 |
| 适合阶段 | 宽探索找方向 | 深挖掘产候选池 |

### 与论文对比

| | AlphaJungle | AlphaCFG | AlphaPROBE | **MCTS v1** |
|:---|:---|:---|:---|:---|
| 变异生成 | LLM | CFG+Tree-LSTM | LLM | **6 种本地动作** |
| LLM 依赖 | 强 | 零 | 强 | **零** |
| GPU 依赖 | 中 | 有 | 中 | **零** |
| 多样性 | FSA | 相似度折扣 | 3D 度量 | **FSA+出度+签名** |
| A 股数据 | 未提 | CSI300 | CSI300/500/1000 | **31 申万行业** |
| 实测指标 | 优于基线 | 优于基线 | ICIR 3× | **Sharpe 1.17** |

---

## 七、关键配置参数

| 参数 | 默认 | 说明 |
|:---|:---|:---|
| `n_iterations` | 300 | 总搜索轮数 |
| `n_branches` | 3 | 每轮扩路子节点数 |
| `max_depth` | 6 | 树最大深度 |
| `selection_mode` | `bayesian_ucb` | 选路策略 |
| `ucb_constant` | 1.414 | 探索-利用平衡 |
| `gamma` | 0.05 | 贝叶斯深度惩罚 |
| `beta` | 0.01 | 贝叶斯出度惩罚 |
| `enable_graft` | True | 嫁接变异（关键：跨越下坡路） |
| `enable_cfg` | True | CFG 语法约束 |
| `enable_semantic` | True | 语义约束（防冗余） |
| `enable_subtree_avoid` | True | 频繁子树回避 |
| `enable_diverse_pool` | True | 最优池结构去重 |
| `best_pool_size` | 20 | 最优池容量 |
| `early_stop_rounds` | 2000 | 全局最优 N 轮无提升早停 |

---

## 八、经验教训

### 已验证的

1. **零先验可行**：46 个裸变量种子即可自主发现复杂结构，不需要手工桥接种子
2. **graft 是关键**：MCTS 依赖 graft 跳跃下坡路，没有 graft 的纯变异路径很多方向不可达
3. **FUNC_META 必须完整**：漏填 6 个函数导致 `ts_predict(-ts_kurt)` 类结构永远不可达
4. **多样性归档有效**：仅 12 行代码将 Top-15 从 2 范式扩展到 9 范式
5. **冠军在 18% 预算出现**：剩余 82% 预算在冠军上原地踏步

### 需要注意的

1. **MCTS 缺宽探索**：单一路径搜索，适合深挖不适合从零广撒网
2. **add_condition 过拟合**：if-else 门控在单变量空间中容易数据挖掘
3. **相似度折扣伤浅层**：单变量空间中好结构天然相似，折扣误杀太多
4. **后期效率低**：冠军找到后大量预算浪费（需配合早停或预算重分配）

---

## 九、文件清单

| 文件 | 行数 | 职责 |
|:---|:---|:---|
| `engine.py` | ~480 | 主循环 + 配置 + 结构签名 + 相似折扣 |
| `tree.py` | ~400 | select/expand/backprop + FSA |
| `node.py` | ~80 | MCTSNode dataclass |
| `actions.py` | ~450 | 6 种变异动作 + _FUNC_META |
| `config.py` | ~60 | ActionConfig |
| `constraints.py` | ~250 | CFG 语法 + 语义检查 |
| `ast_utils.py` | ~200 | AST 遍历/替换工具 |
| `dedup.py` | ~180 | 子树同构 + FrequentSubtreeMonitor |
| `cache.py` | ~60 | SimpleFitnessCache |

---

## 十、参考文献

| 论文 | ID | 核心贡献 | v1 采纳 |
|:---|:---|:---|:---|
| AlphaJungle (清华) | 2505.11122 | MCTS+LLM，频繁子树回避 | FSA |
| AlphaCFG | 2601.22119 | CFG 约束 + Tree-LSTM + PUCT | CFG 过滤 |
| AlphaPROBE | 2602.11917 | DAG + 贝叶斯检索 + 3D 多样性 | Bayesian UCB，出度 |
| AlphaAgent (KDD) | 2502.16789 | AST 子树同构 | 子树同构检测 |
