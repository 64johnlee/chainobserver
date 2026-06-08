"""ChainObserver FastAPI server — REST API for Ethereum transaction diagnosis."""
from __future__ import annotations

import os
import time

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(
    title="ChainObserver",
    description="AI agent that diagnoses failed Ethereum transactions in seconds",
    version="0.1.0",
)

_LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>ChainObserver — AI Ethereum Transaction Diagnosis</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
         background:#0d1117;color:#e6edf3;min-height:100vh}
    header{background:linear-gradient(135deg,#1a1f2e 0%,#161b27 100%);
           border-bottom:1px solid #30363d;padding:2rem 2rem 1.5rem}
    header h1{font-size:2rem;font-weight:700;color:#a371f7}
    header p{color:#8b949e;margin-top:.4rem;font-size:1.05rem}
    .badge{display:inline-block;background:#6e40c9;color:#fff;border-radius:4px;
           padding:.15rem .55rem;font-size:.78rem;font-weight:600;margin-left:.5rem;vertical-align:middle}
    main{max-width:900px;margin:0 auto;padding:2rem}
    .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem;margin:2rem 0}
    .card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1.2rem}
    .card h3{color:#a371f7;margin-bottom:.5rem;font-size:1rem}
    .card p{color:#8b949e;font-size:.9rem;line-height:1.5}
    section{margin:2rem 0}
    section h2{font-size:1.3rem;font-weight:600;color:#e6edf3;
               border-bottom:1px solid #30363d;padding-bottom:.5rem;margin-bottom:1rem}
    .demo-box{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1.5rem}
    label{display:block;color:#8b949e;font-size:.85rem;margin-bottom:.3rem}
    input{width:100%;background:#0d1117;border:1px solid #30363d;color:#e6edf3;
          border-radius:6px;padding:.55rem .75rem;font-size:.95rem;margin-bottom:1rem;
          outline:none;transition:border .2s;font-family:monospace}
    input:focus{border-color:#a371f7}
    button{background:#6e40c9;color:#fff;border:none;border-radius:6px;
           padding:.6rem 1.4rem;font-size:.95rem;cursor:pointer;font-weight:600;
           transition:background .2s}
    button:hover{background:#8957e5}
    button:disabled{background:#21262d;color:#484f58;cursor:not-allowed}
    .preset-row{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:1.2rem}
    .preset-btn{background:#21262d;border:1px solid #30363d;color:#8b949e;
                border-radius:6px;padding:.35rem .85rem;font-size:.82rem;
                cursor:pointer;transition:all .2s;font-weight:500;font-family:monospace}
    .preset-btn:hover{border-color:#a371f7;color:#a371f7;background:#161b22}
    .result-card{background:#0d1117;border:1px solid #30363d;border-radius:8px;
                 padding:1.2rem;margin-top:1rem;display:none}
    .result-header{display:flex;align-items:center;gap:.75rem;margin-bottom:1rem;flex-wrap:wrap}
    .type-badge{display:inline-block;padding:.2rem .65rem;border-radius:12px;
                font-size:.78rem;font-weight:600;border:1px solid}
    .type-slippage{background:#2a1a0d;border-color:#d29922;color:#d29922}
    .type-balance{background:#2a1a1a;border-color:#f85149;color:#f85149}
    .type-allowance{background:#1a2a1a;border-color:#3fb950;color:#3fb950}
    .type-gas{background:#1a1a2a;border-color:#58a6ff;color:#58a6ff}
    .type-revert{background:#2a1a2a;border-color:#bc8cff;color:#bc8cff}
    .type-unknown{background:#21262d;border-color:#30363d;color:#8b949e}
    .timing{font-size:.78rem;color:#484f58;margin-left:auto}
    .root-cause{font-size:1rem;font-weight:600;color:#e6edf3;margin-bottom:.5rem}
    .fix{font-size:.9rem;color:#3fb950;margin-bottom:.5rem}
    .analysis{font-size:.88rem;color:#8b949e;line-height:1.6;white-space:pre-wrap}
    pre{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:1rem;
        font-size:.82rem;overflow-x:auto;color:#e6edf3;white-space:pre-wrap}
    .error{color:#f85149;background:#2a1a1a;border:1px solid #f85149;border-radius:6px;
           padding:.75rem 1rem;margin-top:.5rem}
    footer{text-align:center;padding:2rem;color:#484f58;font-size:.82rem;
           border-top:1px solid #21262d;margin-top:2rem}
    a{color:#a371f7;text-decoration:none}
    a:hover{text-decoration:underline}
  </style>
</head>
<body>
<header>
  <h1>ChainObserver <span class="badge">v0.1</span></h1>
  <p>AI agent that diagnoses failed Ethereum transactions in &lt;45 seconds</p>
</header>
<main>
  <div class="cards">
    <div class="card">
      <h3>Instant Root Cause</h3>
      <p>Paste any failed tx hash. Get slippage/balance/allowance/gas analysis in seconds — not hours of Etherscan hunting.</p>
    </div>
    <div class="card">
      <h3>5 Diagnosis Tools</h3>
      <p>Receipt fetcher, revert decoder, contract ABI lookup, tx simulation, and pool liquidity checker — all coordinated by Gemini 2.5 Flash.</p>
    </div>
    <div class="card">
      <h3>Actionable Fixes</h3>
      <p>Not just "why it failed" but exactly what to do: increase slippage, call approve(), raise gas limit, check balance.</p>
    </div>
  </div>

  <section>
    <h2>Try It Now</h2>
    <div class="demo-box">
      <label>Sample failed transactions (click to load):</label>
      <div class="preset-row">
        <button class="preset-btn" onclick="loadPreset('uniswap')">Uniswap slippage</button>
        <button class="preset-btn" onclick="loadPreset('approve')">Missing approve()</button>
        <button class="preset-btn" onclick="loadPreset('gas')">Out of gas</button>
      </div>
      <label for="txInput">Transaction hash</label>
      <input id="txInput" placeholder="0x..." />
      <button id="diagnoseBtn" onclick="runDiagnosis()">Diagnose Transaction</button>
      <div class="result-card" id="resultCard">
        <div class="result-header">
          <span class="type-badge" id="typeBadge"></span>
          <span id="confidence"></span>
          <span class="timing" id="timing"></span>
        </div>
        <div class="root-cause" id="rootCause"></div>
        <div class="fix" id="fixSuggestion"></div>
        <details style="margin-top:1rem">
          <summary style="cursor:pointer;color:#8b949e;font-size:.85rem">Full analysis</summary>
          <div class="analysis" id="fullAnalysis" style="margin-top:.75rem"></div>
        </details>
      </div>
      <div class="error" id="errorBox" style="display:none"></div>
    </div>
  </section>

  <section>
    <h2>API</h2>
    <pre>POST /diagnose
Content-Type: application/json

{"tx_hash": "0x..."}

→ {
  "tx_hash": "0x...",
  "root_cause": "Uniswap swap reverted due to slippage tolerance exceeded",
  "failure_type": "slippage_exceeded",
  "confidence": "high",
  "fix_suggestion": "Increase slippage tolerance from 0.5% to 1-2%",
  "diagnosis_time_s": 28.4,
  "tool_calls": 4
}</pre>
    <p style="margin-top:.75rem;color:#8b949e;font-size:.9rem">
      Interactive docs: <a href="/docs">/docs</a> &nbsp;·&nbsp;
      Health check: <a href="/health">/health</a>
    </p>
  </section>
</main>
<footer>
  <p>Built for <strong>ETHGlobal Lisbon 2026</strong> · Powered by Gemini 2.5 Flash · 
     <a href="https://github.com/observer-ai/chainobserver">GitHub</a>
  </p>
</footer>
<script>
const PRESETS = {
  uniswap: "0x5c6dbfab47ddc9d8eb7c5c48acbb9ab7dc8f2ae8eb9c17af7daf06f54d8fc1d6",
  approve: "0xa6b4cdf5b6e3cdf5b6e3a6b4cdf5b6e3cdf5b6e3a6b4cdf5b6e3cdf5b6e3a6b4",
  gas: "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12",
};
function loadPreset(key) {
  document.getElementById("txInput").value = PRESETS[key] || "";
}
async function runDiagnosis() {
  const txHash = document.getElementById("txInput").value.trim();
  if (!txHash) { return; }
  const btn = document.getElementById("diagnoseBtn");
  btn.disabled = true;
  btn.textContent = "Diagnosing…";
  document.getElementById("resultCard").style.display = "none";
  document.getElementById("errorBox").style.display = "none";
  try {
    const resp = await fetch("/diagnose", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({tx_hash: txHash}),
    });
    const data = await resp.json();
    if (!resp.ok) {
      document.getElementById("errorBox").textContent = data.detail || "Error";
      document.getElementById("errorBox").style.display = "block";
      return;
    }
    const typeMap = {
      slippage_exceeded:"type-slippage", insufficient_balance:"type-balance",
      insufficient_allowance:"type-allowance", out_of_gas:"type-gas",
      contract_revert:"type-revert", unauthorized:"type-revert",
      unknown:"type-unknown",
    };
    const badge = document.getElementById("typeBadge");
    badge.textContent = (data.failure_type || "unknown").replace(/_/g," ");
    badge.className = "type-badge " + (typeMap[data.failure_type] || "type-unknown");
    document.getElementById("confidence").textContent = "confidence: " + (data.confidence || "—");
    document.getElementById("timing").textContent =
      data.diagnosis_time_s + "s · " + data.tool_calls + " calls";
    document.getElementById("rootCause").textContent = data.root_cause || "";
    document.getElementById("fixSuggestion").textContent =
      data.fix_suggestion ? "Fix: " + data.fix_suggestion : "";
    document.getElementById("fullAnalysis").textContent = data.full_analysis || "";
    document.getElementById("resultCard").style.display = "block";
  } catch(e) {
    document.getElementById("errorBox").textContent = "Request failed: " + e.message;
    document.getElementById("errorBox").style.display = "block";
  } finally {
    btn.disabled = false;
    btn.textContent = "Diagnose Transaction";
  }
}
</script>
</body>
</html>"""


class DiagnoseRequest(BaseModel):
    tx_hash: str = Field(..., description="Ethereum transaction hash (0x-prefixed)")
    chain_id: int = Field(1, description="Chain ID (1=Ethereum, 42161=Arbitrum, 8453=Base, 10=Optimism, 137=Polygon)")


class DiagnoseResponse(BaseModel):
    tx_hash: str
    chain_id: int
    root_cause: str
    failure_type: str
    affected_address: str
    confidence: str
    fix_suggestion: str
    related_link: str
    diagnosis_time_s: float
    tool_calls: int
    full_analysis: str


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing() -> str:
    return _LANDING_HTML


@app.get("/health")
async def health() -> dict:
    from chainobserver.cache import _cache
    return {
        "status": "ok",
        "version": "0.1.0",
        "service": "chainobserver",
        "cache": _cache.stats(),
    }


@app.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(request: DiagnoseRequest) -> DiagnoseResponse:
    """Diagnose a failed Ethereum transaction.

    Pass a 0x-prefixed transaction hash. Returns root cause, failure type,
    fix suggestion, and full Gemini analysis.
    """
    from chainobserver.agent import EthereumDiagnosisAgent

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    use_vertex = os.environ.get("USE_VERTEX", "").lower() in ("1", "true", "yes")
    gcp_project = os.environ.get("GCP_PROJECT", "")

    if not gemini_key and not use_vertex:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY not configured. Set the env var and restart.",
        )

    from chainobserver.cache import _cache
    cached = _cache.get(request.tx_hash, request.chain_id)
    if cached is not None:
        return cached

    agent = EthereumDiagnosisAgent(
        gemini_api_key=gemini_key,
        eth_rpc_url=os.environ.get("ETH_RPC_URL", "https://ethereum.publicnode.com"),
        etherscan_api_key=os.environ.get("ETHERSCAN_API_KEY", ""),
        chain_id=request.chain_id,
        use_vertex=use_vertex,
        gcp_project=gcp_project,
    )

    report = await agent.diagnose(request.tx_hash)

    response = DiagnoseResponse(
        tx_hash=report.tx_hash,
        chain_id=request.chain_id,
        root_cause=report.root_cause,
        failure_type=report.failure_type.value,
        affected_address=report.affected_address,
        confidence=report.confidence.value,
        fix_suggestion=report.fix_suggestion,
        related_link=report.related_link,
        diagnosis_time_s=report.diagnosis_time_s,
        tool_calls=report.tool_calls,
        full_analysis=report.full_analysis,
    )
    _cache.set(request.tx_hash, request.chain_id, response)
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
