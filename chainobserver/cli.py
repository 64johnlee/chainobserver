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
@click.option("--chain", "chain_id", type=int, default=1, envvar="CHAIN_ID",
              help="Chain ID: 1=Ethereum, 42161=Arbitrum, 8453=Base, 10=Optimism, 137=Polygon")
@click.option("--rpc", envvar="ETH_RPC_URL", default="",
              help="Override RPC URL (default: public node for selected chain)")
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
    chain_id: int,
    rpc: str,
    etherscan_key: str,
    gemini_key: str,
    vertex: bool,
    gcp_project: str,
) -> None:
    """Diagnose a failed Ethereum transaction.

    TX_HASH  The 0x-prefixed transaction hash to diagnose.

    Examples:
        chainobserver diagnose 0xabc123...
        chainobserver diagnose 0xabc123... --chain 42161  # Arbitrum
        chainobserver diagnose 0xabc123... --chain 8453   # Base
    """
    from .agent import EthereumDiagnosisAgent
    from .chains import get_chain, get_default_rpc

    if not gemini_key and not vertex:
        click.echo("Error: GEMINI_API_KEY not set. Pass --gemini-key or set GEMINI_API_KEY.", err=True)
        raise SystemExit(1)

    try:
        chain_cfg = get_chain(chain_id)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    effective_rpc = rpc or get_default_rpc(chain_id)

    agent = EthereumDiagnosisAgent(
        gemini_api_key=gemini_key,
        eth_rpc_url=effective_rpc,
        etherscan_api_key=etherscan_key,
        chain_id=chain_id,
        use_vertex=vertex,
        gcp_project=gcp_project,
    )
    report = asyncio.run(agent.diagnose(tx_hash))

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    table.add_row("Chain", chain_cfg.name)
    table.add_row("Root cause", report.root_cause)
    table.add_row("Failure type", report.failure_type.value)
    table.add_row("Confidence", report.confidence.value)
    table.add_row("Affected", report.affected_address or "—")
    table.add_row("Fix", report.fix_suggestion or "—")
    table.add_row("Explorer", report.related_link or "—")
    table.add_row("Time", f"{report.diagnosis_time_s}s · {report.tool_calls} tool calls")

    console.print()
    console.print(Panel(table, title="[bold]ChainObserver Diagnosis[/]", border_style="green"))

    if report.full_analysis:
        console.print("\n[dim]── Full Analysis ──[/]")
        console.print(report.full_analysis)


@main.command("chains")
def list_chains() -> None:
    """List all supported chains."""
    from .chains import CHAINS
    table = Table(title="Supported Chains", show_header=True)
    table.add_column("Chain ID", style="cyan")
    table.add_column("Name")
    table.add_column("Native Token")
    table.add_column("Explorer")
    for cid, cfg in CHAINS.items():
        table.add_row(str(cid), cfg.name, cfg.native_token, cfg.explorer_url)
    console.print(table)


@main.group()
def solana() -> None:
    """Solana (SVM) transaction diagnosis."""


@solana.command("diagnose")
@click.argument("signature")
@click.option("--cluster", default="mainnet-beta", envvar="SOLANA_CLUSTER",
              help="Cluster: mainnet-beta, devnet, testnet")
@click.option("--rpc", envvar="SOLANA_RPC_URL", default="",
              help="Override RPC URL (default: public node for selected cluster)")
@click.option("--gemini-key", envvar="GEMINI_API_KEY", default="",
              help="Gemini API key")
@click.option("--vertex", is_flag=True, envvar="USE_VERTEX",
              help="Use Vertex AI instead of AI Studio")
@click.option("--gcp-project", envvar="GCP_PROJECT", default="",
              help="GCP project for Vertex AI")
def solana_diagnose(
    signature: str,
    cluster: str,
    rpc: str,
    gemini_key: str,
    vertex: bool,
    gcp_project: str,
) -> None:
    """Diagnose a failed Solana transaction.

    SIGNATURE  The base58 transaction signature to diagnose.

    Examples:
        chainobserver solana diagnose 5j7s...
        chainobserver solana diagnose 5j7s... --cluster devnet
    """
    from .solana_agent import SolanaDiagnosisAgent
    from .solana_chains import get_cluster, get_default_rpc

    if not gemini_key and not vertex:
        click.echo("Error: GEMINI_API_KEY not set. Pass --gemini-key or set GEMINI_API_KEY.", err=True)
        raise SystemExit(1)

    try:
        cluster_cfg = get_cluster(cluster)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    effective_rpc = rpc or get_default_rpc(cluster)

    agent = SolanaDiagnosisAgent(
        gemini_api_key=gemini_key,
        solana_rpc_url=effective_rpc,
        cluster=cluster,
        use_vertex=vertex,
        gcp_project=gcp_project,
    )
    report = asyncio.run(agent.diagnose(signature))

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    table.add_row("Cluster", cluster_cfg.name)
    table.add_row("Root cause", report.root_cause)
    table.add_row("Failure type", report.failure_type.value)
    table.add_row("Confidence", report.confidence.value)
    table.add_row("Affected", report.affected_address or "—")
    table.add_row("Fix", report.fix_suggestion or "—")
    table.add_row("Explorer", report.related_link or "—")
    table.add_row("Time", f"{report.diagnosis_time_s}s · {report.tool_calls} tool calls")

    console.print()
    console.print(Panel(table, title="[bold]ChainObserver Diagnosis[/]", border_style="green"))

    if report.full_analysis:
        console.print("\n[dim]── Full Analysis ──[/]")
        console.print(report.full_analysis)


@solana.command("clusters")
def list_clusters() -> None:
    """List all supported Solana clusters."""
    from .solana_chains import CLUSTERS
    table = Table(title="Supported Solana Clusters", show_header=True)
    table.add_column("Cluster", style="cyan")
    table.add_column("Name")
    table.add_column("Native Token")
    table.add_column("Explorer")
    for cid, cfg in CLUSTERS.items():
        table.add_row(cid, cfg.name, cfg.native_token, cfg.explorer_url)
    console.print(table)


if __name__ == "__main__":
    main()
