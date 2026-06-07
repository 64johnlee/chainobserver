"""ChainObserver CLI — diagnose failed Ethereum transactions from the terminal."""
from __future__ import annotations

import asyncio
import os

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv()
console = Console()


@click.group()
def main() -> None:
    """ChainObserver — AI-powered Ethereum transaction diagnosis."""


@main.command()
@click.argument("tx_hash")
@click.option("--rpc", envvar="ETH_RPC_URL", default="https://eth.llamarpc.com",
              help="Ethereum RPC URL")
@click.option("--etherscan-key", envvar="ETHERSCAN_API_KEY", default="",
              help="Etherscan API key")
@click.option("--gemini-key", envvar="GEMINI_API_KEY", default="",
              help="Gemini API key")
@click.option("--vertex", is_flag=True, envvar="USE_VERTEX",
              help="Use Vertex AI instead of AI Studio")
@click.option("--gcp-project", envvar="GCP_PROJECT", default="",
              help="GCP project for Vertex AI")
def diagnose(
    tx_hash: str,
    rpc: str,
    etherscan_key: str,
    gemini_key: str,
    vertex: bool,
    gcp_project: str,
) -> None:
    """Diagnose a failed Ethereum transaction.

    TX_HASH  The 0x-prefixed transaction hash to diagnose.

    Example:
        chainobserver diagnose 0xabc123...
    """
    from .agent import EthereumDiagnosisAgent

    if not gemini_key and not vertex:
        click.echo("Error: GEMINI_API_KEY not set. Pass --gemini-key or set GEMINI_API_KEY.", err=True)
        raise SystemExit(1)

    agent = EthereumDiagnosisAgent(
        gemini_api_key=gemini_key,
        eth_rpc_url=rpc,
        etherscan_api_key=etherscan_key,
        use_vertex=vertex,
        gcp_project=gcp_project,
    )
    report = asyncio.run(agent.diagnose(tx_hash))

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    table.add_row("Root cause", report.root_cause)
    table.add_row("Failure type", report.failure_type.value)
    table.add_row("Confidence", report.confidence.value)
    table.add_row("Affected", report.affected_address or "—")
    table.add_row("Fix", report.fix_suggestion or "—")
    table.add_row("Time", f"{report.diagnosis_time_s}s · {report.tool_calls} tool calls")

    console.print()
    console.print(Panel(table, title="[bold]ChainObserver Diagnosis[/]", border_style="green"))

    if report.full_analysis:
        console.print("\n[dim]── Full Analysis ──[/]")
        console.print(report.full_analysis)


if __name__ == "__main__":
    main()
