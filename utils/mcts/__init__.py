"""
utils/mcts/ — MCTS 因子搜索引擎（深挖掘），与 gp/ 同级

文献基础:
  AlphaJungle (2505.11122), AlphaCFG (2601.22119), AlphaPROBE (2602.11917)

架构定位:
  v5 GP → 宽探索（找种子）
  v6 AURORA → 广撒网（保持多样性）
  mcts/v1 → 深挖掘（对种子深度优化）
"""
