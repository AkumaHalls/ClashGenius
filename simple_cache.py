import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("simple_cache")


class SimpleCache:
    """Cache em memória com TTL, limite de tamanho, evicção e estatísticas."""

    def __init__(self, default_ttl: int = 30, maxsize: int = 500):
        self._store: Dict[str, dict] = {}
        self.default_ttl = default_ttl
        self.maxsize = maxsize
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # API pública (idêntica à versão anterior)
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if time.time() > entry["expires"]:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry["data"]

    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        if len(self._store) >= self.maxsize:
            self._evict()
        self._store[key] = {
            "data": data,
            "expires": time.time() + (ttl if ttl is not None else self.default_ttl),
        }

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
        now = time.time()
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
        """Remove itens expirados e, se ainda cheio, os 25% mais velhos."""
        now = time.time()
        expired = [k for k, v in self._store.items() if v["expires"] <= now]
        for k in expired:
            del self._store[k]

        if len(self._store) >= self.maxsize:
            sorted_keys = sorted(self._store, key=lambda k: self._store[k]["expires"])
            qtd = max(1, len(self._store) // 4)
            for k in sorted_keys[:qtd]:
                del self._store[k]
            logger.warning(
                "_evict: cache cheio (%d/%d), removidos %d itens mais velhos",
                len(self._store) + len(expired) + qtd,
                self.maxsize,
                len(expired) + qtd,
            )


cache = SimpleCache(default_ttl=30)
