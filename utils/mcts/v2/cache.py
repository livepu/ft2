"""
core/cache.py — 简单内存缓存（v1 搬运，逻辑不变）
=============================================================================

[搬运] 2026-08-06 从 utils/mcts/v1/cache.py 搬运。
"""

from typing import Dict, Optional, Tuple


class SimpleFitnessCache:
    """签名 → (fitness, depth, node_count) 内存缓存"""

    def __init__(self):
        self._cache: Dict[str, Tuple[float, int, int]] = {}

    def get(self, key: str) -> Optional[Tuple[float, int, int]]:
        return self._cache.get(key)

    def put(self, key: str, value: Tuple[float, int, int]):
        self._cache[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    def clear(self):
        self._cache.clear()
