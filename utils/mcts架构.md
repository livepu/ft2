# MCTS 因子搜索架构（信号行者 / Signal Walker）

> 定位：**价值驱动的路径探索**，非随机采样。
> 核心哲学：搜索不是"碰运气"，是"沿着有希望的路走"。
> 不属 GP 范畴，属搜索算法（Search Algorithm）——MCTS + 进化变异 + LLM 引导的混合体。

**文献基础**：AlphaJungle (清华, 2505) 首次验证 LLM+MCTS 因子挖掘可行性；AlphaCFG (2601) 引入 CFG 语法约束 + Tree-LSTM 增强 MCTS；AlphaPROBE (2602) 提出 DAG 进化 + 贝叶斯检索，A 股 CSI300/500/1000 实测 ICIR 达 3× 基线。本方案在这些工作的基础上，保留 v5 的 AST 变异算子效率优势，融合贝叶斯选择、CFG 约束和 GT-Score 防过拟合。

---

## 一、核心问题

### GP 的瓶颈（已被多篇论文证实）

```
GP 每代：200 个随机变异 → 筛掉差的 → 下一轮
  → 盲目：不知道往哪走（AlphaAgent 实验：GP 有效因子率仅 ~30%）
  → 无记忆：走过了还走（每代从零开始，无路径记忆）
  → 下坡路必死：A→A1(0.55) 死了，A2(1.20) 永远不会出现
  → 局部性缺失：微小语法变化 → 行为大幅跳变（连续程序搜索 2602.07659）
```

### MCTS 的解决（AlphaJungle/AlphaCFG 已验证）

```
MCTS 路径：只走最有希望的一条路 → 深度探索
  → 有方向：UCB/PUCT 告诉你哪条路最有希望
  → 有记忆：树结构记录所有走过的路径
  → 下坡路保护：A1(0.55) 是 A2(1.20) 的必经之路，反向传播让 A1 的 UCB 上升
  → 语法约束：CFG 约束变异空间，消除语义冗余（AlphaCFG 方案）
```

---

## 二、架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                      MCTS 因子搜索引擎 (v2)                            │
│                                                                      │
│  ┌──────────────┐  ┌─────────────┐  ┌────────────────────────────┐  │
│  │  MCTS 树      │  │ 变异策略池    │  │  评估管道                   │  │
│  │  (路径记忆)    │  │  (动作空间)   │  │  (fitness 计算)            │  │
│  └──────┬───────┘  └──────┬──────┘  └──────────┬─────────────────┘  │
│         │                 │                     │                     │
│         ▼                 ▼                     ▼                     │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    核心循环 (4 步)                               │  │
│  │                                                                  │  │
│  │  ① Selection ──→ ② Expansion ──→ ③ Evaluation ──→ ④ Backup    │  │
│  │  (贝叶斯+UCB)     (CFG约束+变异)   (GT-Score)      (反向传播)    │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    增强层（论文驱动）                             │  │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌──────────────┐   │  │
│  │  │ 贝叶斯检索  │ │ CFG语法   │ │ 子树同构   │ │ GT-Score     │   │  │
│  │  │ (PROBE)    │ │ 约束(CFG) │ │ 去重(Agent)│ │ 防过拟合(GT) │   │  │
│  │  └───────────┘ └───────────┘ └───────────┘ └──────────────┘   │  │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌──────────────┐   │  │
│  │  │ 频繁子树   │ │ 权重聚焦   │ │ LLM引导    │ │ 并行多树      │   │  │
│  │  │ 回避(Jungle)│ │ (v5复用)  │ │ 变异方向    │ │ 多根搜索      │   │  │
│  │  └───────────┘ └───────────┘ └───────────┘ └──────────────┘   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

> 标注说明：`(PROBE)` = AlphaPROBE 2602.11917, `(CFG)` = AlphaCFG 2601.22119, `(Agent)` = AlphaAgent 2502.16789, `(GT)` = GT-Score 2602.00080, `(Jungle)` = AlphaJungle 2505.11122

---

## 三、核心数据结构

### 3.1 MCTSNode

