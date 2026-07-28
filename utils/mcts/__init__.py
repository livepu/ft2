"""
utils/mcts/ — MCTS 树搜索引擎（深挖掘），与 gp/ 同级

文献基础:
  AlphaJungle (2505.11122), AlphaCFG (2601.22119), AlphaPROBE (2602.11917)

架构定位:
  v5 GP     → 宽探索（找种子）
  v6 AURORA → 广撒网（保持多样性）
  mcts/v1   → 深挖掘（对种子深度优化）

拆分模式 (对齐 utils/gp/v5):
  utils/mcts/v1/       ← 纯搜索算法 (零评估依赖)
  factor/v5/mcts_engine.py ← 桥接层 (28行, 注入因子 evaluator)
  factor/v5/           ← 纯评估引擎 (FacEngine.backtest)
"""
