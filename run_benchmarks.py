"""
ChainObserver benchmark runner — Day 10 testing.

Usage:
    python run_benchmarks.py [TX_HASH ...]

Runs ChainObserver on each tx hash and logs time, tool calls, failure_type, confidence, fix.
"""
from __future__ import annotations
import asyncio, os, sys, time, json
from dataclasses import dataclass, asdict

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()
console = Console()


@dataclass
class BenchResult:
    tx_hash: str
    expected_type: str
    actual_type: str
    confidence: str
    root_cause: str
    fix_suggestion: str
    time_s: float
    tool_calls: int
    correct: bool


async def run_one(tx_hash: str, expected: str, gemini_key: str) -> BenchResult:
    from chainobserver.agent import EthereumDiagnosisAgent
    agent = EthereumDiagnosisAgent(
        gemini_api_key=gemini_key,
        eth_rpc_url=os.getenv("ETH_RPC_URL", "https://ethereum.publicnode.com"),
        etherscan_api_key=os.getenv("ETHERSCAN_API_KEY", ""),
    )
    console.rule(f"[cyan]{tx_hash[:20]}…  (expected: {expected})")
    report = await agent.diagnose(tx_hash)
    correct = report.failure_type.value == expected
    return BenchResult(
        tx_hash=tx_hash,
        expected_type=expected,
        actual_type=report.failure_type.value,
        confidence=report.confidence.value,
        root_cause=report.root_cause[:80],
        fix_suggestion=report.fix_suggestion[:80],
        time_s=report.diagnosis_time_s,
        tool_calls=report.tool_calls,
        correct=correct,
    )


async def main(test_cases: list[tuple[str, str]], gemini_key: str) -> None:
    results: list[BenchResult] = []
    for tx_hash, expected in test_cases:
        r = await run_one(tx_hash, expected, gemini_key)
        results.append(r)
        status = "[green]✅" if r.correct else "[red]❌"
        console.print(f"  {status} {r.actual_type}  {r.time_s}s  {r.tool_calls} calls[/]")

    console.rule("[bold]BENCHMARK SUMMARY")
    t = Table(show_header=True, header_style="bold cyan")
    t.add_column("TX")
    t.add_column("Expected")
    t.add_column("Actual")
    t.add_column("Conf")
    t.add_column("Time")
    t.add_column("Calls")
    t.add_column("OK")

    for r in results:
        ok = "✅" if r.correct else "❌"
        t.add_row(
            r.tx_hash[:16] + "…",
            r.expected_type,
            r.actual_type,
            r.confidence,
            f"{r.time_s:.1f}s",
            str(r.tool_calls),
            ok,
        )
    console.print(t)

    correct_count = sum(1 for r in results if r.correct)
    avg_time = sum(r.time_s for r in results) / len(results) if results else 0
    avg_calls = sum(r.tool_calls for r in results) / len(results) if results else 0
    console.print(f"\n[bold]Accuracy: {correct_count}/{len(results)} ({correct_count/len(results)*100:.0f}%)")
    console.print(f"[bold]Avg time: {avg_time:.1f}s  |  Avg calls: {avg_calls:.1f}")

    # Write JSON results
    with open("benchmark_results.json", "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    console.print("[dim]Results saved to benchmark_results.json")


if __name__ == "__main__":
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        print("Error: GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Test cases: (tx_hash, expected_failure_type)
    # Populated after scanner finds the hashes
    TEST_CASES: list[tuple[str, str]] = [
        # TX-1: Day 9 baseline (allowance)
        ("0xaa78010df34b38c16b5168ada399b840162bbf3566b398025cad7ba69581bab5", "insufficient_allowance"),
        # TX-2, TX-3, TX-4 inserted below after scanner
    ]

    if len(sys.argv) > 1:
        # Accept extra tx hashes as args: python run_benchmarks.py HASH1:type1 HASH2:type2
        for arg in sys.argv[1:]:
            if ":" in arg:
                h, t = arg.split(":", 1)
                TEST_CASES.append((h.strip(), t.strip()))
            else:
                TEST_CASES.append((arg.strip(), "unknown"))

    asyncio.run(main(TEST_CASES, gemini_key))