```python
@dataclass
class MCTSNode:
    """MCTS 树节点 = 一个因子表达式"""
    expression: str                    # 因子表达式字符串
    tree: ast.Expression               # AST 树
    fitness: float = -999.0            # 评估后的 fitness
    
    # MCTS 统计
    visit_count: int = 0               # 被访问次数（反向传播累计）
    total_value: float = 0.0           # 累计价值总和（反向传播累计）
    
    # 树结构
    parent: Optional['MCTSNode'] = None  # 父节点
    children: List['MCTSNode'] = field(default_factory=list)  # 子节点
    edge: Optional[str] = None         # 从父到本节点的变异操作描述
    
    # 元信息
    depth: int = 0                     # 树深度（根=0）
    is_seed: bool = False              # 是否是种子节点
    generation: int = 0                # 创建时的代数
    signature: str = ''                # 方向签名（去重用）
    
    # Bayesian 先验（AlphaPROBE 方案）
    prior_quality: float = 1.0         # 归一化质量（ICIR/SR）
    outdegree: int = 0                 # 当前出度（被用作父因子的次数）
    
    # 子树同构检测（AlphaAgent 方案）
    subtree_hash: str = ''             # 规范化后的 AST 子树哈希
    frequent_subtree_count: int = 0    # 该子树模式在历史中出现次数
```

### 3.2 MCTSTree

```python
class MCTSTree:
    """
    MCTS 树：管理所有节点、路径、统计
    
    结构：
      root ── child1 ── grandchild1
        │                    └─ grandchild2
        └── child2 ── grandchild3
    """
    
    def __init__(self, root_expression: str, root_tree):
        self.root = MCTSNode(
            expression=root_expression,
            tree=root_tree,
            depth=0,
            is_seed=True,
        )
        self.all_nodes: Dict[str, MCTSNode] = {}         # signature → node
        self.signature_index: Dict[str, MCTSNode] = {}   # 去重索引
        self.subtree_freq: Dict[str, int] = {}           # 子树模式频率（AlphaAgent 同构检测）
        self.best_node: MCTSNode = self.root             # 全局最优
    
    def select(self, mode: str = 'bayesian_ucb') -> MCTSNode:
        """
        从根开始选择最优路径，直到叶节点。
        mode='bayesian_ucb': 贝叶斯先验 × UCB（AlphaPROBE 方案）
        mode='puct': PUCT 变体（AlphaCFG 方案）
        """
        ...
    
    def expand(self, node: MCTSNode, n_branches: int = 3,
               cfg: Optional[CFGGrammar] = None) -> List[MCTSNode]:
        """
        为叶节点生成子节点。
        cfg: 上下文无关文法约束（AlphaCFG 方案），过滤语法无效的变异
        """
        ...
    
    def backpropagate(self, node: MCTSNode, fitness: float):
        """从叶节点向根反向传播，更新 visit_count 和 total_value"""
        ...
    
    def bayesian_prior(self, node: MCTSNode, gamma: float = 0.05,
                       beta: float = 0.01) -> float:
        """
        贝叶斯先验（AlphaPROBE）:
        P(F) = Normalized_Quality × (1-γ)^depth × (1-β)^outdegree
        """
        ...
    
    def diversity_3d(self, node: MCTSNode, existing_pool: List[MCTSNode]) -> float:
        """
        三维多样性（AlphaPROBE）:
        ValueDiv(皮尔逊) × SemDiv(语义余弦) × SynDiv(编辑距离)
        """
        ...
    
    def is_subtree_frequent(self, node: MCTSNode, threshold: int = 5) -> bool:
        """
        频繁子树检测（AlphaJungle）：子树模式出现超阈值则标记回避
        """
        ...
```

### 3.3 树结构示例

```
根: cs_rank(ts_roc(CLOSE,20))  [fitness=0.880, visit=100]
├── 变异: 参数调整 → cs_rank(ts_roc(CLOSE,40))  [fitness=0.750, visit=30]
│   ├── 变异: 替换变量 → cs_rank(ts_roc(HIGH,40))  [fitness=0.620, visit=8]
│   │   └── 变异: 嵌套函数 → cs_rank(ts_roc(ts_mean(HIGH,5),40))  [fitness=0.910, visit=3]
│   └── 变异: 外包cs_rank → cs_rank(cs_rank(ts_roc(CLOSE,40)))  [fitness=0.550, visit=5]
│       └── 变异: 条件门控 → ifelse(ts_std(CLOSE,20)>0.01, cs_rank(ts_roc(CLOSE,40)), 0)  [fitness=1.200, visit=2]
│           ↑ 从 0.550→1.200！MCTS 反向传播让 cs_rank(cs_rank...) 的 UCB 上升
└── 变异: 外包cs_rank → cs_rank(cs_rank(ts_roc(CLOSE,20)))  [fitness=0.800, visit=25]
    └── 变异: 加条件 → ifelse(ts_std(CLOSE,20)>0.01, cs_rank(ts_roc(CLOSE,20)), 0)  [fitness=1.350, visit=12]
```

---

## 四、核心循环：4 步详解

### 第 1 步：Selection（选路）— 贝叶斯增强 UCB

**目标**：从根节点出发，每次选择最优子节点，直到叶节点。

