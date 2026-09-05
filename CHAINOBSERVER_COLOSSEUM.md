# ChainObserver — Colosseum Crypto World's Fair 2026 Submission (DRAFT)

> Submission draft for [Crypto World's Fair](https://colosseum.com/worldsfair) — Solana, Base, Ethereum L1 tracks.
> Registration submitted 2026-09-05 under account @64johnlee. Hackathon opens Sep 14; project
> submission window Sep 14 – Oct 12, 2026. **This file is a draft — fill in the TODOs below
> before submitting on the Colosseum dashboard.**

---

## Tagline

**30-second root cause. Every failed transaction. EVM or Solana.**
ChainObserver is a Gemini 2.5 Flash agent that diagnoses failed transactions — Solana program
errors, EVM slippage/allowance/gas failures — and tells you exactly how to fix them, in under 30
seconds, on the chain you're actually building on.

---

## Inspiration

ChainObserver started at ETHGlobal Lisbon 2026 as an Ethereum-only tool: paste a failed tx hash,
get the root cause of a slippage failure, a missing `approve()`, an out-of-gas revert, in seconds
instead of the usual 20-60 minutes of Etherscan archaeology.

Crypto World's Fair is the first Colosseum competition open beyond Solana — exactly the prompt to
ask: does "instant root cause" hold up on a completely different execution model? Solana has no
gas, no revert strings, no `require()`. It has compute units, program logs, and Anchor error
codes. Porting the *idea* meant building genuinely new tooling, not adapting the old one.

---

## What it does

ChainObserver diagnoses a failed transaction in three steps, on either chain family:

1. **Input** — paste a signature (Solana) or tx hash (EVM) via CLI or REST API
2. **Analyze** — Gemini 2.5 Flash drives an agentic loop over a chain-specific MCP toolset
3. **Output** — structured result: failure type, root cause, exact fix, explorer link

### Solana diagnosis (new for this hackathon)

| Type | Example | Signal |
|------|---------|--------|
| Custom program error | Anchor program revert | `Error Code: X. Error Number: N. Error Message: ...` in program logs |
| Compute budget exceeded | Complex CPI chain | `computeUnitsConsumed` ≥ 98% of requested/default limit |
| Account not found / uninitialized | Missing PDA init | Built-in `InstructionError` string |
| Rent-exempt minimum | Withdrawal leaves dust | `InsufficientFundsForRent` |
| Unauthorized | Missing signer | `MissingRequiredSignature` / `PrivilegeEscalation` |

4 purpose-built Solana MCP tools: `get_solana_transaction`, `decode_program_error` (built-in
runtime errors + Anchor log parsing + program-defined custom codes), `get_program_info` (owner,
executable, known-program registry), `get_compute_budget_analysis`.

### EVM diagnosis (from the original ETHGlobal build)

5 tools across Ethereum, Arbitrum, Base, Optimism, Polygon — see `CHAINOBSERVER.md` for the full
architecture. Directly covers 2 of this hackathon's 3 registered tracks (Base, Ethereum L1).

---

## How we built it

### Architecture

One shared Gemini 2.5 Flash agentic loop (`BaseDiagnosisAgent`), two chain-specific subclasses:
`EthereumDiagnosisAgent` and `SolanaDiagnosisAgent`. Each pairs with its own stdio MCP server
(`mcp_server.py` / `solana_mcp_server.py`) — same protocol, entirely different tool implementations,
because the failure models don't share vocabulary (gas vs. compute units, revert strings vs.
program logs).

### Stack

- **Inference:** Gemini 2.5 Flash (AI Studio or Vertex AI)
- **MCP:** official Python SDK, stdio transport
- **EVM:** web3.py 6.x + public RPC + Etherscan V2 + Sourcify + 4byte.directory
- **Solana:** raw JSON-RPC over httpx (no solana-py/solders dependency — kept the surface small)
- **API:** FastAPI + uvicorn, `/diagnose` (EVM) and `/diagnose/solana` (Solana)
- **Deployment:** HuggingFace Spaces (Docker), GitHub Actions CI
- **Tests:** unit + live-network split (pytest markers), Solana suite verified against real
  mainnet-beta transactions found dynamically via `getSignaturesForAddress`

### Why raw JSON-RPC instead of solana-py?

The Solana tools only need two RPC methods (`getTransaction`, `getAccountInfo`) plus Solana's
`jsonParsed` encoding, which already hands back structured `ComputeBudget` instruction data. Adding
a full SDK for two calls would be dead weight; `httpx` was already a dependency for the EVM side.

### What we deliberately did NOT build

- **Anchor IDL fetching.** Correctly deriving and fetching an on-chain IDL account requires exact
  PDA-derivation logic we could not verify against a live program in this build window. Rather than
  ship an unverified derivation that might silently return wrong data, `get_program_info` reports
  ownership/executable status and a small built-in registry of well-known programs (System, Token,
  Token-2022, Raydium, Orca, Jupiter), and is honest when a program isn't recognized.
