"""ChainObserver MCP server — Ethereum transaction diagnosis tools.

Exposes 5 Ethereum tools the ChainObserver agent needs, as MCP tools.

Run standalone:
    ETH_RPC_URL=https://... ETHERSCAN_API_KEY=... python -m chainobserver.mcp_server

Or via console script:
    ETH_RPC_URL=https://... chainobserver-mcp

Configuration (env vars):
    ETH_RPC_URL         Ethereum JSON-RPC endpoint (default: https://eth.llamarpc.com)
    ETHERSCAN_API_KEY   Etherscan API key for ABI lookups (optional but recommended)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from web3 import Web3
from web3.exceptions import ContractLogicError

logger = logging.getLogger("chainobserver.mcp_server")

mcp = FastMCP("chainobserver-mcp")

_DEFAULT_CHAIN_ID = 1

from .chains import get_chain, get_default_rpc, explorer_tx_url, explorer_address_url

# Uniswap V2 factory on Ethereum mainnet (overridden per chain via chains.py)
_UNISWAP_V2_FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
_FACTORY_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "tokenA", "type": "address"}, {"name": "tokenB", "type": "address"}],
        "name": "getPair",
        "outputs": [{"name": "pair", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]
_PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"name": "_reserve0", "type": "uint112"},
            {"name": "_reserve1", "type": "uint112"},
            {"name": "_blockTimestampLast", "type": "uint32"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token1",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def _get_w3(chain_id: int = _DEFAULT_CHAIN_ID) -> Web3:
    rpc_url = get_default_rpc(chain_id)
    return Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 15}))


def _etherscan_get(params: dict[str, Any], chain_id: int = _DEFAULT_CHAIN_ID) -> dict[str, Any]:
    api_key = os.environ.get("ETHERSCAN_API_KEY", "")
    chain_cfg = get_chain(chain_id)
    params = {**params, "apikey": api_key, "chainid": str(chain_id)}
    resp = httpx.get(chain_cfg.etherscan_api_url, params=params, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def _hex_bytes_to_str(v: Any) -> str:
    if isinstance(v, (bytes, bytearray)):
        return "0x" + v.hex()
    if hasattr(v, "hex"):
        return "0x" + v.hex()
    return str(v)


def _validate_tx_hash(tx_hash: str) -> str | None:
    """Return error string if tx_hash is obviously invalid, else None."""
    h = tx_hash.strip()
    if not h:
        return "tx_hash is empty"
    if not h.startswith("0x"):
        return f"tx_hash must start with 0x, got: {h[:12]}"
    if len(h) != 66:
        return f"tx_hash must be 66 chars (0x + 32 bytes), got {len(h)} chars"
    return None


@mcp.tool()
def get_transaction_receipt(tx_hash: str) -> str:
    """Fetch transaction receipt and details for a given tx hash.

    Args:
        tx_hash: Ethereum transaction hash (0x-prefixed hex).

    Returns JSON with: status (1=success/0=failed), from_addr, to_addr, value_eth,
    gas_used, gas_limit, gas_price_gwei, block_number, input_selector (first 4 bytes),
    log_count.
    """
    w3 = _get_w3()
    try:
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as e:
        return json.dumps({"error": str(e)})

    input_data = tx.get("input") or b""
    if hasattr(input_data, "__len__") and len(input_data) >= 4:
        selector = "0x" + bytes(input_data[:4]).hex()
    else:
        selector = "0x"

    value_wei = tx.get("value", 0)
    gas_price_wei = tx.get("gasPrice", 0)

    to_addr = tx.get("to", "") or "(contract_creation)"
    return json.dumps({
        "tx_hash": tx_hash,
        "status": receipt.get("status", 0),
        "from_addr": tx.get("from", ""),
        "to_addr": to_addr,
        "value_eth": str(Web3.from_wei(value_wei, "ether")),
        "gas_used": receipt.get("gasUsed", 0),
        "gas_limit": tx.get("gas", 0),
        "gas_price_gwei": str(Web3.from_wei(gas_price_wei, "gwei")),
        "block_number": receipt.get("blockNumber", 0),
        "input_selector": selector,
        "log_count": len(receipt.get("logs", [])),
        "etherscan_tx_url": explorer_tx_url(int(os.environ.get("CHAIN_ID", "1")), tx_hash),
        "etherscan_contract_url": (
            explorer_address_url(int(os.environ.get("CHAIN_ID", "1")), to_addr)
            if to_addr != "(contract_creation)" else ""
        ),
    })


@mcp.tool()
def decode_revert_reason(tx_hash: str) -> str:
    """Decode the revert reason for a failed transaction by replaying it via eth_call.

    Args:
        tx_hash: Ethereum transaction hash (0x-prefixed hex).

    Returns JSON with: revert_reason (human-readable string or raw hex),
    error_type (Error/Panic/custom), is_state_dependent (True if replay succeeded).
    """
    w3 = _get_w3()
    try:
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as e:
        return json.dumps({"error": f"Could not fetch transaction: {e}"})

    if receipt.get("status") == 1:
        return json.dumps({"error": "Transaction succeeded — no revert reason to decode"})

    call_params: dict[str, Any] = {
        "from": tx["from"],
        "to": tx.get("to"),
        "data": _hex_bytes_to_str(tx.get("input", b"")),
        "value": hex(tx.get("value", 0)),
        "gas": hex(tx.get("gas", 0)),
    }
    block_num = receipt.get("blockNumber", "latest")

    # Try replay at mined block first; fall back to latest if RPC lacks archive
    for block_id in [block_num, "latest"]:
        try:
            w3.eth.call(call_params, block_identifier=block_id)
            # Call succeeded in replay — failure was state-dependent
            return json.dumps({
                "revert_reason": "state_dependent",
                "is_state_dependent": True,
                "note": (
                    "Transaction replay succeeded — the failure depended on blockchain state "
                    "at the time (e.g. slippage tolerance, balance, price movement)."
                ),
            })
        except ContractLogicError as e:
            msg = str(e)
            error_type = "Error"
            if "0x4e487b71" in msg:
                error_type = "Panic"
            return json.dumps({
                "revert_reason": msg,
                "error_type": error_type,
                "is_state_dependent": False,
            })
        except Exception as e:
            raw = str(e)
            # Check for known ABI-encoded error selectors in the message
            error_type = "unknown"
            if "0x08c379a0" in raw:
                error_type = "Error(string)"
            elif "0x4e487b71" in raw:
                error_type = "Panic(uint256)"
            if block_id == block_num:
                # Will retry at latest
                continue
            return json.dumps({
                "revert_reason": raw,
                "error_type": error_type,
                "is_state_dependent": None,
            })

    return json.dumps({"error": "Could not determine revert reason"})


def _decode_selector(selector: str) -> list[str]:
    """Decode a 4-byte function selector via 4byte.directory."""
    if not selector or selector == "0x":
        return []
    try:
        resp = httpx.get(
            "https://www.4byte.directory/api/v1/signatures/",
            params={"hex_signature": selector},
            timeout=5.0,
        )
        if resp.status_code == 200:
            return [r["text_signature"] for r in resp.json().get("results", [])]
    except Exception:
        pass
    return []


def _sourcify_name(address: str) -> str:
    """Get contract name from Sourcify v2 API (free, no key required)."""
    try:
        resp = httpx.get(
            f"https://sourcify.dev/server/v2/contract/1/{address}",
            timeout=5.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Sourcify v2 doesn't return name directly — use proxy/match info
            match = data.get("match", "")
            return f"sourcify_verified:{match}" if match else "sourcify_verified"
    except Exception:
        pass
    return ""


@mcp.tool()
def get_contract_info(address: str, input_selector: str = "") -> str:
    """Fetch ABI and contract name from Etherscan for a contract address.
    Also decodes the function selector via 4byte.directory.

    Args:
        address: Ethereum contract address (0x-prefixed).
        input_selector: Optional 4-byte function selector from the transaction input
                        (e.g. '0x3593564c'). Used to decode the called function name.

    Returns JSON with: name, is_verified, function_signatures (list), compiler_version,
    called_function (if input_selector provided).
    """
    result_data: dict[str, Any] = {"address": address}

    # Decode selector via 4byte.directory regardless of contract verification
    if input_selector and input_selector != "0x":
        result_data["called_function_candidates"] = _decode_selector(input_selector)

    # Try Etherscan first (requires API key for reliable results)
    etherscan_ok = False
    api_key = os.environ.get("ETHERSCAN_API_KEY", "")
    if api_key:
        try:
            data = _etherscan_get({
                "module": "contract",
                "action": "getsourcecode",
                "address": address,
            })
            if data.get("status") == "1" and isinstance(data.get("result"), list):
                r = data["result"][0]
                abi_str = r.get("ABI", "")
                is_verified = abi_str not in ("Contract source code not verified", "", None)
                function_sigs: list[str] = []
                event_sigs: list[str] = []
                if is_verified:
                    try:
                        abi = json.loads(abi_str)
                        for item in abi:
                            item_type = item.get("type", "")
                            if item_type == "function":
                                inputs = ",".join(i["type"] for i in item.get("inputs", []))
                                function_sigs.append(f"{item['name']}({inputs})")
                            elif item_type == "event":
                                inputs = ",".join(i["type"] for i in item.get("inputs", []))
                                event_sigs.append(f"{item['name']}({inputs})")
                    except (json.JSONDecodeError, KeyError):
                        pass
                result_data.update({
                    "name": r.get("ContractName", "unknown"),
                    "is_verified": is_verified,
                    "compiler_version": r.get("CompilerVersion", ""),
                    "function_signatures": function_sigs[:25],
                    "event_signatures": event_sigs[:10],
                    "proxy": r.get("Proxy", "0") == "1",
                    "source": "etherscan",
                })
                etherscan_ok = True
        except Exception:
            pass

    # Fallback to Sourcify (free, no key required)
    if not etherscan_ok:
        sourcify = _sourcify_name(address)
        result_data.update({
            "name": sourcify or "unknown",
            "is_verified": bool(sourcify),
            "function_signatures": [],
            "source": "sourcify" if sourcify else "none",
            "note": (
                "Full ABI unavailable without ETHERSCAN_API_KEY. "
                "Set env var for complete contract analysis."
                if not sourcify else "Verified on Sourcify (ABI not extracted)."
            ),
        })

    return json.dumps(result_data)


@mcp.tool()
def simulate_transaction(tx_hash: str) -> str:
    """Simulate a failed transaction to identify its failure mode.

    Checks for out-of-gas, state-dependent failures, and deterministic reverts.

    Args:
        tx_hash: Ethereum transaction hash (0x-prefixed hex).

    Returns JSON with: failure_mode, gas_used, gas_limit, gas_ratio,
    is_out_of_gas, is_state_dependent, replay_error.
    """
    err = _validate_tx_hash(tx_hash)
    if err:
        return json.dumps({"error": err})
    w3 = _get_w3()
    try:
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as e:
        return json.dumps({"error": str(e)})

    gas_used = receipt.get("gasUsed", 0)
    gas_limit = tx.get("gas", 0)
    gas_ratio = (gas_used / gas_limit) if gas_limit > 0 else 0

    # Out-of-gas: used >= 98% of limit
    if gas_limit > 0 and gas_ratio >= 0.98:
        suggested = int(gas_limit * 1.5)
        return json.dumps({
            "failure_mode": "out_of_gas",
            "gas_used": gas_used,
            "gas_limit": gas_limit,
            "gas_ratio": f"{gas_ratio:.1%}",
            "is_out_of_gas": True,
            "suggestion": f"Increase gas limit to at least {suggested:,} (1.5x current)",
        })

    call_params: dict[str, Any] = {
        "from": tx["from"],
        "to": tx.get("to"),
        "data": _hex_bytes_to_str(tx.get("input", b"")),
        "value": hex(tx.get("value", 0)),
    }
    block_num = receipt.get("blockNumber", "latest")

    # Replay at mined block
    try:
        w3.eth.call(call_params, block_identifier=block_num)
        return json.dumps({
            "failure_mode": "state_dependent",
            "gas_used": gas_used,
            "gas_limit": gas_limit,
            "gas_ratio": f"{gas_ratio:.1%}",
            "is_state_dependent": True,
            "note": (
                "Replay at original block succeeded — failure was caused by transient state: "
                "price movement (slippage), balance, allowance, or race condition."
            ),
        })
    except ContractLogicError as e:
        return json.dumps({
            "failure_mode": "deterministic_revert",
            "gas_used": gas_used,
            "gas_limit": gas_limit,
            "gas_ratio": f"{gas_ratio:.1%}",
            "is_deterministic": True,
            "replay_error": str(e),
        })
    except Exception as e:
        # RPC may not support archive calls; retry at latest
        try:
            w3.eth.call(call_params, block_identifier="latest")
            return json.dumps({
                "failure_mode": "state_dependent_likely",
                "gas_used": gas_used,
                "gas_limit": gas_limit,
                "note": "Could not replay at original block (no archive access); latest call succeeded",
            })
        except Exception as e2:
            return json.dumps({
                "failure_mode": "deterministic_revert",
                "gas_used": gas_used,
                "gas_limit": gas_limit,
                "replay_error": str(e2),
            })


@mcp.tool()
def get_pool_info(token_a: str, token_b: str) -> str:
    """Check Uniswap V2 pool liquidity and reserves for a token pair.

    Args:
        token_a: ERC-20 token address (checksummed or lower-case, any order).
        token_b: ERC-20 token address (checksummed or lower-case, any order).

    Returns JSON with: pool_exists, pair_address, reserve_a, reserve_b,
    price_b_per_a, reserve_a_human (approx, assumes 18 decimals), reserve_b_human.
    """
    w3 = _get_w3()
    try:
        addr_a = Web3.to_checksum_address(token_a)
        addr_b = Web3.to_checksum_address(token_b)
        factory = w3.eth.contract(
            address=Web3.to_checksum_address(_UNISWAP_V2_FACTORY),
            abi=_FACTORY_ABI,
        )
        pair_address: str = factory.functions.getPair(addr_a, addr_b).call()
    except Exception as e:
        return json.dumps({"error": f"Could not query Uniswap V2 factory: {e}"})

    zero_addr = "0x" + "0" * 40
    if pair_address.lower() == zero_addr:
        return json.dumps({
            "pool_exists": False,
            "token_a": token_a,
            "token_b": token_b,
            "note": "No Uniswap V2 pool exists for this token pair",
        })

    try:
        pair = w3.eth.contract(address=pair_address, abi=_PAIR_ABI)
        reserves = pair.functions.getReserves().call()
        token0: str = pair.functions.token0().call()
        r0, r1, _ = reserves

        if token0.lower() == addr_a.lower():
            ra, rb = r0, r1
        else:
            ra, rb = r1, r0

        price = rb / ra if ra > 0 else 0

        return json.dumps({
            "pool_exists": True,
            "pair_address": pair_address,
            "token0": token0,
            "reserve_a_raw": str(ra),
            "reserve_b_raw": str(rb),
            "price_b_per_a": f"{price:.8f}",
            "reserve_a_human": f"{ra / 1e18:.4f}",
            "reserve_b_human": f"{rb / 1e18:.4f}",
            "note": "reserve_a/b_human assumes 18 decimals; verify with actual token decimals",
        })
    except Exception as e:
        return json.dumps({
            "error": f"Could not read pair reserves: {e}",
            "pair_address": pair_address,
        })


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    mcp.run()


if __name__ == "__main__":
    main()