#### 4.1.1 标准 UCB（基础版）

```
UCB(node) = Q(node) + C × sqrt(ln(N_parent) / N_node)
  
  其中：
    Q(node) = total_value / visit_count  (平均价值)
    C = UCB 常数（默认 1.414，越大越探索）
```

#### 4.1.2 贝叶斯增强 UCB（AlphaPROBE 方案，推荐）

核心思路：Selection 不只是看 Q 值，还考虑该节点作为"父因子"的**先验潜力**——高质量 + 未被过度使用 + 不太深。

```python
def bayesian_enhanced_ucb(node: MCTSNode, parent_visits: int,
                          C: float = 1.414,
                          gamma: float = 0.05,   # 深度惩罚
                          beta: float = 0.01) -> float:   # 出度惩罚
    """AlphaPROBE 风格的贝叶斯增强 UCB"""
    if node.visit_count == 0:
        # 未访问节点：用父节点 Q + 先验作为初值（优于 float('inf')）
        if node.parent:
            return node.parent.total_value / max(node.parent.visit_count, 1) + C
        return C * 2
    
    # 标准 UCB 项
    Q = node.total_value / node.visit_count
    explore = C * math.sqrt(math.log(parent_visits) / node.visit_count)
    
    # 贝叶斯先验乘子（AlphaPROBE）
    # P(F) = Normalized_Quality × (1-γ)^depth × (1-β)^outdegree
    prior = node.prior_quality * ((1 - gamma) ** node.depth) * ((1 - beta) ** node.outdegree)
    
    return Q * prior + explore
```

**直觉**：
- `(1-γ)^depth`：越深层的因子过拟合风险越高，prior 打折
- `(1-β)^outdegree`：被频繁用作父因子 → 该方向已充分探索，鼓励另辟蹊径

#### 4.1.3 PUCT 变体（AlphaCFG 方案，高阶可选）

```python
def puct_score(node: MCTSNode, parent_visits: int, c_puct: float = 1.0) -> float:
    """
    PUCT = Q(node) + c_puct × prior_prob × sqrt(N_parent) / (1 + N_node)
    
    适用场景：当有策略网络能预测"该变异方向的好坏"时，
    prior_prob 由网络给出，比均匀先验更有效。
    """
    Q = node.total_value / max(node.visit_count, 1)
    prior_prob = node.prior_quality  # 由 Tree-LSTM 策略网络预测
    return Q + c_puct * prior_prob * math.sqrt(parent_visits) / (1 + node.visit_count)
```

#### 选择过程

```
当前路径：根 → A → B → ？
  计算 B 的所有子节点的贝叶斯增强 UCB
  选得分最高的子节点
  
  如果 B 无子节点 → B 就是叶节点，进入 Step 2（Expansion）

关键：贝叶斯先验让选择不再是"唯 Q 值论"——
      深度过深、出度过高的路径会被系统性打折
```

### 第 2 步：Expansion（扩路）— CFG 约束 + 频繁子树回避

**目标**：从叶节点出发，生成 N 个变异子节点。

#### 4.2.1 变异策略（复用 v5 + 扩展）

| 变异类型 | 操作 | 来源 |
|:--------|:----|:----|
| 参数调整 | 改窗口/常数 | v5 `_mutate_param` |
| 子树替换 | 替换一个子树为随机新树 | v5 `_mutate_subtree` |
| 逻辑变异 | and↔or / 加/删 not | v5 `_mutate_logic` |
| 条件插入 | 用 if-else 包裹 | v5 `_mutate_insert_condition` |
| 变量替换 | 替换一个变量 | 新增 |
| 函数嵌套 | 在叶子上加一层函数 | 新增 |
| 结构简化 | 去除冗余嵌套 | 新增 |
| 嫁接变异 | 从全局最优池取子树嫁接到当前节点 | 新增（替代交叉） |

#### 4.2.2 CFG 语法约束（AlphaCFG 方案）

问题：GP/随机变异产生大量**语法合法但语义冗余**的表达式——如 `x+0`, `x*1`, `cs_rank(cs_rank(...))`。

方案：用**上下文无关文法（CFG）**定义三层约束空间：

| 层次 | 含义 | 内容 |
|:----|:-----|:-----|
| $\mathcal{L}_{\text{syn}}$ | 语法有效 | 算子元数正确、类型匹配 |
| $\mathcal{L}_{\text{sem}}$ | 语义可解释 | 必须含数据变量、无冗余恒等变换、算子领域合理性 |
| $\mathcal{L}_{\text{sem}}^{\leq K}$ | 深度受限 | 再加 AST 深度上限 K，确保搜索可行 |

