"""Shared Gemini agentic tool-loop for ChainObserver's chain-specific diagnosis agents."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

from google import genai
from google.genai import types
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

logger = logging.getLogger(__name__)
console = Console()

GEMINI_MODEL = "gemini-2.5-flash"
MAX_TOOL_ITERATIONS = 12


class BaseDiagnosisAgent:
    """Runs the Gemini 2.5 Flash agentic tool-call loop against an MCP backend.

    Chain-specific subclasses (EthereumDiagnosisAgent, SolanaDiagnosisAgent) provide
    the system prompt, the MCP backend, and how to parse the final report — this
    class owns only the iterate-and-call-tools mechanics, identical across chains.
    """

    def __init__(
        self,
        gemini_api_key: str = "",
        use_vertex: bool = False,
        gcp_project: str = "",
        gcp_location: str = "us-central1",
    ) -> None:
        if use_vertex or (not gemini_api_key and gcp_project):
            self._genai = genai.Client(vertexai=True, project=gcp_project, location=gcp_location)
        else:
            self._genai = genai.Client(api_key=gemini_api_key)

    async def _run_tool_loop(
        self,
        backend: Any,
        system_prompt: str,
        tools: list[types.Tool],
        messages: list[types.Content],
    ) -> tuple[str, int]:
        final_text = ""
        tool_call_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task_id = progress.add_task("Analyzing…", total=None)

            for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
                progress.update(task_id, description=f"Iteration {iteration}/{MAX_TOOL_ITERATIONS}…")

                # Retry with backoff on rate-limit (429) errors
                for _attempt in range(8):
                    try:
                        response = await self._genai.aio.models.generate_content(
                            model=GEMINI_MODEL,
                            contents=messages,
                            config=types.GenerateContentConfig(
                                system_instruction=system_prompt,
                                tools=tools,
                                temperature=0.1,
                            ),
                        )
                        break
                    except Exception as exc:
                        err_str = str(exc)
                        if any(c in err_str for c in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"]):
                            wait = 65
                            m = re.search(r"retry in ([0-9.]+)s", err_str)
                            if m:
                                wait = int(float(m.group(1))) + 5
                            progress.update(task_id, description=f"Rate limited — waiting {wait}s…")
                            console.print(f"  [yellow]Rate limit hit — sleeping {wait}s before retry…[/]")
                            await asyncio.sleep(wait)
                        else:
                            raise
                else:
                    raise RuntimeError("Gemini rate limit: max retries exceeded")

                if not response.candidates:
                    logger.warning("Gemini returned no candidates")
                    break

                candidate = response.candidates[0]
                messages.append(candidate.content)

                tool_calls = [
                    p.function_call
                    for p in (candidate.content.parts or [])
                    if p.function_call
                ]
                text_parts = [
                    p.text
                    for p in (candidate.content.parts or [])
                    if p.text
                ]

                if text_parts:
                    final_text = "\n".join(text_parts)

                if not tool_calls:
                    break

                tool_responses: list[types.Part] = []
                for fc in tool_calls:
                    tool_call_count += 1
                    progress.update(task_id, description=f"→ {fc.name}(…)")
                    console.print(f"  [dim]→ {fc.name}({_fmt_args(dict(fc.args))})[/]")
                    result_text = await backend.call_tool(fc.name, dict(fc.args))
                    tool_responses.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=fc.name,
                                response={"output": result_text},
                            )
                        )
                    )
                messages.append(types.Content(role="tool", parts=tool_responses))

        return final_text, tool_call_count


def _fmt_args(args: dict[str, Any]) -> str:
    s = json.dumps(args, default=str)
    return (s[:80] + "…") if len(s) > 80 else s


def extract_json_block(text: str) -> str | None:
    start = text.find("```json")
    if start == -1:
        return None
    brace_start = text.find("{", start)
    if brace_start == -1:
        return None
    depth = 0
    in_str = False
    escaped = False
    for i, ch in enumerate(text[brace_start:], brace_start):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_str:
            escaped = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[brace_start:i + 1]
    return None
