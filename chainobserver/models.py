"""Data models for ChainObserver transaction diagnosis results."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FailureType(str, Enum):
    SLIPPAGE_EXCEEDED = "slippage_exceeded"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    INSUFFICIENT_ALLOWANCE = "insufficient_allowance"
    OUT_OF_GAS = "out_of_gas"
    CONTRACT_REVERT = "contract_revert"
    UNAUTHORIZED = "unauthorized"
    LIQUIDITY_ISSUE = "liquidity_issue"
    UNKNOWN = "unknown"


@dataclass
class TxDiagnosisReport:
    tx_hash: str
    root_cause: str
    failure_type: FailureType = FailureType.UNKNOWN
    affected_address: str = ""
    confidence: Confidence = Confidence.MEDIUM
    fix_suggestion: str = ""
    related_link: str = ""
    full_analysis: str = ""
    diagnosis_time_s: float = 0.0
    tool_calls: int = 0