```python
def expand_with_cfg(node: MCTSNode, n_branches: int = 3,
                    cfg: CFGGrammar, max_depth: int = 6) -> List[MCTSNode]:
    """
    CFG 约束下的扩展：
      1. 从变异策略池中随机选 n_branches 种策略
      2. 每种策略生成候选表达式
      3. 通过 CFG 语法检查 → 过滤语法无效候选
      4. 通过语义约束检查 → 过滤冗余表达式（如 x+0, x*1, x/x）
      5. 通过深度检查 → 过滤超 max_depth 候选
      6. 子树同构去重（见 4.2.3）
      7. 频繁子树回避（见 4.2.4）
      8. 返回有效子节点列表
    """
```

#### 4.2.3 AST 子树同构检测（AlphaAgent 方案，KDD 2025）

不满足于简单的 signature 字符串匹配——检测 AST 子树的**结构同构**：

```python
def compute_subtree_hash(node: ast.Expression) -> str:
    """
    计算规范化 AST 子树的哈希值。
    同一结构不同变量名的表达式会被映射到同一哈希（先规范化变量名）。
    
    例如：
      cs_rank(ts_roc(CLOSE, 20)) 和 cs_rank(ts_roc(HIGH, 10))
      → 规范化：cs_rank(ts_roc(VAR, N)) → 同一哈希
      → 检测到结构同构，即使参数不同
    """
    
def is_novel_enough(node: MCTSNode, existing_pool: List[MCTSNode],
                    sim_threshold: float = 0.85) -> bool:
    """
    AlphaAgent 式的新颖性检查：
      1. 子树哈希是否与已有因子高度重合
      2. 若相似度 > sim_threshold → 拒绝（防止拥挤）
    """
```

#### 4.2.4 频繁子树回避（AlphaJungle 方案）

在因子库规模增长后，某些子树模式（如 `ts_roc(CLOSE, N)`）会大量出现。AlphaJungle 通过挖掘频繁子树模式，**明确要求变异算子避免使用高频子树**。

```python
class FrequentSubtreeMonitor:
    """
    维护全局子树频率表。
    当某子树模式出现次数超过阈值（如 5 次），
    变异算子在选择子树结构时降低该模式的权重。
    """
    def __init__(self, threshold: int = 5):
        self.freq_table: Dict[str, int] = {}  # 规范化子树哈希 → 频率
        self.threshold = threshold
    
    def is_frequent(self, subtree_hash: str) -> bool:
        return self.freq_table.get(subtree_hash, 0) >= self.threshold
    
    def get_avoidance_weight(self, subtree_hash: str, base_weight: float = 1.0) -> float:
        """频繁子树权重衰减：出现次数越多，权重越低"""
        count = self.freq_table.get(subtree_hash, 0)
        if count < self.threshold:
            return base_weight
        return base_weight / (1 + math.log(1 + count - self.threshold))
```

### 第 3 步：Evaluation（评估）— GT-Score 防过拟合

**目标**：评估新生成的子节点的 fitness。

#### 4.3.1 标准评估管道（复用 v5）

```python
def evaluate(node: MCTSNode, evaluator, fitness_calculator, data) -> float:
    """
    1. evaluator(data, node.tree) → 因子值面板
    2. fitness_calculator.compute(因子值面板) → fitness 标量
    3. 写入缓存（复用 v5 FitnessCache）
    4. 返回 fitness
    """
```

#### 4.3.2 GT-Score 增强评估（2602.00080，已开源）

**核心问题**：传统 fitness（IC/Sharpe/Sortino）在优化过程中会自动"追高"训练集表现，选出过拟合参数。

**GT-Score 公式**：

```
GT_Score = μ · ln(z) · r² / σd

其中：
  μ     = 策略平均收益（基础性能）
  z     = (μ - μ_benchmark) / (σ / √N)  （统计显著性门控）
  r²    = 收益一致性 R²  （惩罚依赖极端行情）
  σd    = 下行标准差  （只惩罚负波动）
```

**核心思想**：不是"跑得最快"重要，是"跑得稳"（统计显著 + 时序一致 + 下行可控）重要。

**实验结果**：Walk-forward 泛化率 36.5%（基线仅 18.5%），即训练集收益保留到样本外的比例翻倍。

