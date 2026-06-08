"""Chain configuration for ChainObserver multi-chain support."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChainConfig:
    chain_id: int
    name: str
    rpc_url: str
    explorer_url: str           # e.g. https://etherscan.io
    etherscan_api_url: str      # Etherscan V2 API base
    uniswap_v2_factory: str     # 0x0... if not deployed
    uniswap_v3_factory: str
    native_token: str           # ETH, MATIC, etc.


CHAINS: dict[int, ChainConfig] = {
    1: ChainConfig(
        chain_id=1,
        name="Ethereum",
        rpc_url="https://ethereum.publicnode.com",
        explorer_url="https://etherscan.io",
        etherscan_api_url="https://api.etherscan.io/v2/api",
        uniswap_v2_factory="0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
        uniswap_v3_factory="0x1F98431c8aD98523631AE4a59f267346ea31F984",
        native_token="ETH",
    ),
    42161: ChainConfig(
        chain_id=42161,
        name="Arbitrum One",
        rpc_url="https://arb1.arbitrum.io/rpc",
        explorer_url="https://arbiscan.io",
        etherscan_api_url="https://api.etherscan.io/v2/api",
        uniswap_v2_factory="0xf1D7CC64Fb4452F05c498126312eBE29f30Fbcf9",
        uniswap_v3_factory="0x1F98431c8aD98523631AE4a59f267346ea31F984",
        native_token="ETH",
    ),
    8453: ChainConfig(
        chain_id=8453,
        name="Base",
        rpc_url="https://mainnet.base.org",
        explorer_url="https://basescan.org",
        etherscan_api_url="https://api.etherscan.io/v2/api",
        uniswap_v2_factory="0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6",
        uniswap_v3_factory="0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
        native_token="ETH",
    ),
    10: ChainConfig(
        chain_id=10,
        name="Optimism",
        rpc_url="https://mainnet.optimism.io",
        explorer_url="https://optimistic.etherscan.io",
        etherscan_api_url="https://api.etherscan.io/v2/api",
        uniswap_v2_factory="0x0000000000000000000000000000000000000000",
        uniswap_v3_factory="0x1F98431c8aD98523631AE4a59f267346ea31F984",
        native_token="ETH",
    ),
    137: ChainConfig(
        chain_id=137,
        name="Polygon",
        rpc_url="https://polygon-rpc.com",
        explorer_url="https://polygonscan.com",
        etherscan_api_url="https://api.etherscan.io/v2/api",
        uniswap_v2_factory="0x9e5A52f57b3038F1B8EeE45F28b3C1967e22799C",
        uniswap_v3_factory="0x1F98431c8aD98523631AE4a59f267346ea31F984",
        native_token="MATIC",
    ),
}

SUPPORTED_CHAIN_IDS = list(CHAINS.keys())


def get_chain(chain_id: int) -> ChainConfig:
    if chain_id not in CHAINS:
        supported = ", ".join(str(c) for c in SUPPORTED_CHAIN_IDS)
        raise ValueError(f"Unsupported chain_id {chain_id}. Supported: {supported}")
    return CHAINS[chain_id]


def get_default_rpc(chain_id: int) -> str:
    import os
    env_rpc = os.environ.get("ETH_RPC_URL", "")
    if env_rpc and chain_id == 1:
        return env_rpc
    return get_chain(chain_id).rpc_url


def explorer_tx_url(chain_id: int, tx_hash: str) -> str:
    return f"{get_chain(chain_id).explorer_url}/tx/{tx_hash}"


def explorer_address_url(chain_id: int, address: str) -> str:
    return f"{get_chain(chain_id).explorer_url}/address/{address}"
