"""ChainObserver Solana MCP server — SVM transaction diagnosis tools.

Exposes 4 Solana tools the ChainObserver Solana agent needs, as MCP tools.
Uses raw JSON-RPC over httpx — no solana-py/solders dependency required.

Run standalone:
    SOLANA_RPC_URL=https://... python -m chainobserver.solana_mcp_server

Configuration (env vars):
    SOLANA_RPC_URL   Solana JSON-RPC endpoint (default: public mainnet-beta node)
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from .solana_chains import explorer_account_url, explorer_tx_url, get_default_rpc, known_program_name

logger = logging.getLogger("chainobserver.solana_mcp_server")

mcp = FastMCP("chainobserver-solana-mcp")

_DEFAULT_CLUSTER = "mainnet-beta"
_DEFAULT_COMPUTE_UNITS_PER_IX = 200_000
_MAX_COMPUTE_UNITS = 1_400_000

# Builtin Solana runtime instruction errors (TransactionError::InstructionError detail
# when it's a string, not a {"Custom": n} program error) mapped to a human explanation.
_INSTRUCTION_ERROR_MEANINGS: dict[str, str] = {
    "InsufficientFunds": "Account lacks enough lamports/tokens for this instruction",
    "InsufficientFundsForRent": "Account balance would fall below the rent-exempt minimum",
    "MissingRequiredSignature": "A required signer did not sign the transaction",
    "AccountNotFound": "Referenced account does not exist",
    "UninitializedAccount": "Referenced account exists but is not initialized",
    "InvalidAccountData": "Account data does not match what the instruction expected",
    "AccountAlreadyInitialized": "Account was already initialized",
    "AccountBorrowFailed": "Account was borrowed mutably twice in the same instruction",
    "InvalidArgument": "Instruction received an invalid argument",
    "InvalidInstructionData": "Instruction data could not be deserialized",
    "NotEnoughAccountKeys": "Instruction did not receive enough account keys",
    "PrivilegeEscalation": "Instruction tried to escalate signer/writable privileges",
}

# Transaction-level errors (TransactionError itself is a bare string, no InstructionError wrapper)
_TRANSACTION_ERROR_MEANINGS: dict[str, str] = {
    "AccountInUse": "Account was locked by another transaction in the same block",
    "AlreadyProcessed": "This exact transaction was already processed",
    "BlockhashNotFound": "Recent blockhash expired before the transaction landed",
    "InsufficientFundsForFee": "Fee payer lacks enough lamports to cover the transaction fee",
    "SanitizeFailure": "Transaction failed basic validation (duplicate accounts, bad indices)",
}

_ANCHOR_ERROR_RE = re.compile(
    r"AnchorError.*?Error Code:\s*(?P<code>\w+)\.\s*Error Number:\s*(?P<number>\d+)\.\s*Error Message:\s*(?P<message>[^.]+)\.",
    re.DOTALL,
)


def _rpc_call(method: str, params: list[Any], rpc_url: str | None = None) -> dict[str, Any]:
    url = rpc_url or get_default_rpc(os.environ.get("SOLANA_CLUSTER", _DEFAULT_CLUSTER))
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = httpx.post(url, json=payload, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data.get("result")  # type: ignore[return-value]


def _validate_signature(signature: str) -> str | None:
    """Return error string if signature is obviously invalid, else None."""
    s = signature.strip()
    if not s:
        return "signature is empty"
    if not (64 <= len(s) <= 96):
        return f"signature must be ~87-88 base58 chars, got {len(s)} chars"
    if not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]+", s):
        return "signature is not valid base58"
    return None


def _validate_pubkey(pubkey: str) -> str | None:
    """Return error string if a pubkey/program_id is obviously invalid, else None.

    A Solana pubkey is 32 raw bytes, base58-encoded to ~32-44 chars — much shorter
    than a 64-byte transaction signature (~87-88 chars).
    """
    s = pubkey.strip()
    if not s:
        return "program_id is empty"
    if not (32 <= len(s) <= 44):
        return f"program_id must be ~32-44 base58 chars, got {len(s)} chars"
    if not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]+", s):
        return "program_id is not valid base58"
    return None


def _get_transaction(signature: str) -> dict[str, Any] | None:
    return _rpc_call(
        "getTransaction",
        [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
    )


@mcp.tool()
def get_solana_transaction(signature: str) -> str:
    """Fetch a Solana transaction and its execution metadata.

    Args:
        signature: Solana transaction signature (base58).

    Returns JSON with: success, fee_lamports, compute_units_consumed, slot, block_time,
    program_ids (unique programs invoked), account_key_count, log_message_count,
    solscan_tx_url.
    """
    err = _validate_signature(signature)
    if err:
        return json.dumps({"error": err})
    try:
        tx = _get_transaction(signature)
    except Exception as e:
        return json.dumps({"error": str(e)})
    if tx is None:
        return json.dumps({"error": "Transaction not found (not finalized, or pruned by this RPC)"})

    meta = tx.get("meta") or {}
    message = (tx.get("transaction") or {}).get("message") or {}
    instructions = message.get("instructions", [])
    account_keys = message.get("accountKeys", [])

    program_ids: list[str] = []
    for ix in instructions:
        pid = ix.get("programId")
        if pid and pid not in program_ids:
            program_ids.append(pid)
    for inner in meta.get("innerInstructions", []) or []:
        for ix in inner.get("instructions", []):
            pid = ix.get("programId")
            if pid and pid not in program_ids:
                program_ids.append(pid)

    cluster = os.environ.get("SOLANA_CLUSTER", _DEFAULT_CLUSTER)
    return json.dumps({
        "signature": signature,
        "success": meta.get("err") is None,
        "fee_lamports": meta.get("fee", 0),
        "compute_units_consumed": meta.get("computeUnitsConsumed", 0),
        "slot": tx.get("slot", 0),
        "block_time": tx.get("blockTime"),
        "program_ids": program_ids,
        "program_names": [known_program_name(p) or p for p in program_ids],
        "account_key_count": len(account_keys),
        "log_message_count": len(meta.get("logMessages", []) or []),
        "solscan_tx_url": explorer_tx_url(cluster, signature),
    })


def _decode_program_error(err: Any, log_messages: list[str]) -> dict[str, Any]:
    log_tail = log_messages[-15:] if log_messages else []

    if err is None:
        return {"category": "success", "note": "Transaction succeeded — no error to decode"}

    anchor_match = None
    joined_logs = "\n".join(log_messages)
    m = _ANCHOR_ERROR_RE.search(joined_logs)
    if m:
        anchor_match = {
            "error_code": m.group("code"),
            "error_number": int(m.group("number")),
            "error_message": m.group("message").strip(),
        }

    if isinstance(err, str):
        return {
            "category": "transaction_error",
            "error": err,
            "meaning": _TRANSACTION_ERROR_MEANINGS.get(err, "Unrecognized transaction-level error"),
            "log_tail": log_tail,
        }

    if isinstance(err, dict) and "InstructionError" in err:
        ix_err = err["InstructionError"]
        if not (isinstance(ix_err, (list, tuple)) and len(ix_err) == 2):
            return {"category": "unknown", "raw_err": err, "log_tail": log_tail}
        idx, detail = ix_err
        result: dict[str, Any] = {"failed_instruction_index": idx, "log_tail": log_tail}
        if isinstance(detail, dict) and "Custom" in detail:
            result["category"] = "custom_program_error"
            result["custom_error_code"] = detail["Custom"]
            if anchor_match:
                result["anchor_error"] = anchor_match
                result["meaning"] = anchor_match["error_message"]
            else:
                result["meaning"] = (
                    "Program-defined error code — no Anchor error log found; "
                    "check the program's IDL/source for this error number"
                )
        elif isinstance(detail, str):
            result["category"] = "instruction_error"
            result["instruction_error"] = detail
            result["meaning"] = _INSTRUCTION_ERROR_MEANINGS.get(detail, "Unrecognized instruction error")
        else:
            result["category"] = "instruction_error"
            result["instruction_error"] = str(detail)
            result["meaning"] = "Unrecognized instruction error shape"
        return result

    return {"category": "unknown", "raw_err": err, "log_tail": log_tail}


@mcp.tool()
def decode_program_error(signature: str) -> str:
    """Decode why a Solana transaction failed from its on-chain error + program logs.

    Handles built-in runtime instruction errors, program-defined custom error codes,
    and Anchor's structured "AnchorError ... Error Code: X. Error Number: N. Error
    Message: ..." log format when present.

    Args:
        signature: Solana transaction signature (base58).

    Returns JSON with: category (success/transaction_error/instruction_error/
    custom_program_error/unknown), meaning, failed_instruction_index (if applicable),
    custom_error_code (if applicable), anchor_error (if decoded from logs), log_tail.
    """
    err = _validate_signature(signature)
    if err:
        return json.dumps({"error": err})
    try:
        tx = _get_transaction(signature)
    except Exception as e:
        return json.dumps({"error": str(e)})
    if tx is None:
        return json.dumps({"error": "Transaction not found (not finalized, or pruned by this RPC)"})

    meta = tx.get("meta") or {}
    result = _decode_program_error(meta.get("err"), meta.get("logMessages") or [])
    return json.dumps(result)


@mcp.tool()
def get_program_info(program_id: str) -> str:
    """Fetch on-chain account info for a Solana program (or any account).

    Args:
        program_id: Program/account public key (base58).

    Returns JSON with: owner, executable, lamports, known_name (from a small built-in
    registry of System/Token/major DEX programs — empty string if not recognized).
    Does not fetch Anchor IDLs; unrecognized custom programs return known_name="".
    """
    err = _validate_pubkey(program_id)
    if err:
        return json.dumps({"error": err})
    try:
        info = _rpc_call("getAccountInfo", [program_id, {"encoding": "base64"}])
    except Exception as e:
        return json.dumps({"error": str(e)})
    if info is None or info.get("value") is None:
        return json.dumps({
            "error": "Account not found",
            "program_id": program_id,
            "known_name": known_program_name(program_id),
        })

    value = info["value"]
    cluster = os.environ.get("SOLANA_CLUSTER", _DEFAULT_CLUSTER)
    return json.dumps({
        "program_id": program_id,
        "owner": value.get("owner", ""),
        "executable": value.get("executable", False),
        "lamports": value.get("lamports", 0),
        "known_name": known_program_name(program_id),
        "solscan_account_url": explorer_account_url(cluster, program_id),
        "note": "" if known_program_name(program_id) else (
            "Not in the built-in registry — Anchor IDL introspection is not implemented; "
            "identify this program from context (logs, related_link) instead."
        ),
    })


_COMPUTE_BUDGET_PROGRAM_ID = "ComputeBudget111111111111111111111111111111"
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _base58_decode(s: str) -> bytes:
    num = 0
    for char in s:
        num = num * 58 + _BASE58_ALPHABET.index(char)
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    n_pad = len(s) - len(s.lstrip("1"))  # leading '1's encode leading zero bytes
    return b"\x00" * n_pad + body


def _decode_set_compute_unit_limit(data_b58: str) -> int | None:
    """Decode a ComputeBudget instruction's raw data for SetComputeUnitLimit (discriminant 2, u32 LE).

    Verified against live mainnet-beta data: this RPC does NOT populate a "parsed"/"program"
    shape for the ComputeBudget program (unlike System/Token/etc.) — only raw base58 `data`.
    """
    try:
        raw = _base58_decode(data_b58)
    except (ValueError, IndexError):
        return None
    if len(raw) >= 5 and raw[0] == 2:
        return int.from_bytes(raw[1:5], "little")
    return None


def _requested_compute_units(instructions: list[dict[str, Any]]) -> int | None:
    for ix in instructions:
        if ix.get("programId") != _COMPUTE_BUDGET_PROGRAM_ID:
            continue
        # Fast path in case an RPC provider does emit a parsed shape for this program.
        parsed = ix.get("parsed")
        if isinstance(parsed, dict) and parsed.get("type") in (
            "setComputeUnitLimit", "set-compute-unit-limit"
        ):
            info = parsed.get("info", {})
            units = info.get("units")
            if isinstance(units, int):
                return units
        data = ix.get("data")
        if isinstance(data, str):
            units = _decode_set_compute_unit_limit(data)
            if units is not None:
                return units
    return None


@mcp.tool()
def get_compute_budget_analysis(signature: str) -> str:
    """Check whether a Solana transaction ran out of compute budget.

    Compares compute_units_consumed against the requested limit (from a
    SetComputeUnitLimit instruction if present, else Solana's default of
    200,000 CU per instruction capped at 1,400,000).

    Args:
        signature: Solana transaction signature (base58).

    Returns JSON with: compute_units_consumed, requested_compute_units,
    compute_ratio, is_compute_exceeded, suggestion.
    """
    err = _validate_signature(signature)
    if err:
        return json.dumps({"error": err})
    try:
        tx = _get_transaction(signature)
    except Exception as e:
        return json.dumps({"error": str(e)})
    if tx is None:
        return json.dumps({"error": "Transaction not found (not finalized, or pruned by this RPC)"})

    meta = tx.get("meta") or {}
    message = (tx.get("transaction") or {}).get("message") or {}
    instructions = message.get("instructions", [])

    consumed = meta.get("computeUnitsConsumed", 0)
    requested = _requested_compute_units(instructions)
    if requested is None:
        requested = min(_DEFAULT_COMPUTE_UNITS_PER_IX * max(len(instructions), 1), _MAX_COMPUTE_UNITS)
        requested_source = "default_heuristic"
    else:
        requested_source = "SetComputeUnitLimit"

    ratio = (consumed / requested) if requested > 0 else 0
    is_exceeded = ratio >= 0.98

    result = {
        "compute_units_consumed": consumed,
        "requested_compute_units": requested,
        "requested_source": requested_source,
        "compute_ratio": f"{ratio:.1%}",
        "is_compute_exceeded": is_exceeded,
    }
    if is_exceeded:
        suggested = int(requested * 1.5)
        result["suggestion"] = (
            f"Add a SetComputeUnitLimit instruction requesting at least {suggested:,} CU "
            f"(1.5x current)"
        )
    return json.dumps(result)


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    mcp.run()


if __name__ == "__main__":
    main()