```python
def gt_score(returns: np.ndarray, benchmark_returns: np.ndarray,
             min_trades: int = 50) -> float:
    """
    GT-Score 防过拟合目标函数。
    
    若交易次数 < min_trades → 返回高惩罚值
    若 z < 1（未显著跑赢基准） → 返回高惩罚值
    """
    if len(returns) < min_trades:
        return -999.0
    
    mu = np.mean(returns)
    sigma = np.std(returns, ddof=1)
    z = (mu - np.mean(benchmark_returns)) / (sigma / np.sqrt(len(returns)))
    
    if z < 1.0:
        return -999.0  # 不显著的策略直接拒绝
    
    # 收益一致性 r²: 累积收益曲线 vs 理想直线的拟合度
    cum_ret = np.cumsum(returns)
    ideal_line = np.linspace(0, cum_ret[-1], len(returns))
    ss_res = np.sum((cum_ret - ideal_line) ** 2)
    ss_tot = np.sum((cum_ret - np.mean(cum_ret)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
    # 下行标准差
    downside = returns[returns < 0]
    sigma_d = np.std(downside, ddof=1) if len(downside) > 1 else sigma
    
    return mu * np.log(z) * max(r_squared, 0.01) / max(sigma_d, 1e-8)
```

#### 4.3.3 Fitness 策略

| 场景 | 推荐 fitness |
|:----|:------------|
| P0 快速验证 | 标准 IC / Rank IC（简单直接） |
| P1 深度搜索 | GT-Score（防过拟合，泛化率 +98%） |
| 组合层面 | EFS 式联合优化（因子挖掘+组合稀疏性联合目标） |

**关键点**：MCTS 串行评估，一次只评估一个节点（非批量）。但每次评估都是定向搜索，价值密度高于 GP 的随机变异。

### 第 4 步：Backpropagation（反向传播）

**目标**：将新评估的 fitness 沿路径一路向上传播，更新所有祖先节点的统计。

```
反向传播流程：

  叶节点 C(1.200) 评估完成 →
    C.visit_count += 1
    C.total_value += 1.200
  
  父节点 B:
    B.visit_count += 1
    B.total_value += 1.200（C 的 fitness）
  
  祖父节点 A:
    A.visit_count += 1
    A.total_value += 1.200
  
  根节点:
    root.visit_count += 1
    root.total_value += 1.200
  
  结果：
    C 的 Q = 1.200
    B 的 Q = (0.550 + 1.200) / 2 = 0.875  ← 上升！
    A 的 Q = 更新
    root 的 Q = 更新

  虽然 B 自己只有 0.550，但它是通往 C(1.200) 的必经之路
  → B 的 UCB 上升 → 下次 Selection 更可能选 B
  → 系统会继续探索 B 这条路径
  → 这是 GP 做不到的时序信用分配
```

---

## 五、UCB 变体汇总（详见 §4.1）

| 变体 | 公式 | 适用场景 | 来源 |
|:----|:-----|:---------|:-----|
| 标准 UCB | Q + C×√(lnN/n) | 基线 | 经典 MCTS |
| 贝叶斯增强 UCB | Q×prior + C×√(lnN/n), prior=(1-γ)^d×(1-β)^k | **推荐默认** | AlphaPROBE |
| PUCT | Q + c_puct×prior×√N/(1+n) | 有策略网络时 | AlphaCFG |

### 一致性惩罚（金融适配）

金融市场 reward 非平稳，单次高 IC 可能是运气。建议在 Q 值中加入一致性惩罚：

```python
def consistency_adjusted_Q(values: List[float]) -> float:
    """如果节点被多次访问，用 reward 序列的稳定性打折 Q"""
    if len(values) < 3:
        return np.mean(values)
    cv = np.std(values) / (abs(np.mean(values)) + 1e-8)  # 变异系数
    consistency = 1.0 / (1.0 + cv)  # 越稳定越接近 1
    return np.mean(values) * consistency
```

---

## 六、变异策略池

### 6.1 复用 v5 算子

直接调用 v5 的 `tree_gen.py` 已有变异函数：

```python
from utils.gp.v5.tree_gen import (
    _mutate_subtree,
    _mutate_param,
    _mutate_logic,
    _mutate_insert_condition,
)
```

### 6.2 新增算子

| 算子 | 操作 | 来源 |
|:----|:----|:----|
| `_mutate_variable` | 将树中某个变量替换为另一个变量 | 新增 |
| `_mutate_nest` | 在叶子/子树上加一层函数包装 | 新增 |
| `_mutate_simplify` | 简化冗余嵌套（反变异） | 新增 |
| `_mutate_graft` | 从全局最优池取子树嫁接到当前节点 | 新增（替代交叉） |

### 6.3 嫁接变异（弥补 MCTS 无交叉）

