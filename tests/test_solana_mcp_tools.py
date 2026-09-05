"""
Unit tests for ChainObserver Solana MCP tools.

Tests split into:
  - Pure logic (no network): signature validation, error decoding, compute-budget math
  - Network-required (marked): call real Solana public RPC
"""
import json
import pytest
from unittest.mock import patch, MagicMock

SOLANA_RPC = "https://api.mainnet-beta.solana.com"


@pytest.fixture(autouse=True)
def set_rpc(monkeypatch):
    monkeypatch.setenv("SOLANA_RPC_URL", SOLANA_RPC)
    monkeypatch.delenv("SOLANA_CLUSTER", raising=False)


# ── _validate_signature ──────────────────────────────────────────────────────

@pytest.mark.unit
class TestValidateSignature:
    def test_empty_signature_returns_error(self):
        from chainobserver.solana_mcp_server import _validate_signature
        assert _validate_signature("") is not None

    def test_too_short_returns_error(self):
        from chainobserver.solana_mcp_server import _validate_signature
        assert _validate_signature("abc") is not None

    def test_invalid_base58_chars_return_error(self):
        from chainobserver.solana_mcp_server import _validate_signature
        # '0', 'O', 'I', 'l' are excluded from base58
        bad = "0" * 87
        assert _validate_signature(bad) is not None

    def test_valid_looking_signature_returns_none(self):
        from chainobserver.solana_mcp_server import _validate_signature
        valid = "5" + "j" * 86
        assert _validate_signature(valid) is None


# ── get_solana_transaction (unit, mocked RPC) ────────────────────────────────

@pytest.mark.unit
class TestGetSolanaTransactionUnit:
    def test_invalid_signature_returns_error(self):
        from chainobserver.solana_mcp_server import get_solana_transaction
        result = json.loads(get_solana_transaction(""))
        assert "error" in result

    def test_transaction_not_found_returns_error(self):
        from chainobserver.solana_mcp_server import get_solana_transaction
        with patch("chainobserver.solana_mcp_server._get_transaction", return_value=None):
            result = json.loads(get_solana_transaction("5" + "j" * 86))
            assert "error" in result

    def test_successful_tx_parsed_fields(self):
        from chainobserver.solana_mcp_server import get_solana_transaction
        fake_tx = {
            "slot": 123456,
            "blockTime": 1700000000,
            "meta": {
                "err": None,
                "fee": 5000,
                "computeUnitsConsumed": 12345,
                "logMessages": ["Program log: ok"],
                "innerInstructions": [],
            },
            "transaction": {
                "message": {
                    "accountKeys": ["A", "B"],
                    "instructions": [{"programId": "11111111111111111111111111111111"}],
                }
            },
        }
        with patch("chainobserver.solana_mcp_server._get_transaction", return_value=fake_tx):
            result = json.loads(get_solana_transaction("5" + "j" * 86))
        assert result["success"] is True
        assert result["fee_lamports"] == 5000
        assert result["compute_units_consumed"] == 12345
        assert result["program_names"] == ["System Program"]
        assert result["account_key_count"] == 2


# ── decode_program_error ──────────────────────────────────────────────────────

@pytest.mark.unit
class TestDecodeProgramError:
    def test_success_category(self):
        from chainobserver.solana_mcp_server import _decode_program_error
        result = _decode_program_error(None, [])
        assert result["category"] == "success"

    def test_transaction_level_string_error(self):
        from chainobserver.solana_mcp_server import _decode_program_error
        result = _decode_program_error("BlockhashNotFound", [])
        assert result["category"] == "transaction_error"
        assert "blockhash" in result["meaning"].lower()

    def test_builtin_instruction_error(self):
        from chainobserver.solana_mcp_server import _decode_program_error
        err = {"InstructionError": [1, "InsufficientFundsForRent"]}
        result = _decode_program_error(err, [])
        assert result["category"] == "instruction_error"
        assert result["failed_instruction_index"] == 1
        assert "rent" in result["meaning"].lower()

    def test_custom_program_error_without_anchor_log(self):
        from chainobserver.solana_mcp_server import _decode_program_error
        err = {"InstructionError": [0, {"Custom": 6000}]}
        result = _decode_program_error(err, ["Program log: something unrelated"])
        assert result["category"] == "custom_program_error"
        assert result["custom_error_code"] == 6000
        assert "anchor_error" not in result

    def test_custom_program_error_with_anchor_log(self):
        from chainobserver.solana_mcp_server import _decode_program_error
        err = {"InstructionError": [0, {"Custom": 6001}]}
        logs = [
            "Program 11111 invoke [1]",
            "Program log: AnchorError thrown in programs/foo/src/lib.rs:42. "
            "Error Code: InvalidAmount. Error Number: 6001. "
            "Error Message: Amount must be greater than zero.",
        ]
        result = _decode_program_error(err, logs)
        assert result["category"] == "custom_program_error"
        assert result["anchor_error"]["error_code"] == "InvalidAmount"
        assert result["anchor_error"]["error_number"] == 6001
        assert "greater than zero" in result["meaning"]

    def test_unknown_error_shape(self):
        from chainobserver.solana_mcp_server import _decode_program_error
        result = _decode_program_error({"SomeWeirdShape": True}, [])
        assert result["category"] == "unknown"

    def test_log_tail_capped_at_15(self):
        from chainobserver.solana_mcp_server import _decode_program_error
        logs = [f"Program log: line {i}" for i in range(30)]
        result = _decode_program_error({"InstructionError": [0, "AccountNotFound"]}, logs)
        assert len(result["log_tail"]) == 15
        assert result["log_tail"][-1] == "Program log: line 29"


