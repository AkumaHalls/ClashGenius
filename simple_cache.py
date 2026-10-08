import logging
import time
from collections import OrderedDict
from typing import Any, Callable, Optional

logger = logging.getLogger("simple_cache")


class SimpleCache:
    """Cache em memória com TTL, limite de tamanho, evicção LRU e estatísticas."""

    def __init__(self, default_ttl: int = 30, maxsize: int = 500):
        if maxsize <= 0:
            raise ValueError(f"maxsize deve ser > 0, recebido {maxsize!r}")
        if default_ttl <= 0:
            raise ValueError(f"default_ttl deve ser > 0, recebido {default_ttl!r}")
        # OrderedDict: a ordem é a recência de acesso (LRU = início da fila).
        self._store: "OrderedDict[str, dict]" = OrderedDict()
        self.default_ttl = default_ttl
        self.maxsize = maxsize
        self._hits = 0
        self._misses = 0
        # Relógio injetável (monotonic) para testes controlarem a expiração.
        self._clock: Callable[[], float] = time.monotonic

    # ------------------------------------------------------------------
    # API pública (idêntica à versão anterior)
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if self._clock() >= entry["expires"]:
            del self._store[key]
            self._misses += 1
            return None
        self._store.move_to_end(key)
        self._hits += 1
        return entry["data"]

    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        if ttl is not None and ttl <= 0:
            raise ValueError(f"ttl deve ser > 0, recebido {ttl!r}")
        if key not in self._store and len(self._store) >= self.maxsize:
            self._evict()
        self._store[key] = {
            "data": data,
            "expires": self._clock() + (ttl if ttl is not None else self.default_ttl),
        }
        self._store.move_to_end(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def delete_by_prefix(self, prefix: str) -> None:
        to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in to_delete:
            del self._store[k]
        if to_delete:
            logger.info("delete_by_prefix(%r): removidas %d chaves", prefix, len(to_delete))

    def clear(self) -> None:
        count = len(self._store)
        self._store.clear()
        if count:
            logger.info("clear: removidas %d chaves", count)

    def size(self) -> int:
        now = self._clock()
        return sum(1 for e in self._store.values() if e["expires"] > now)

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total * 100, 1) if total else 0.0,
            "stored": len(self._store),
            "valid": self.size(),
            "maxsize": self.maxsize,
        }

    def _evict(self) -> None:
        """Purga expirados e, se ainda cheio, remove o menos recentemente usado."""
        now = self._clock()
        expired = [k for k, v in self._store.items() if v["expires"] <= now]
        for k in expired:
            del self._store[k]

        while len(self._store) >= self.maxsize:
            lru_key, _ = self._store.popitem(last=False)
            logger.warning(
                "_evict: cache cheio (%d/%d), removendo LRU %r",
                len(self._store) + 1,
                self.maxsize,
                lru_key,
            )


cache = SimpleCache(default_ttl=30)