- **DEX pool-liquidity checks on Solana** (the EVM side's `get_pool_info` equivalent). Raydium/Orca
  pool state uses custom binary account layouts without a stable public schema we could verify
  in-scope; listed under "What's next" instead of faked.

---

## Accomplishments we are proud of

**1. Genuinely different tooling, not a reskin.** `decode_program_error` handles three distinct
error shapes Solana can return (bare string transaction errors, built-in `InstructionError`
strings, and `{"Custom": n}` program-defined codes) and additionally regex-parses Anchor's
structured error-log format when present — closer to how an engineer actually debugs a Solana
failure than a generic "tx reverted" message.

**2. Verified against live chain data, not fixtures only.** The Solana test suite includes tests
that query real mainnet-beta transactions at run time (finding a recent failed transaction against
the SPL Token program rather than hardcoding a signature that a public RPC might later prune).

**3. Shared engineering core, chain-specific correctness.** The Gemini tool-loop, rate-limit
backoff, and JSON-report parsing are one shared base class — only the domain tools and prompts
differ per chain, keeping the two diagnosis paths consistent without pretending Solana and EVM
failures are the same thing.

---

## Challenges we ran into

**Solana has no single "revert reason."** EVM gives you one revert string. Solana's `meta.err` can
be a bare string, an `InstructionError` tuple with a built-in reason, or an opaque
`{"Custom": n}` code — the same code number means different things on different programs. We
resolve ambiguity by cross-referencing Anchor's log format when present, and are explicit when we
can't (rather than guessing).

**No stand-in for gas.** Solana's compute budget model (default 200k CU/instruction, capped at
1.4M, overridable via a `SetComputeUnitLimit` instruction) needed its own detection logic —
`get_compute_budget_analysis` reads the actual requested limit from the parsed instruction when
present instead of assuming the default.

**TODO before submitting:** [fill in any additional challenges hit while wiring GEMINI_API_KEY /
running the live demo — this section should reflect what actually happened in testing, not just
design-time predictions]

---

## What's next

- Anchor IDL on-chain fetch (once PDA derivation is verified against a live test program)
- Raydium/Orca pool-liquidity tool (Solana's `get_pool_info` equivalent)
- Real-time monitoring: watch a wallet, alert on any failed tx across both chain families
- SDK for frontend dApps to surface diagnosis inline when a user's tx fails

---

## Links

- **GitHub (MIT):** https://github.com/64johnlee/chainobserver
- **Live demo (HF Space):** https://huggingface.co/spaces/johnlee007/chainobserver — TODO: verify
  the Space redeploys with Solana support before demo day (current deploy predates this branch)
- **Demo video (Solana):** `demo/chainobserver_solana_demo.mp4` (89s, local) — real data walkthrough of
  the live signature above. TODO: upload to YouTube (ask before public — default unlisted) and link here.
- **Demo video (EVM):** `demo/chainobserver_demo.mp4` — original ETHGlobal Lisbon video, unchanged

---

## Team

Solo submission — @64johnlee.

---

## Live verification (2026-09-05)

First real end-to-end runs against the deployed HF Space (`GEMINI_API_KEY` configured, `mcp<2`
pinned to fix a FastMCP-rename subprocess crash that was blocking both endpoints):

| Chain | Input | Result | Confidence | Time | Tool calls |
|-------|-------|--------|------------|------|------------|
| Ethereum | real mainnet Uniswap Universal Router failure | `contract_revert`, error `0x5bf6f916` | medium | 16.5s | 4 |
| Solana | real mainnet-beta failure, program `GnZr2LD3...` | `custom_program_error`, code 6000 | high | 86.0s | 3 |

n=1 per chain so far — not a benchmark table yet, just proof the full Gemini-driven loop works
live on both chains. The Solana run took notably longer (86s vs 16.5s); worth a few more runs to
see if that's typical or an outlier (rate-limit backoff, a colder RPC response, etc.) before
citing a number in the submission.

## Planned genuine contest-window work (start Sep 14, not before)

Per the FAQ: "products are judged only on the work completed between the competition's start and
end dates," and misrepresenting development history is grounds for disqualification. Everything in
this doc as of 2026-09-05 (Solana support, error-handling fix, deps fix, demo video) is real but
**pre-existing** relative to the Sep 14 start — to be disclosed as such in the submission form, not
hidden. The item below is deliberately deferred so it's genuine Sep 14–Oct 12 work instead:

- [ ] **Raydium/Orca pool-liquidity tool** — Solana's `get_pool_info` equivalent (the EVM agent has
      this; Solana doesn't yet). Do NOT start before Sep 14 — starting earlier defeats the point.

## TODO before submitting on the Colosseum dashboard

- [ ] Run a few more real Solana diagnoses to get an actual average time/tool-call count (one data
      point isn't a benchmark — see the table above)
- [x] Record a Solana demo video — `demo/chainobserver_solana_demo.mp4`, real data, not fabricated
- [ ] Upload the Solana demo video to YouTube and link it here (default unlisted per usual practice)
- [x] Redeploy the HuggingFace Space with the Solana code path — confirmed live, both
      `/diagnose` and `/diagnose/solana` return real 200 OK diagnoses in production
- [ ] Confirm the Colosseum project-creation form (opens with the hackathon on Sep 14) accepts this
      GitHub repo, and copy the relevant sections above into it