```python
def _mutate_graft(node: MCTSNode, best_pool: List[MCTSNode], 
                  max_tries: int = 5) -> Optional[MCTSNode]:
    """
    从全局最优池中随机取一个节点，摘取其子树嫁接到当前节点。
    
    这是 MCTS 结构下对"交叉"的最优替代：
    - GP 的交叉：两个个体的子树随机交换
    - MCTS 嫁接：最优池的子树 → 当前路径的叶节点
    
    避免了纯 MCTS 的"只能沿一条路走下去"的局限。
    """
    for _ in range(max_tries):
        donor = random.choice(best_pool)
        graft_point = random.choice(get_all_subtrees(node.tree))
        donor_subtree = random.choice(get_all_subtrees(donor.tree))
        
        new_tree = replace_subtree(node.tree, graft_point, donor_subtree)
        if is_valid_cfg(new_tree):  # CFG 检查
            return MCTSNode(tree=new_tree, edge=f'graft_from_{donor.signature}')
    return None
```

### 6.4 LLM 引导变异（可选增强）

```python
def llm_guided_mutation(expression: str, llm_client) -> List[str]:
    """
    LLM 分析因子含义后，建议 3 个有意义的修改方向
    
    示例：
      输入: "cs_rank(ts_roc(CLOSE,20))"
      LLM 输出:
        1. "cs_rank(ts_roc(AMOUNT,20))"  # 量代替价
        2. "cs_rank(ts_roc(CLOSE,40))"   # 更长窗口
        3. "cs_rank(ts_roc(CLOSE,20)) * ts_std(CLOSE,20)"  # 乘波动率
    """
```

### 6.5 权重聚焦（复用 v5 TreeGenConfig）

```python
# 变异时的权重偏置，复用 v5 的权重聚焦机制
cfg = TreeGenConfig(
    var_weights={'AMOUNT': 3, 'VOLUME': 2},
    ts_weights={'ts_rank': 3, 'ts_mean': 2, 'ts_std': 1},
    func_allowlist={'ts_rank', 'ts_mean', 'ts_std', 'ts_roc', 'ts_cov'},
)
```

---

## 七、完整循环流程

```python
class MCTSEngine:
    """
    MCTS 因子搜索引擎
    
    MCTS 不是 GP——没有种群、没有选择、没有交叉。
    它是树搜索：评估一条路径 → 更新路径估值 → 根据估值决定下一步往哪走
    """
    
    def __init__(self, 
                 evaluator,                # 复用 v5 的 evaluator
                 fitness_calculator,        # 复用 v5 的 fitness_calculator
                 data,                      # 数据
                 seed_expressions: List[str],  # 种子因子
                 tree_gen_config: TreeGenConfig,  # 复用 v5 的权重聚焦
                 config: dict = None):      # 引擎参数
        ...
    
    def run(self, n_iterations: int = 1000) -> MCTSReport:
        """
        主循环
        
        流程：
          for i in range(n_iterations):
            leaf = self.tree.select()          # Step 1: UCB 选路
            children = self.tree.expand(leaf)  # Step 2: 变异扩路
            for child in children:
                fitness = self.evaluate(child) # Step 3: 评估
                self.tree.backpropagate(child, fitness)  # Step 4: 反向传播
            
            # 可选：每 N 轮打印日志
            if i % 50 == 0:
                self.log_progress(i)
        """
```

---

## 八、对比各范式差异

### 8.1 GP vs MCTS vs DAG vs Code-Level

| 维度 | GP (v5) | MCTS (本文) | DAG进化 (AlphaPROBE) | 代码级 (CogAlpha/XAlpha) |
|:----|:-------|:-----------|:--------------------|:------------------------|
| **核心机制** | 种群进化 + 选择淘汰 | 树搜索 + 反向传播 | DAG搜索 + 贝叶斯检索 | LLM生成代码 + 多Agent审查 |
| **搜索方式** | 每代 200 个随机变异（广度） | 每次走一条路（深度） | 全局拓扑引导（广度+深度） | 思路→代码链式推理 |
| **并行性** | ✅ 高 | ❌ 低（串行） | ⚠️ 中（DAG节点可部分并行） | ❌ 极低（LLM串行推理） |
| **下坡路保护** | ❌ 无 | ✅ 反向传播 | ✅ DAG保留所有进化链 | ✅ 记忆系统保留失败经验 |
| **记忆** | ❌ 无 | ✅ 树结构 | ✅ DAG拓扑（更丰富） | ✅ 报告+经验双重记忆 |
| **方向选择** | 随机（概率偏置） | 价值驱动（UCB） | 贝叶斯后验驱动 | LLM认知推理驱动 |
| **交叉** | ✅ 有 | ❌ 无（用嫁接替代） | ⚠️ DAG天然交叉 | ✅ 轨迹级交叉 |
| **防过拟合** | ❌ 无内置 | GT-Score | 深度+出度惩罚 | 三对齐验证 |
| **多样性** | ❌ 弱 | 频繁子树回避 | 三维多样性度量 | 多Agent多视角审查 |
| **LLM成本** | 高（每代200次） | 低（每次1条路径） | 中（Analyst+Executor+Validator） | 极高（每次多轮推理） |
| **实现复杂度** | 中等 | 中低 | 高 | 极高 |
| **A股验证** | ✅ | 🔲 待验证 | ✅ CSI300/500/1000 | ✅ CSI300 |
| **开源** | ✅ | 🔲 | ✅ | ❌ |
| **有效因子率** | ~30% | 🔲 | 3×基线 ICIR | 优于所有基线 |

