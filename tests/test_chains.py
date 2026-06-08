"""Unit tests for multi-chain configuration — Days 19-25."""
import pytest
from chainobserver.chains import (
    get_chain, get_default_rpc, explorer_tx_url, explorer_address_url,
    CHAINS, SUPPORTED_CHAIN_IDS
)


class TestChainConfig:
    @pytest.mark.unit
    @pytest.mark.parametrize("chain_id,name", [
        (1, "Ethereum"),
        (42161, "Arbitrum One"),
        (8453, "Base"),
        (10, "Optimism"),
        (137, "Polygon"),
    ])
    def test_chain_name(self, chain_id, name):
        assert get_chain(chain_id).name == name

    @pytest.mark.unit
    @pytest.mark.parametrize("chain_id", [1, 42161, 8453, 10, 137])
    def test_chain_has_rpc(self, chain_id):
        cfg = get_chain(chain_id)
        assert cfg.rpc_url.startswith("http")

    @pytest.mark.unit
    @pytest.mark.parametrize("chain_id", [1, 42161, 8453, 10, 137])
    def test_chain_has_explorer(self, chain_id):
        cfg = get_chain(chain_id)
        assert cfg.explorer_url.startswith("https://")

    @pytest.mark.unit
    def test_unsupported_chain_raises(self):
        with pytest.raises(ValueError, match="Unsupported chain_id"):
            get_chain(999)

    @pytest.mark.unit
    def test_all_chains_in_supported_list(self):
        for cid in SUPPORTED_CHAIN_IDS:
            assert cid in CHAINS

    @pytest.mark.unit
    def test_explorer_tx_url_format(self):
        url = explorer_tx_url(1, "0xabc")
        assert url == "https://etherscan.io/tx/0xabc"

    @pytest.mark.unit
    def test_explorer_address_url_format(self):
        url = explorer_address_url(42161, "0xdef")
        assert "arbiscan.io/address/0xdef" in url

    @pytest.mark.unit
    def test_arbitrum_tx_url_uses_arbiscan(self):
        url = explorer_tx_url(42161, "0x123")
        assert "arbiscan.io" in url

    @pytest.mark.unit
    def test_base_tx_url_uses_basescan(self):
        url = explorer_tx_url(8453, "0x456")
        assert "basescan.org" in url

    @pytest.mark.unit
    def test_polygon_native_token_is_matic(self):
        assert get_chain(137).native_token == "MATIC"

    @pytest.mark.unit
    def test_ethereum_native_token_is_eth(self):
        assert get_chain(1).native_token == "ETH"

    @pytest.mark.unit
    def test_get_default_rpc_uses_env_for_mainnet(self, monkeypatch):
        monkeypatch.setenv("ETH_RPC_URL", "https://custom.rpc.example.com")
        assert get_default_rpc(1) == "https://custom.rpc.example.com"

    @pytest.mark.unit
    def test_get_default_rpc_ignores_env_for_l2(self, monkeypatch):
        monkeypatch.setenv("ETH_RPC_URL", "https://custom.rpc.example.com")
        # L2 uses its own RPC regardless of ETH_RPC_URL
        rpc = get_default_rpc(42161)
        assert rpc != "https://custom.rpc.example.com"
        assert "arbitrum" in rpc.lower() or "arb" in rpc.lower()
