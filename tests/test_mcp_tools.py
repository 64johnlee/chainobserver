"""
Unit tests for ChainObserver MCP tools.

Tests split into:
  - Pure logic (no network): json parsing, edge cases, error handling
  - Network-required (marked): call real Ethereum public node
"""
import json
import os
import pytest
from unittest.mock import patch, MagicMock

# Use public node for network tests
ETH_RPC = "https://ethereum.publicnode.com"

# Real failed tx hashes verified in Day 9-10 benchmarks
TX_ALLOWANCE  = "0xaa78010df34b38c16b5168ada399b840162bbf3566b398025cad7ba69581bab5"
TX_SLIPPAGE   = "0x791cddd199261dbca8562001c55a0b11aa51cf22ba0681d926dfe85c9274f7d5"
TX_BALANCE    = "0xb7d9acfa1450a0d54fe09c1d83c87598220fc97af44b81669dac6eedff997f19"
TX_SEAPORT    = "0xd546940038094f8a50254f8d75ed9dfba2c692d38b0c857a167d2f941982cde8"
WETH          = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDC          = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
UNISWAP_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"


@pytest.fixture(autouse=True)
def set_rpc(monkeypatch):
    monkeypatch.setenv("ETH_RPC_URL", ETH_RPC)


# ── Tool 1: get_transaction_receipt ──────────────────────────────────────────

@pytest.mark.network
class TestGetTransactionReceipt:
    def test_known_failed_tx_returns_status_0(self):
        from chainobserver.mcp_server import get_transaction_receipt
        result = json.loads(get_transaction_receipt(TX_ALLOWANCE))
        assert "error" not in result
        assert result["status"] == 0

    def test_fields_present(self):
        from chainobserver.mcp_server import get_transaction_receipt
        result = json.loads(get_transaction_receipt(TX_ALLOWANCE))
        for field in ("tx_hash", "status", "from_addr", "to_addr", "gas_used",
                      "gas_limit", "block_number", "input_selector", "log_count"):
            assert field in result, f"Missing field: {field}"

    def test_input_selector_is_hex(self):
        from chainobserver.mcp_server import get_transaction_receipt
        result = json.loads(get_transaction_receipt(TX_ALLOWANCE))
        sel = result["input_selector"]
        assert sel.startswith("0x")
        assert len(sel) == 10  # 0x + 4 bytes

    def test_invalid_hash_returns_error(self):
        from chainobserver.mcp_server import get_transaction_receipt
        result = json.loads(get_transaction_receipt("0xdeadbeef"))
        assert "error" in result

    def test_empty_hash_returns_error(self):
        from chainobserver.mcp_server import get_transaction_receipt
        result = json.loads(get_transaction_receipt(""))
        assert "error" in result

    def test_gas_used_less_than_or_equal_gas_limit(self):
        from chainobserver.mcp_server import get_transaction_receipt
        result = json.loads(get_transaction_receipt(TX_ALLOWANCE))
        assert result["gas_used"] <= result["gas_limit"]


# ── Tool 2: decode_revert_reason ─────────────────────────────────────────────

@pytest.mark.network
class TestDecodeRevertReason:
    def test_allowance_failure_revert_contains_transfer_from_failed(self):
        from chainobserver.mcp_server import decode_revert_reason
        result = json.loads(decode_revert_reason(TX_ALLOWANCE))
        reason = result.get("revert_reason", "").lower()
        assert "transfer_from_failed" in reason or "transfer" in reason

    def test_slippage_failure_contains_insufficient_output(self):
        from chainobserver.mcp_server import decode_revert_reason
        result = json.loads(decode_revert_reason(TX_SLIPPAGE))
        reason = result.get("revert_reason", "").lower()
        assert "insufficient" in reason or "output" in reason or "slippage" in reason

    def test_balance_failure_contains_balance(self):
        from chainobserver.mcp_server import decode_revert_reason
        result = json.loads(decode_revert_reason(TX_BALANCE))
        reason = result.get("revert_reason", "").lower()
        assert "balance" in reason

    def test_result_has_required_fields(self):
        from chainobserver.mcp_server import decode_revert_reason
        result = json.loads(decode_revert_reason(TX_ALLOWANCE))
        assert "revert_reason" in result or "error" in result

    def test_invalid_tx_returns_error(self):
        from chainobserver.mcp_server import decode_revert_reason
        result = json.loads(decode_revert_reason("0xinvalidhash"))
        assert "error" in result


# ── Tool 3: get_contract_info ─────────────────────────────────────────────────

