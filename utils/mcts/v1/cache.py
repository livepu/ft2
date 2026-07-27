"""
utils/mcts/v1/cache.py — 简单内存缓存（独立，不依赖 v5 FitnessCache）
"""

from typing import Dict, Optional, Tuple


class SimpleFitnessCache:
    """简单的内存缓存：signature → (fitness, depth, node_count)

    替代 v5 的 FitnessCache（内存+SQLite双级），
    MCTS 场景下只需要内存缓存即可（搜索规模远小于 GP 种群）。
    """

    def __init__(self):
        self._cache: Dict[str, Tuple[float, int, int]] = {}

    def get(self, key: str) -> Optional[Tuple[float, int, int]]:
        """查询缓存，命中返回 (fitness, depth, nodes)，否则 None"""
        return self._cache.get(key)

    def put(self, key: str, value: Tuple[float, int, int]):
        """写入缓存"""
        self._cache[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    def clear(self):
        """清空缓存"""
        self._cache.clear()
