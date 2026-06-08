"""Unit tests for DiagnosisCache — Days 26-40 production hardening."""
import pytest, time, threading
from chainobserver.cache import DiagnosisCache


@pytest.mark.unit
class TestDiagnosisCache:
    def test_miss_returns_none(self):
        c = DiagnosisCache()
        assert c.get("0xabc", 1) is None

    def test_set_then_get(self):
        c = DiagnosisCache()
        c.set("0xabc", 1, {"result": "ok"})
        assert c.get("0xabc", 1) == {"result": "ok"}

    def test_different_chain_is_separate_entry(self):
        c = DiagnosisCache()
        c.set("0xabc", 1, "mainnet")
        c.set("0xabc", 42161, "arbitrum")
        assert c.get("0xabc", 1) == "mainnet"
        assert c.get("0xabc", 42161) == "arbitrum"

    def test_case_insensitive_hash(self):
        c = DiagnosisCache()
        c.set("0xABC", 1, "val")
        assert c.get("0xabc", 1) == "val"

    def test_ttl_expiry(self):
        c = DiagnosisCache(ttl=0)   # instant expiry
        c.set("0xabc", 1, "val")
        time.sleep(0.01)
        assert c.get("0xabc", 1) is None

    def test_maxsize_evicts_oldest(self):
        c = DiagnosisCache(maxsize=2)
        c.set("0x001", 1, "a")
        time.sleep(0.001)
        c.set("0x002", 1, "b")
        time.sleep(0.001)
        c.set("0x003", 1, "c")   # should evict 0x001
        assert c.get("0x001", 1) is None
        assert c.get("0x002", 1) is not None
        assert c.get("0x003", 1) == "c"

    def test_stats_returns_counts(self):
        c = DiagnosisCache()
        c.set("0xaaa", 1, "x")
        c.set("0xbbb", 1, "y")
        s = c.stats()
        assert s["live"] == 2
        assert s["total"] == 2
        assert "capacity" in s

    def test_health_endpoint_includes_cache(self):
        from fastapi.testclient import TestClient
        from server import app
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "cache" in data
        assert "live" in data["cache"]

    def test_diagnose_endpoint_returns_cached_result(self):
        # Pre-seed the module-level singleton so the /diagnose endpoint
        # hits the cache branch (lines 277-279 in server.py) without
        # needing a real Gemini call.
        from fastapi.testclient import TestClient
        from server import app, DiagnoseResponse
        from chainobserver.cache import _cache

        fake = DiagnoseResponse(
            tx_hash="0xcacheddeadbeef" + "0" * 48,
            chain_id=1,
            root_cause="cached slippage",
            failure_type="slippage_exceeded",
            affected_address="0xabc",
            confidence="high",
            fix_suggestion="increase slippage",
            related_link="https://etherscan.io/tx/0xcached",
            diagnosis_time_s=0.001,
            tool_calls=0,
            full_analysis="from cache",
        )
        tx = fake.tx_hash
        _cache.set(tx, 1, fake)

        client = TestClient(app)
        r = client.post("/diagnose", json={"tx_hash": tx, "chain_id": 1})
        # Even without GEMINI_API_KEY the cached path returns 200
        assert r.status_code == 200
        data = r.json()
        assert data["root_cause"] == "cached slippage"
        assert data["failure_type"] == "slippage_exceeded"
        assert data["tool_calls"] == 0   # 0 proves it came from cache, not agent

    def test_concurrent_writes_are_thread_safe(self):
        c = DiagnosisCache(maxsize=1000)
        errors: list[Exception] = []

        def writer(n: int) -> None:
            try:
                for i in range(50):
                    key = f"0x{n:04x}{i:058x}"
                    c.set(key, 1, f"val-{n}-{i}")
                    assert c.get(key, 1) == f"val-{n}-{i}"
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert c.stats()["total"] <= 1000  # maxsize respected