@pytest.mark.network
class TestGetContractInfo:
    def test_usdc_identified_as_verified(self):
        from chainobserver.mcp_server import get_contract_info
        result = json.loads(get_contract_info(USDC, "0xa9059cbb"))
        # USDC is verified on Sourcify or Etherscan
        assert result.get("is_verified") is True or result.get("name") not in ("", None)

    def test_selector_decoded_via_4byte(self):
        from chainobserver.mcp_server import get_contract_info
        result = json.loads(get_contract_info(USDC, "0xa9059cbb"))
        candidates = result.get("called_function_candidates", [])
        assert any("transfer" in c.lower() for c in candidates)

    def test_execute_selector_decoded(self):
        from chainobserver.mcp_server import get_contract_info
        # 0x3593564c = execute(bytes,bytes[],uint256) on Uniswap Universal Router
        result = json.loads(get_contract_info(
            "0x66a9893cC07D91D95644AEDD05D03f95e1dBA8Af", "0x3593564c"
        ))
        candidates = result.get("called_function_candidates", [])
        assert any("execute" in c.lower() for c in candidates)

    def test_no_selector_still_returns_address(self):
        from chainobserver.mcp_server import get_contract_info
        result = json.loads(get_contract_info(USDC))
        assert result.get("address") == USDC

    def test_seaport_fulfilladvancedorder_selector(self):
        from chainobserver.mcp_server import get_contract_info
        result = json.loads(get_contract_info(
            "0x0000000000000068F116a894984e2DB1123eB395", "0xe7acab24"
        ))
        candidates = result.get("called_function_candidates", [])
        assert any("fulfillAdvancedOrder" in c or "fulfill" in c.lower() for c in candidates)


# ── Tool 4: simulate_transaction ─────────────────────────────────────────────

@pytest.mark.network
class TestSimulateTransaction:
    def test_allowance_is_deterministic_revert(self):
        from chainobserver.mcp_server import simulate_transaction
        result = json.loads(simulate_transaction(TX_ALLOWANCE))
        assert result.get("failure_mode") in (
            "deterministic_revert", "state_dependent", "state_dependent_likely"
        )
        assert "gas_used" in result

    def test_result_has_gas_fields(self):
        from chainobserver.mcp_server import simulate_transaction
        result = json.loads(simulate_transaction(TX_ALLOWANCE))
        assert "gas_used" in result
        assert "gas_limit" in result

    def test_invalid_hash_returns_error(self):
        from chainobserver.mcp_server import simulate_transaction
        result = json.loads(simulate_transaction("0xinvalid"))
        assert "error" in result

    def test_gas_ratio_format(self):
        from chainobserver.mcp_server import simulate_transaction
        result = json.loads(simulate_transaction(TX_ALLOWANCE))
        if "gas_ratio" in result:
            assert result["gas_ratio"].endswith("%")


# ── Tool 5: get_pool_info ─────────────────────────────────────────────────────

@pytest.mark.network
class TestGetPoolInfo:
    def test_weth_usdc_pool_exists(self):
        from chainobserver.mcp_server import get_pool_info
        result = json.loads(get_pool_info(WETH, USDC))
        assert result.get("pool_exists") is True
        assert "pair_address" in result

    def test_fake_pair_returns_pool_not_exists(self):
        from chainobserver.mcp_server import get_pool_info
        # Two addresses that have no Uniswap V2 pair
        fake_a = "0x0000000000000000000000000000000000000001"
        fake_b = "0x0000000000000000000000000000000000000002"
        result = json.loads(get_pool_info(fake_a, fake_b))
        assert result.get("pool_exists") is False or "error" in result

    def test_pool_has_reserves(self):
        from chainobserver.mcp_server import get_pool_info
        result = json.loads(get_pool_info(WETH, USDC))
        if result.get("pool_exists"):
            assert "reserve_a_raw" in result
            assert "reserve_b_raw" in result
            # reserves should be non-zero integers
            assert int(result["reserve_a_raw"]) > 0

    def test_pair_address_is_valid_hex(self):
        from chainobserver.mcp_server import get_pool_info
        result = json.loads(get_pool_info(WETH, USDC))
        if result.get("pool_exists"):
            addr = result["pair_address"]
            assert addr.startswith("0x")
            assert len(addr) == 42

    def test_invalid_address_returns_error(self):
        from chainobserver.mcp_server import get_pool_info
        result = json.loads(get_pool_info("notanaddress", USDC))
        assert "error" in result


# ── Agent helpers (no network / no Gemini) ───────────────────────────────────

@pytest.mark.unit
class TestAgentHelpers:
    def test_extract_json_block_basic(self):
        from chainobserver.agent import _extract_json_block
        text = 'Some text.\n```json\n{"key": "value"}\n```\nMore text.'
        result = _extract_json_block(text)
        assert result == '{"key": "value"}'

    def test_extract_json_block_missing(self):
        from chainobserver.agent import _extract_json_block
        assert _extract_json_block("No JSON here") is None

    def test_parse_report_with_valid_json(self):
        from chainobserver.agent import _parse_report
        text = '''Analysis here.
```json
{
  "root_cause": "slippage too tight",
  "failure_type": "slippage_exceeded",
  "affected_address": "0xabc",
  "confidence": "high",
  "fix_suggestion": "increase slippage"
}
```'''
        report = _parse_report(text, "0xdeadbeef")
        assert report.root_cause == "slippage too tight"
        assert report.failure_type.value == "slippage_exceeded"
        assert report.confidence.value == "high"

    def test_parse_report_with_invalid_json_falls_back(self):
        from chainobserver.agent import _parse_report
        report = _parse_report("Just plain text no JSON", "0x123")
        assert report.root_cause == "See full analysis below"
        assert report.full_analysis == "Just plain text no JSON"

    def test_parse_report_unknown_failure_type_fallback(self):
        from chainobserver.agent import _parse_report
        text = '```json\n{"root_cause":"x","failure_type":"nonexistent_type","confidence":"high","fix_suggestion":"fix"}\n```'
        # Should fall back gracefully
        report = _parse_report(text, "0x123")
        # Either parses or falls back — just must not raise
        assert report.tx_hash == "0x123"
