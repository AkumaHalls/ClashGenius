"""Testes do SimpleCache — FIX-19a: LRU real, TTL e validação de parâmetros."""
import pytest

import simple_cache as sc
from simple_cache import SimpleCache


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture()
def clock(monkeypatch):
    c = FakeClock()
    monkeypatch.setattr("simple_cache.time.monotonic", c, raising=True)
    return c


def test_lru_evicts_least_recently_used_not_oldest():
    cache = SimpleCache(default_ttl=100, maxsize=2)
    cache.set("A", "va")
    cache.set("B", "vb")
    assert cache.get("A") == "va"  # A deixa de ser a menos usada
    cache.set("C", "vc")  # deve evictar B (LRU), não A
    assert cache.get("B") is None
    assert cache.get("A") == "va"
    assert cache.get("C") == "vc"


def test_lru_set_overwrite_does_not_evict():
    cache = SimpleCache(default_ttl=100, maxsize=2)
    cache.set("A", "va")
    cache.set("B", "vb")
    cache.set("A", "va2")  # atualizar chave existente não pode ocupar slot extra
    assert cache.size() == 2
    assert cache.get("A") == "va2"
    assert cache.get("B") == "vb"


def test_ttl_expiration_not_served_and_purged(clock):
    cache = SimpleCache(default_ttl=10, maxsize=5)
    cache.set("k", "v")
    assert cache.get("k") == "v"
    clock.advance(11)
    assert cache.get("k") is None  # expirada não serve
    assert "k" not in cache._store  # purgada no acesso
    assert cache.size() == 0


def test_ttl_per_set_respected(clock):
    cache = SimpleCache(default_ttl=100, maxsize=5)
    cache.set("short", "v", ttl=5)
    clock.advance(6)
    assert cache.get("short") is None
    assert cache.get("missing") is None


def test_invalid_maxsize_raises():
    with pytest.raises(ValueError):
        SimpleCache(maxsize=0)
    with pytest.raises(ValueError):
        SimpleCache(maxsize=-1)


def test_invalid_ttl_raises():
    with pytest.raises(ValueError):
        SimpleCache(default_ttl=0)
    with pytest.raises(ValueError):
        SimpleCache(default_ttl=-5)


def test_invalid_set_ttl_raises():
    cache = SimpleCache(default_ttl=10, maxsize=5)
    with pytest.raises(ValueError):
        cache.set("k", "v", ttl=0)
    with pytest.raises(ValueError):
        cache.set("k", "v", ttl=-1)


def test_public_api_unchanged():
    cache = SimpleCache(default_ttl=10, maxsize=3)
    cache.set("a", 1, ttl=5)
    assert cache.get("a") == 1
    assert cache.get("nope") is None
    cache.delete("a")
    assert cache.get("a") is None
    cache.set("p1", 1)
    cache.set("p2", 2)
    cache.delete_by_prefix("p")
    assert cache.size() == 0
    cache.set("z", 9)
    assert cache.size() == 1
    cache.clear()
    assert cache.size() == 0
    stats = cache.stats
    assert {"hits", "misses", "hit_rate", "stored", "valid", "maxsize"} <= set(stats)
    assert isinstance(sc.cache, SimpleCache)
