from __future__ import annotations

from whitesnout.cache import LRUCache, StatCache


def test_lru_cache_get_miss() -> None:
    cache: LRUCache[str, int] = LRUCache(maxsize=3)
    assert cache.get("missing") is None


def test_lru_cache_get_hit() -> None:
    cache: LRUCache[str, int] = LRUCache(maxsize=3)
    cache.put("a", 1)
    assert cache.get("a") == 1


def test_lru_cache_eviction() -> None:
    cache: LRUCache[str, int] = LRUCache(maxsize=3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    cache.put("d", 4)
    assert cache.get("a") is None
    assert cache.get("d") == 4
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_lru_cache_recently_used_preserved() -> None:
    cache: LRUCache[str, int] = LRUCache(maxsize=3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    cache.get("a")
    cache.put("d", 4)
    assert cache.get("a") == 1
    assert cache.get("b") is None


# --- StatCache ---


def test_stat_cache_get_miss() -> None:
    cache = StatCache(maxsize=3)
    assert cache.get("missing") is None


def test_stat_cache_get_hit() -> None:
    cache = StatCache(maxsize=3)
    cache.put("a", 100, 200)
    assert cache.get("a") == (100, 200)


def test_stat_cache_eviction() -> None:
    cache = StatCache(maxsize=3)
    cache.put("a", 1, 10)
    cache.put("b", 2, 20)
    cache.put("c", 3, 30)
    cache.put("d", 4, 40)
    assert cache.get("a") is None
    assert cache.get("d") == (4, 40)
    assert cache.get("b") == (2, 20)
    assert cache.get("c") == (3, 30)


def test_stat_cache_clear() -> None:
    cache = StatCache(maxsize=3)
    cache.put("a", 1, 10)
    cache.clear()
    assert cache.get("a") is None
