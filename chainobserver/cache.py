"""Simple TTL cache for diagnosis results — avoids re-running Gemini on duplicate tx hashes."""
from __future__ import annotations

import time
from threading import Lock
from typing import Any


_TTL_SECONDS = 300   # 5 minutes
_MAX_ENTRIES = 500


class DiagnosisCache:
    """Thread-safe LRU-ish cache with TTL eviction."""

    def __init__(self, ttl: int = _TTL_SECONDS, maxsize: int = _MAX_ENTRIES) -> None:
        self._ttl = ttl
        self._maxsize = maxsize
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def _cache_key(self, tx_hash: str, chain_id: int | str) -> str:
        # EVM hex tx hashes are case-insensitive; Solana base58 signatures are
        # case-SENSITIVE (distinct upper/lowercase letters are different characters) —
        # lowercasing them would collide two genuinely different signatures.
        normalized = tx_hash.lower() if isinstance(chain_id, int) else tx_hash
        return f"{chain_id}:{normalized}"

    def get(self, tx_hash: str, chain_id: int | str = 1) -> Any | None:
        key = self._cache_key(tx_hash, chain_id)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.monotonic() - ts > self._ttl:
                del self._store[key]
                return None
            return value

    def set(self, tx_hash: str, chain_id: int | str, value: Any) -> None:
        key = self._cache_key(tx_hash, chain_id)
        with self._lock:
            if len(self._store) >= self._maxsize:
                oldest = min(self._store, key=lambda k: self._store[k][0])
                del self._store[oldest]
            self._store[key] = (time.monotonic(), value)

    def stats(self) -> dict[str, int]:
        with self._lock:
            now = time.monotonic()
            live = sum(1 for ts, _ in self._store.values() if now - ts <= self._ttl)
            return {"total": len(self._store), "live": live, "capacity": self._maxsize}


_cache = DiagnosisCache()
