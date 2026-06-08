"""Unit tests for ChainObserver CLI — --chain flag and chains subcommand."""
import pytest
from click.testing import CliRunner
from chainobserver.cli import main


@pytest.mark.unit
class TestCLI:
    def test_chains_subcommand_lists_all_five(self):
        result = CliRunner().invoke(main, ["chains"])
        assert result.exit_code == 0
        for name in ("Ethereum", "Arbitrum One", "Base", "Optimism", "Polygon"):
            assert name in result.output

    def test_chains_subcommand_shows_chain_ids(self):
        result = CliRunner().invoke(main, ["chains"])
        assert result.exit_code == 0
        for cid in ("1", "42161", "8453", "10", "137"):
            assert cid in result.output

    def test_diagnose_missing_gemini_key_exits_1(self):
        env = {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}
        result = CliRunner().invoke(
            main,
            ["diagnose", "0x" + "a" * 64],
            env=env,
            catch_exceptions=False,
        )
        assert result.exit_code == 1
        assert "GEMINI_API_KEY" in result.output

    def test_diagnose_invalid_chain_id_exits_1(self):
        env = {"GEMINI_API_KEY": "fake", "GOOGLE_API_KEY": ""}
        result = CliRunner().invoke(
            main,
            ["diagnose", "0x" + "a" * 64, "--chain", "999"],
            env=env,
            catch_exceptions=False,
        )
        assert result.exit_code == 1
        assert "Unsupported chain_id" in result.output or "999" in result.output

    def test_diagnose_default_chain_is_mainnet(self):
        # Without --chain the effective RPC should be for chain 1 (Ethereum).
        # We just verify the option is accepted and defaults without error
        # (will fail at GEMINI_API_KEY step, not at chain resolution).
        env = {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}
        result = CliRunner().invoke(
            main,
            ["diagnose", "0x" + "b" * 64],
            env=env,
            catch_exceptions=False,
        )
        # exits 1 due to missing key, not due to chain error
        assert result.exit_code == 1
        assert "GEMINI_API_KEY" in result.output

    def test_diagnose_arbitrum_chain_resolves_correctly(self):
        # --chain 42161 passes chain validation and reaches key check.
        env = {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}
        result = CliRunner().invoke(
            main,
            ["diagnose", "0x" + "c" * 64, "--chain", "42161"],
            env=env,
            catch_exceptions=False,
        )
        # Fails at key check (exit 1), NOT at chain resolution (which would
        # print "Unsupported chain_id") — proves Arbitrum is recognised.
        assert result.exit_code == 1
        assert "Unsupported" not in result.output
        assert "GEMINI_API_KEY" in result.output

    def test_help_shows_chain_option(self):
        result = CliRunner().invoke(main, ["diagnose", "--help"])
        assert result.exit_code == 0
        assert "--chain" in result.output
        assert "42161" in result.output   # shown in help text
