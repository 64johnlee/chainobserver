"""
Expanded benchmark test suite — Days 13-15.
8 real mainnet txs + unit tests for all 7 failure categories = 10 cases.
"""
import json, os, pytest
os.environ.setdefault("ETH_RPC_URL", "https://ethereum.publicnode.com")

TX1_ALLOWANCE = "0xaa78010df34b38c16b5168ada399b840162bbf3566b398025cad7ba69581bab5"
TX2_SLIPPAGE  = "0x791cddd199261dbca8562001c55a0b11aa51cf22ba0681d926dfe85c9274f7d5"
TX3_BALANCE   = "0xb7d9acfa1450a0d54fe09c1d83c87598220fc97af44b81669dac6eedff997f19"
TX4_SEAPORT   = "0xd546940038094f8a50254f8d75ed9dfba2c692d38b0c857a167d2f941982cde8"
TX5_OOG       = "0xc85afb8c601aabc2d0fa55ae930ef7d29030f5a346c94bb7919f07b08314302d"
TX6_COW_SLIP  = "0x7321fb0ff871d2cbfa30e2b0131881eed34dd17e4560d2fe81dcec1b34b79534"
TX7_AGG_SLIP  = "0x894df9372b1ea83c19e46906f36bf7eb52d4ec716fed337d022b99cd47330d07"
TX8_QUOTE_EXP = "0x21c9c841c0a1b77eab457bb5417c94332c89eee44cae73a640564839794370f9"

ALL_FAILED = [TX1_ALLOWANCE, TX2_SLIPPAGE, TX3_BALANCE, TX4_SEAPORT,
              TX5_OOG, TX6_COW_SLIP, TX7_AGG_SLIP, TX8_QUOTE_EXP]


@pytest.fixture(autouse=True)
def set_rpc(monkeypatch):
    monkeypatch.setenv("ETH_RPC_URL", "https://ethereum.publicnode.com")


@pytest.mark.network
class TestAllTxsFailedWithStatus0:
    @pytest.mark.parametrize("tx_hash", ALL_FAILED)
    def test_status_zero(self, tx_hash):
        from chainobserver.mcp_server import get_transaction_receipt
        r = json.loads(get_transaction_receipt(tx_hash))
        assert "error" not in r, r.get("error")
        assert r["status"] == 0

    @pytest.mark.parametrize("tx_hash", ALL_FAILED)
    def test_etherscan_url_present(self, tx_hash):
        from chainobserver.mcp_server import get_transaction_receipt
        r = json.loads(get_transaction_receipt(tx_hash))
        assert "error" not in r
        assert r.get("etherscan_tx_url") == f"https://etherscan.io/tx/{tx_hash}"


@pytest.mark.network
class TestOutOfGasDetection:
    def test_oog_tx_ratio_above_98pct(self):
        from chainobserver.mcp_server import get_transaction_receipt
        r = json.loads(get_transaction_receipt(TX5_OOG))
        assert "error" not in r
        assert r["gas_used"] / r["gas_limit"] >= 0.98

    def test_simulate_identifies_oog_mode(self):
        from chainobserver.mcp_server import simulate_transaction
        r = json.loads(simulate_transaction(TX5_OOG))
        assert r.get("failure_mode") == "out_of_gas"
        assert r.get("is_out_of_gas") is True

    def test_oog_suggestion_includes_gas(self):
        from chainobserver.mcp_server import simulate_transaction
        r = json.loads(simulate_transaction(TX5_OOG))
        assert "gas" in r.get("suggestion", "").lower()


@pytest.mark.network
class TestSlippageVariants:
    def test_tx2_insufficient_output_amount(self):
        from chainobserver.mcp_server import decode_revert_reason
        r = json.loads(decode_revert_reason(TX2_SLIPPAGE))
        assert "insufficient" in r.get("revert_reason", "").lower()

    def test_tx6_min_return_not_reached(self):
        from chainobserver.mcp_server import decode_revert_reason
        r = json.loads(decode_revert_reason(TX6_COW_SLIP))
        assert "min return" in r.get("revert_reason", "").lower()

    def test_tx7_insufficient_output(self):
        from chainobserver.mcp_server import decode_revert_reason
        r = json.loads(decode_revert_reason(TX7_AGG_SLIP))
        assert "insufficient" in r.get("revert_reason", "").lower()


