"""Unit tests for Solana cluster configuration."""
import pytest
from chainobserver.solana_chains import (
    get_cluster, get_default_rpc, explorer_tx_url, explorer_account_url,
    known_program_name, CLUSTERS, SUPPORTED_CLUSTERS,
)


class TestSolanaClusterConfig:
    @pytest.mark.unit
    @pytest.mark.parametrize("cluster,name", [
        ("mainnet-beta", "Solana Mainnet Beta"),
        ("devnet", "Solana Devnet"),
        ("testnet", "Solana Testnet"),
    ])
    def test_cluster_name(self, cluster, name):
        assert get_cluster(cluster).name == name

    @pytest.mark.unit
    @pytest.mark.parametrize("cluster", ["mainnet-beta", "devnet", "testnet"])
    def test_cluster_has_rpc(self, cluster):
        assert get_cluster(cluster).rpc_url.startswith("http")

    @pytest.mark.unit
    def test_all_clusters_native_token_is_sol(self):
        for cluster in SUPPORTED_CLUSTERS:
            assert get_cluster(cluster).native_token == "SOL"

    @pytest.mark.unit
    def test_unsupported_cluster_raises(self):
        with pytest.raises(ValueError, match="Unsupported cluster"):
            get_cluster("localnet")

    @pytest.mark.unit
    def test_all_clusters_in_supported_list(self):
        for cluster in SUPPORTED_CLUSTERS:
            assert cluster in CLUSTERS

    @pytest.mark.unit
    def test_explorer_tx_url_mainnet_has_no_cluster_param(self):
        url = explorer_tx_url("mainnet-beta", "abc123")
        assert url == "https://solscan.io/tx/abc123"

    @pytest.mark.unit
    def test_explorer_tx_url_devnet_has_cluster_param(self):
        url = explorer_tx_url("devnet", "abc123")
        assert "solscan.io/tx/abc123" in url
        assert "cluster=devnet" in url

    @pytest.mark.unit
    def test_explorer_account_url_format(self):
        url = explorer_account_url("mainnet-beta", "def456")
        assert url == "https://solscan.io/account/def456"

    @pytest.mark.unit
    def test_get_default_rpc_uses_env_for_mainnet(self, monkeypatch):
        monkeypatch.setenv("SOLANA_RPC_URL", "https://custom.rpc.example.com")
        assert get_default_rpc("mainnet-beta") == "https://custom.rpc.example.com"

    @pytest.mark.unit
    def test_get_default_rpc_ignores_env_for_devnet(self, monkeypatch):
        monkeypatch.setenv("SOLANA_RPC_URL", "https://custom.rpc.example.com")
        rpc = get_default_rpc("devnet")
        assert rpc != "https://custom.rpc.example.com"
        assert "devnet" in rpc.lower()

    @pytest.mark.unit
    def test_known_program_name_system_program(self):
        assert known_program_name("11111111111111111111111111111111") == "System Program"

    @pytest.mark.unit
    def test_known_program_name_token_program(self):
        assert known_program_name("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA") == "SPL Token Program"

    @pytest.mark.unit
    def test_known_program_name_unrecognized_returns_empty(self):
        assert known_program_name("SomeRandomUnknownProgramId111111111111111") == ""
