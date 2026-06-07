"""Unit tests for ChainObserver data models."""
import pytest
from chainobserver.models import TxDiagnosisReport, FailureType, Confidence


def test_default_report():
    r = TxDiagnosisReport(tx_hash="0xabc", root_cause="test")
    assert r.failure_type == FailureType.UNKNOWN
    assert r.confidence == Confidence.MEDIUM
    assert r.tool_calls == 0
    assert r.diagnosis_time_s == 0.0


def test_failure_type_enum():
    assert FailureType("slippage_exceeded") == FailureType.SLIPPAGE_EXCEEDED
    assert FailureType("insufficient_balance") == FailureType.INSUFFICIENT_BALANCE
    assert FailureType("insufficient_allowance") == FailureType.INSUFFICIENT_ALLOWANCE
    assert FailureType("out_of_gas") == FailureType.OUT_OF_GAS
    assert FailureType("contract_revert") == FailureType.CONTRACT_REVERT
    assert FailureType("unauthorized") == FailureType.UNAUTHORIZED
    assert FailureType("liquidity_issue") == FailureType.LIQUIDITY_ISSUE
    assert FailureType("unknown") == FailureType.UNKNOWN


def test_confidence_enum():
    assert Confidence("high") == Confidence.HIGH
    assert Confidence("medium") == Confidence.MEDIUM
    assert Confidence("low") == Confidence.LOW


def test_full_report_fields():
    r = TxDiagnosisReport(
        tx_hash="0xdeadbeef",
        root_cause="Slippage exceeded",
        failure_type=FailureType.SLIPPAGE_EXCEEDED,
        affected_address="0xUniswap",
        confidence=Confidence.HIGH,
        fix_suggestion="Increase slippage tolerance",
        full_analysis="Full text here",
        diagnosis_time_s=18.5,
        tool_calls=3,
    )
    assert r.failure_type.value == "slippage_exceeded"
    assert r.confidence.value == "high"
    assert r.diagnosis_time_s == 18.5
    assert r.tool_calls == 3


def test_invalid_failure_type():
    with pytest.raises(ValueError):
        FailureType("not_a_valid_type")