@pytest.mark.network
class TestCustomErrorDecoding:
    def test_seaport_fulfilladvancedorder_decoded(self):
        from chainobserver.mcp_server import get_contract_info
        r = json.loads(get_contract_info(
            "0x0000000000000068F116a894984e2DB1123eB395", "0xe7acab24"
        ))
        candidates = r.get("called_function_candidates", [])
        assert any("fulfill" in c.lower() for c in candidates)

    def test_paraswap_tx8_non_empty_selector(self):
        from chainobserver.mcp_server import get_transaction_receipt
        r = json.loads(get_transaction_receipt(TX8_QUOTE_EXP))
        assert r.get("input_selector", "0x") != "0x"
        assert r["status"] == 0


@pytest.mark.network
class TestEdgeCases:
    """Day 15: input validation, successful tx field shape, related_link."""

    def test_empty_hash_all_tools(self):
        from chainobserver.mcp_server import (
            get_transaction_receipt, decode_revert_reason, simulate_transaction
        )
        for fn in (get_transaction_receipt, decode_revert_reason, simulate_transaction):
            r = json.loads(fn(""))
            assert "error" in r

    def test_too_short_hash_rejected(self):
        from chainobserver.mcp_server import get_transaction_receipt
        r = json.loads(get_transaction_receipt("0xabc"))
        assert "error" in r

    def test_non_prefixed_hash_rejected(self):
        from chainobserver.mcp_server import get_transaction_receipt
        r = json.loads(get_transaction_receipt("abc123" + "0" * 58))
        assert "error" in r

    def test_receipt_always_has_required_shape(self):
        from chainobserver.mcp_server import get_transaction_receipt
        r = json.loads(get_transaction_receipt(TX1_ALLOWANCE))
        for key in ("tx_hash","status","from_addr","to_addr","gas_used","gas_limit",
                    "block_number","input_selector","etherscan_tx_url"):
            assert key in r, f"Missing: {key}"


@pytest.mark.unit
class TestClassificationLogic:
    """Pure unit tests — all 7 failure types parsed correctly, no network."""

    @pytest.mark.parametrize("failure_type", [
        "slippage_exceeded", "insufficient_balance", "insufficient_allowance",
        "out_of_gas", "contract_revert", "unauthorized", "liquidity_issue", "unknown"
    ])
    def test_failure_type_round_trip(self, failure_type):
        from chainobserver.agent import _parse_report
        from chainobserver.models import FailureType
        # Build a text block with the JSON embedded
        text = (
            "Analysis paragraph.\n"
            "```json\n"
            "{\n"
            '  "root_cause": "test cause",\n'
            f'  "failure_type": "{failure_type}",\n'
            '  "affected_address": "0xabc",\n'
            '  "confidence": "high",\n'
            '  "fix_suggestion": "do the fix"\n'
            "}\n"
            "```"
        )
        report = _parse_report(text, "0xdeadbeef")
        assert report.failure_type == FailureType(failure_type)
        assert report.confidence.value == "high"
        assert report.fix_suggestion == "do the fix"

    def test_related_link_always_populated_on_fallback(self):
        from chainobserver.agent import _parse_report
        tx = "0xaaaa" + "b" * 62
        report = _parse_report("no json", tx)
        assert report.related_link == f"https://etherscan.io/tx/{tx}"

    def test_related_link_populated_from_parsed_json(self):
        from chainobserver.agent import _parse_report
        tx = "0xbbbb" + "c" * 62
        text = (
            "```json\n"
            '{"root_cause":"r","failure_type":"unknown",'
            '"affected_address":"","confidence":"low","fix_suggestion":""}\n'
            "```"
        )
        report = _parse_report(text, tx)
        assert report.related_link == f"https://etherscan.io/tx/{tx}"