### 8.2 互补关系（不变）

```
GP 适合：      宽探索 → 找"哪里可能有鱼"
MCTS 适合：    深挖掘 → 找到鱼后"怎么钓最多"
DAG 适合：     结构化记录 → 保存每条进化链的谱系信息
代码级 适合：  复杂逻辑 → LLM 原生优势（条件分支/多步计算）

最佳实践：
  Step 1: GP 跑 20 代 → 找到 10 个有潜力的因子（AST 公式）
  Step 2: MCTS 对每个因子深挖 100 步 → 找到最优 AST 变体
  Step 3: 对 top-3 冠军用代码级 LLM 精调 → 转化为可执行 Python 策略
```

---

## 九、MCTS vs v5/v6 的协作

### 9.1 MCTS 作为 v5/v6 的补充

```
ft2/utils/gp/
├── v5/               # GP 引擎（宽探索）
├── v6/               # AURORA GP（广撒网）
└── mcts/             # MCTS 引擎（深挖掘）← 新增
```

### 9.2 三种引擎的协作模式

```
v5（宽探索）：
  种群 500 × 40 代 → 找到 10 个方向
  → 输出 top-10 种子

v6（广撒网）：
  Archive 300 × 持续积累 → 保持 60+ 方向的多样性
  → 输出方向覆盖报告

MCTS（深挖掘）：
  对每个种子深挖 100 步 → 找到最优变体
  → 输出每个方向的深度优化结果
```

### 9.3 复用 v5 基础设施

| 组件 | 复用方式 |
|:----|:--------|
| `tree_gen.py` 变异算子 | 直接调用 `_mutate_subtree / _mutate_param / _mutate_logic / _mutate_insert_condition` |
| `config.py TreeGenConfig` | 作为变异时的权重偏置配置 |
| `config.py Individual` | 可复用（MCTSNode 可包含 Individual） |
| `cache.py FitnessCache` | 直接复用，跨 GP 和 MCTS 共享缓存 |
| `ast_utils.py` 工具函数 | 直接复用 `_simplify_ast / _canonicalize_key / _expr_str` |
| evaluator + fitness_calculator | 完全复用，接口一致 |

---

## 十、实现优先级

### P0：核心骨架（可运行）

```
文件：mcts/engine.py
  MCTSNode 数据结构（含 bayesian prior 字段）
  MCTSTree 管理类（select / expand / backpropagate）
  MCTSEngine 主循环
  标准 UCB + 贝叶斯增强 UCB
  复用 v5 变异算子

文件：mcts/constraints.py
  CFGGrammar 语法约束定义
  _check_semantic_validity（过滤 x+0, x*1, x/x 等冗余）
  _check_depth_constraint

文件：mcts/dedup.py
  AST 子树同构检测（AlphaAgent 方案）
  FrequentSubtreeMonitor（AlphaJungle 方案）

文件：mcts/__init__.py
  统一导出
```

### P1：防过拟合增强

```
GT-Score 评估器（2602.00080）
  替代或平行于纯 IC/Sharpe fitness
  默认用于深度搜索阶段的评估

三维多样性度量（AlphaPROBE 方案）
  ValueDiv（皮尔逊）+ SemDiv（语义余弦）+ SynDiv（编辑距离）
  用于 Expansion 阶段去重筛选
```

### P2：并行与集成

```
LLM 引导变异（可选）
  llm_guided_mutation.py

并行多树 + Virtual Loss
  多线程并行评估，用 Virtual Loss 避免路径冲突
  每个种子独立一棵 MCTS 树 → 并行跑

早停机制
  全局最优连续 N 步无提升 + 当前路径连续 M 步下降 → 双条件早停

与 v5/v6 集成
  v5 冠军 → MCTS 深挖
  MCTS 最优路径 → v5 种子增强
```

---

## 十一、关键参数

