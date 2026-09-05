"""ChainObserver Solana agent — diagnoses failed Solana transactions using Gemini 2.5 Flash."""
from __future__ import annotations

import json
import logging
import time

from google.genai import types
from rich.console import Console
from rich.panel import Panel

from .backends.solana_mcp import SolanaMCPBackend
from .base_agent import BaseDiagnosisAgent, extract_json_block
from .models import Confidence, FailureType, TxDiagnosisReport
from .solana_prompts import SOLANA_SYSTEM_PROMPT, build_solana_analysis_prompt

logger = logging.getLogger(__name__)
console = Console()


class SolanaDiagnosisAgent(BaseDiagnosisAgent):
    """
    Diagnoses failed Solana transactions using Gemini 2.5 Flash + ChainObserver Solana MCP tools.

    Auth modes:
      - AI Studio: set gemini_api_key (or GEMINI_API_KEY env var)
      - Vertex AI: set use_vertex=True, gcp_project, gcp_location
    """

    def __init__(
        self,
        gemini_api_key: str = "",
        solana_rpc_url: str = "",
        cluster: str = "mainnet-beta",
        use_vertex: bool = False,
        gcp_project: str = "",
        gcp_location: str = "us-central1",
    ) -> None:
        super().__init__(
            gemini_api_key=gemini_api_key,
            use_vertex=use_vertex,
            gcp_project=gcp_project,
            gcp_location=gcp_location,
        )
        self._solana_rpc_url = solana_rpc_url
        self._cluster = cluster

    async def diagnose(self, signature: str) -> TxDiagnosisReport:
        import os
        from .solana_chains import get_cluster
        os.environ["SOLANA_CLUSTER"] = self._cluster
        try:
            cluster_name = get_cluster(self._cluster).name
        except ValueError:
            cluster_name = f"cluster:{self._cluster}"
        console.print(
            Panel(
                f"[bold cyan]ChainObserver[/] · tx [green]{signature}[/]\n"
                f"[dim]Cluster: {cluster_name} · Gemini 2.5 Flash · Solana MCP tools[/]",
                border_style="cyan",
            )
        )
        start = time.monotonic()
        async with SolanaMCPBackend(self._solana_rpc_url) as backend:
            tools = await backend.list_tools_as_gemini()
            prompt = build_solana_analysis_prompt(signature)
            messages: list[types.Content] = [
                types.Content(role="user", parts=[types.Part(text=prompt)])
            ]
            final_text, tool_call_count = await self._run_tool_loop(
                backend, SOLANA_SYSTEM_PROMPT, tools, messages
            )

        elapsed = time.monotonic() - start
        report = _parse_solana_report(final_text, signature, self._cluster)
        report.diagnosis_time_s = round(elapsed, 2)
        report.tool_calls = tool_call_count
        console.print(
            f"\n[bold green]✓ Diagnosis complete[/] in [yellow]{elapsed:.1f}s[/] "
            f"· [dim]{tool_call_count} tool calls[/]"
        )
        return report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_solana_report(text: str, signature: str, cluster: str = "mainnet-beta") -> TxDiagnosisReport:
    from .solana_chains import explorer_tx_url
    link = explorer_tx_url(cluster, signature)
    raw_json = extract_json_block(text)
    if raw_json is not None:
        try:
            data = json.loads(raw_json)
            return TxDiagnosisReport(
                tx_hash=signature,
                root_cause=data.get("root_cause", "see full analysis"),
                failure_type=FailureType(data.get("failure_type", "unknown")),
                affected_address=data.get("affected_address", ""),
                confidence=Confidence(data.get("confidence", "medium")),
                fix_suggestion=data.get("fix_suggestion", ""),
                related_link=link,
                full_analysis=text,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.debug("Could not parse structured report: %s", exc)

    return TxDiagnosisReport(
        tx_hash=signature,
        root_cause="See full analysis below",
        related_link=link,
        full_analysis=text,
    )