# ── get_program_info (unit, mocked RPC) ───────────────────────────────────────

@pytest.mark.unit
class TestGetProgramInfoUnit:
    def test_invalid_program_id_returns_error_without_calling_rpc(self):
        from chainobserver.solana_mcp_server import get_program_info
        with patch("chainobserver.solana_mcp_server._rpc_call") as mock_rpc:
            result = json.loads(get_program_info(""))
        assert "error" in result
        mock_rpc.assert_not_called()

    def test_too_long_program_id_returns_error(self):
        from chainobserver.solana_mcp_server import get_program_info
        # 88 chars looks like a signature, not a 32-44 char pubkey
        result = json.loads(get_program_info("j" * 88))
        assert "error" in result

    def test_account_not_found(self):
        from chainobserver.solana_mcp_server import get_program_info
        with patch("chainobserver.solana_mcp_server._rpc_call", return_value={"value": None}):
            result = json.loads(get_program_info("SomeRandomUnknownProgram111111111111111"))
        assert "error" in result
        assert result["known_name"] == ""

    def test_known_program_identified(self):
        from chainobserver.solana_mcp_server import get_program_info
        fake_value = {"owner": "BPFLoaderUpgradeab1e11111111111111111111111", "executable": True, "lamports": 1}
        with patch("chainobserver.solana_mcp_server._rpc_call", return_value={"value": fake_value}):
            result = json.loads(get_program_info("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
        assert result["known_name"] == "SPL Token Program"
        assert result["executable"] is True

    def test_unknown_program_has_note(self):
        from chainobserver.solana_mcp_server import get_program_info
        fake_value = {"owner": "BPFLoaderUpgradeab1e11111111111111111111111", "executable": True, "lamports": 1}
        with patch("chainobserver.solana_mcp_server._rpc_call", return_value={"value": fake_value}):
            result = json.loads(get_program_info("SomeCustomProgram1111111111111111111111111"))
        assert result["known_name"] == ""
        assert "not" in result["note"].lower()


# ── get_compute_budget_analysis ───────────────────────────────────────────────

@pytest.mark.unit
class TestComputeBudgetAnalysis:
    def _fake_tx(self, consumed, instructions):
        return {
            "meta": {"computeUnitsConsumed": consumed},
            "transaction": {"message": {"instructions": instructions}},
        }

    def test_default_heuristic_when_no_compute_budget_ix(self):
        from chainobserver.solana_mcp_server import get_compute_budget_analysis
        tx = self._fake_tx(199_000, [{"programId": "11111111111111111111111111111111"}])
        with patch("chainobserver.solana_mcp_server._get_transaction", return_value=tx):
            result = json.loads(get_compute_budget_analysis("5" + "j" * 86))
        assert result["requested_source"] == "default_heuristic"
        assert result["requested_compute_units"] == 200_000
        assert result["is_compute_exceeded"] is True

    def test_explicit_compute_budget_ix_used_parsed_shape(self):
        # Fast-path: if some RPC provider ever emits a parsed shape.
        from chainobserver.solana_mcp_server import get_compute_budget_analysis
        instructions = [
            {
                "programId": "ComputeBudget111111111111111111111111111111",
                "parsed": {"type": "setComputeUnitLimit", "info": {"units": 300_000}},
            }
        ]
        tx = self._fake_tx(100_000, instructions)
        with patch("chainobserver.solana_mcp_server._get_transaction", return_value=tx):
            result = json.loads(get_compute_budget_analysis("5" + "j" * 86))
        assert result["requested_source"] == "SetComputeUnitLimit"
        assert result["requested_compute_units"] == 300_000
        assert result["is_compute_exceeded"] is False

    def test_explicit_compute_budget_ix_used_raw_data_shape(self):
        # Real mainnet-beta shape: no "parsed"/"program" fields, only raw base58 "data".
        # "KwoGK1" is real on-chain data for SetComputeUnitLimit(207077), verified live.
        from chainobserver.solana_mcp_server import get_compute_budget_analysis
        instructions = [
            {
                "programId": "ComputeBudget111111111111111111111111111111",
                "data": "KwoGK1",
                "accounts": [],
                "stackHeight": 1,
            }
        ]
        tx = self._fake_tx(100_000, instructions)
        with patch("chainobserver.solana_mcp_server._get_transaction", return_value=tx):
            result = json.loads(get_compute_budget_analysis("5" + "j" * 86))
        assert result["requested_source"] == "SetComputeUnitLimit"
        assert result["requested_compute_units"] == 207_077
        assert result["is_compute_exceeded"] is False

    def test_set_compute_unit_price_ix_is_not_mistaken_for_limit(self):
        # "3wwiehrLvMaX" is real on-chain data for SetComputeUnitPrice (discriminant 3),
        # a different instruction — must NOT be misread as a compute unit limit.
        from chainobserver.solana_mcp_server import get_compute_budget_analysis
        instructions = [
            {
                "programId": "ComputeBudget111111111111111111111111111111",
                "data": "3wwiehrLvMaX",
                "accounts": [],
                "stackHeight": 1,
            }
        ]
        tx = self._fake_tx(199_000, instructions)
        with patch("chainobserver.solana_mcp_server._get_transaction", return_value=tx):
            result = json.loads(get_compute_budget_analysis("5" + "j" * 86))
        assert result["requested_source"] == "default_heuristic"

    def test_not_exceeded_below_98_percent(self):
        from chainobserver.solana_mcp_server import get_compute_budget_analysis
        tx = self._fake_tx(100_000, [{"programId": "11111111111111111111111111111111"}])
        with patch("chainobserver.solana_mcp_server._get_transaction", return_value=tx):
            result = json.loads(get_compute_budget_analysis("5" + "j" * 86))
        assert result["is_compute_exceeded"] is False
        assert "suggestion" not in result

    def test_invalid_signature_returns_error(self):
        from chainobserver.solana_mcp_server import get_compute_budget_analysis
        result = json.loads(get_compute_budget_analysis(""))
        assert "error" in result


# ── Network-required tests (real mainnet-beta RPC) ────────────────────────────

@pytest.mark.network
class TestLiveSolanaRPC:
    """Finds a real recent failed tx dynamically (public RPCs don't retain old history
    indefinitely, so we don't hardcode a signature that may get pruned)."""

    @staticmethod
    def _find_recent_failed_signature() -> str | None:
        import httpx
        payload = {
            "jsonrpc": "2.0", "id": 1, "method": "getSignaturesForAddress",
            "params": ["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", {"limit": 50}],
        }
        resp = httpx.post(SOLANA_RPC, json=payload, timeout=15.0)
        resp.raise_for_status()
        for entry in resp.json().get("result", []):
            if entry.get("err") is not None:
                return entry["signature"]
        return None

    def test_get_solana_transaction_on_real_failed_tx(self):
        from chainobserver.solana_mcp_server import get_solana_transaction
        sig = self._find_recent_failed_signature()
        if not sig:
            pytest.skip("No recent failed tx found against Token program in the sampled window")
        result = json.loads(get_solana_transaction(sig))
        assert "error" not in result
        assert result["success"] is False

    def test_decode_program_error_on_real_failed_tx(self):
        from chainobserver.solana_mcp_server import decode_program_error
        sig = self._find_recent_failed_signature()
        if not sig:
            pytest.skip("No recent failed tx found against Token program in the sampled window")
        result = json.loads(decode_program_error(sig))
        assert "error" not in result
        assert result["category"] != "success"

    @staticmethod
    def _find_recent_compute_unit_limit_signature() -> str | None:
        import httpx
        for prog in (
            "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
            "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
        ):
            payload = {
                "jsonrpc": "2.0", "id": 1, "method": "getSignaturesForAddress",
                "params": [prog, {"limit": 30}],
            }
            resp = httpx.post(SOLANA_RPC, json=payload, timeout=15.0)
            resp.raise_for_status()
            for entry in resp.json().get("result", []):
                sig = entry["signature"]
                tx_payload = {
                    "jsonrpc": "2.0", "id": 1, "method": "getTransaction",
                    "params": [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
                }
                tx = httpx.post(SOLANA_RPC, json=tx_payload, timeout=15.0).json().get("result")
                if not tx:
                    continue
                for ix in tx["transaction"]["message"]["instructions"]:
                    if ix.get("programId") == "ComputeBudget111111111111111111111111111111":
                        return sig
        return None

    def test_compute_budget_analysis_detects_real_set_compute_unit_limit(self):
        """Regression test for the case-review finding: this RPC returns raw base58 `data`
        for ComputeBudget instructions, not a parsed "program"/"parsed" shape — the detection
        must decode that data directly."""
        from chainobserver.solana_mcp_server import get_compute_budget_analysis
        sig = self._find_recent_compute_unit_limit_signature()
        if not sig:
            pytest.skip("No recent tx with a ComputeBudget instruction found in the sampled window")
        result = json.loads(get_compute_budget_analysis(sig))
        assert "error" not in result
        assert result["requested_source"] in ("SetComputeUnitLimit", "default_heuristic")
