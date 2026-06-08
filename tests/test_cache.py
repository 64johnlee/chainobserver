"""Unit tests for DiagnosisCache — Days 26-40 production hardening."""
import pytest, time
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