| 参数 | 默认 | 说明 |
|:----|:----|:-----|
| `n_iterations` | 1000 | 总搜索步数 |
| `selection_mode` | `bayesian_ucb` | 选择模式：`ucb`/`bayesian_ucb`/`puct` |
| `ucb_constant` | 1.414 | 探索-利用平衡 |
| `n_branches` | 3 | 每次扩路生成子节点数 |
| `max_depth` | 10 | 树最大深度 |
| `gamma` | 0.05 | 贝叶斯深度惩罚系数（每深一层 prior×0.95） |
| `beta` | 0.01 | 贝叶斯出度惩罚系数 |
| `fitness_mode` | `ic` | `ic`/`sharpe`/`gt_score`（P1 推荐 gt_score） |
| `enable_cfg` | True | 是否启用 CFG 语法约束 |
| `enable_subtree_avoid` | True | 是否启用频繁子树回避 |
| `freq_subtree_threshold` | 5 | 频繁子树阈值 |
| `enable_graft` | False | 是否启用嫁接变异 |
| `llm_guided` | False | 是否启用 LLM 引导变异 |
| `parallel_trees` | 1 | 并行搜索的树数量 |
| `early_stop_rounds` | 50 | 全局最优连续 N 步无提升则早停 |
| `early_stop_path_rounds` | 20 | 当前路径连续 M 步下降 → 放弃该路径 |

---

## 十二、投入评估

```
✅ 论文已验证 MCTS 因子搜索可行：
  AlphaJungle (清华, 2505): MCTS+LLM > 纯LLM > GP，频繁子树回避有效
  AlphaCFG (2601): CFG约束+MCTS+Tree-LSTM，已开源，CSI300实测
  AlphaPROBE (2602): DAG+贝叶斯检索，已开源，CSI300 ICIR 3×基线

✅ MCTS 解决了 GP 的 3 个核心问题（被多篇论文独立证实）：
  1. 下坡路抛弃 → 反向传播天然保护中介状态
  2. 无记忆 → 树结构记录所有路径
  3. 盲目变异 → UCB/贝叶斯先验引导方向选择

✅ 复用 v5 基础设施，增量成本低：
  变异算子、权重配置、缓存、评估管道全部复用
  代码量 ~400 行核心 + 200 行集成

✅ 本方案相对论文的增量贡献：
  - 贝叶斯增强 UCB（AlphaPROBE 的 Selection 策略入 MCTS）
  - CFG 语法约束（AlphaCFG 的语义层约束入变异）
  - GT-Score 防过拟合（替代纯 IC/Sharpe）
  - 嫁接变异（弥补 MCTS 无交叉的缺陷）
  - 保持 AST 运算效率优于代码级 LLM

⚠️ 需要接受的 tradeoff：
  MCTS 串行执行（但每次是定向搜索，价值密度高）
  MCTS 不是 GP（没有种群/交叉/选择）
  MCTS 适合深挖掘，不适合宽探索（种子来自 GP）

❌ MCTS 不适合的场景：
  从零开始搜（无种子时效率低）→ 用 GP 产出种子
  需要大量并行评估时 → 用 GP 做宽探索
  需要复杂多步逻辑（如 if-else 链条）→ 用代码级 LLM 精调
```

---

## 十三、参考文献

| 论文 | ID | 核心贡献 | 与本方案关系 |
|:-----|:---|:---------|:------------|
| **AlphaJungle** (清华) | 2505.11122 | 首次验证 LLM+MCTS 因子挖掘，频繁子树回避 | 频繁子树回避机制 |
| **AlphaCFG** | 2601.22119 | CFG语法约束 + Tree-LSTM + PUCT-MCTS | CFG约束、PUCT变体 |
| **AlphaPROBE** | 2602.11917 | DAG进化 + 贝叶斯检索 + 3D多样性 | 贝叶斯先验、三维多样性 |
| **AlphaAgent** (KDD 2025) | 2502.16789 | 三重正则化 + AST子树同构 | 子树同构去重 |
| **GT-Score** | 2602.00080 | 防过拟合复合目标函数 μ·ln(z)·r²/σd | 替代纯IC/Sharpe |
| **QuantaAlpha** | 2602.07085 | 轨迹级进化 + 跨市场迁移 | 轨迹交叉思路 |
| **连续程序搜索** | 2602.07659 | DAE学习程序隐空间 + 几何编译变异 | GP局部性问题佐证 |
| **EFS** | 2507.17211 | 因子挖掘+稀疏组合联合优化 | 组合级fitness方向 |
| **CogAlpha** (港大) | 2511.18850 | 7层Agent + 代码级因子 > AST公式 | 代码级vs公式级讨论 |
| **XAlpha** (港大) | 2607.08332 | 三脑架构 + 报告驱动记忆 | 记忆系统参考 |