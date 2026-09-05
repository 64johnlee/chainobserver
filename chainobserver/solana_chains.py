"""Cluster configuration for ChainObserver Solana (SVM) support."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SolanaClusterConfig:
    cluster: str          # "mainnet-beta", "devnet", "testnet"
    name: str
    rpc_url: str
    explorer_url: str      # https://solscan.io, cluster query param added for non-mainnet
    native_token: str = "SOL"


CLUSTERS: dict[str, SolanaClusterConfig] = {
    "mainnet-beta": SolanaClusterConfig(
        cluster="mainnet-beta",
        name="Solana Mainnet Beta",
        rpc_url="https://api.mainnet-beta.solana.com",
        explorer_url="https://solscan.io",
    ),
    "devnet": SolanaClusterConfig(
        cluster="devnet",
        name="Solana Devnet",
        rpc_url="https://api.devnet.solana.com",
        explorer_url="https://solscan.io",
    ),
    "testnet": SolanaClusterConfig(
        cluster="testnet",
        name="Solana Testnet",
        rpc_url="https://api.testnet.solana.com",
        explorer_url="https://solscan.io",
    ),
}

SUPPORTED_CLUSTERS = list(CLUSTERS.keys())

# Well-known program IDs ChainObserver can name without an on-chain IDL lookup.
KNOWN_PROGRAMS: dict[str, str] = {
    "11111111111111111111111111111111": "System Program",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "SPL Token Program",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": "SPL Token-2022 Program",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL": "Associated Token Account Program",
    "ComputeBudget111111111111111111111111111111": "Compute Budget Program",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM V4",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpools",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter Aggregator V6",
}


def get_cluster(cluster: str) -> SolanaClusterConfig:
    if cluster not in CLUSTERS:
        supported = ", ".join(SUPPORTED_CLUSTERS)
        raise ValueError(f"Unsupported cluster '{cluster}'. Supported: {supported}")
    return CLUSTERS[cluster]


def get_default_rpc(cluster: str) -> str:
    import os
    env_rpc = os.environ.get("SOLANA_RPC_URL", "")
    if env_rpc and cluster == "mainnet-beta":
        return env_rpc
    return get_cluster(cluster).rpc_url


def _cluster_query_suffix(cluster: str) -> str:
    return "" if cluster == "mainnet-beta" else f"?cluster={cluster}"


def explorer_tx_url(cluster: str, signature: str) -> str:
    base = get_cluster(cluster).explorer_url
    return f"{base}/tx/{signature}{_cluster_query_suffix(cluster)}"


def explorer_account_url(cluster: str, address: str) -> str:
    base = get_cluster(cluster).explorer_url
    return f"{base}/account/{address}{_cluster_query_suffix(cluster)}"


def known_program_name(program_id: str) -> str:
    return KNOWN_PROGRAMS.get(program_id, "")
