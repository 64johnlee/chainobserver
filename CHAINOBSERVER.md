# ChainObserver — Design Document

**Version:** 0.1.0  
**Built for:** ETHGlobal Lisbon 2026  
**Status:** MVP complete

---

## Problem

Every developer who has worked with Ethereum has hit this wall: a transaction fails with a cryptic hex error code or an opaque "execution reverted" message. Diagnosing it means:

1. Opening Etherscan and decoding the revert data manually
2. Looking up the contract ABI
3. Tracing through internal calls
4. Guessing what "TRANSFER_FROM_FAILED" means in context

This takes 20-60 minutes per incident. ChainObserver does it in **under 30 seconds**.

---

## Architecture

```
User / CI / dApp
      │
      ▼
┌─────────────────────────────────┐
│  FastAPI Server  (server.py)    │
│  POST /diagnose {tx_hash}       │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│  EthereumDiagnosisAgent         │
│  (chainobserver/agent.py)       │
│                                 │
│  Gemini 2.5 Flash               │
│  ← agentic tool-call loop →    │
│  max 6 calls, stops early       │
└──────────┬──────────────────────┘
           │ MCP stdio subprocess
           ▼
┌─────────────────────────────────┐
│  ChainObserver MCP Server       │
│  (chainobserver/mcp_server.py)  │
│                                 │
│  Tool 1: get_transaction_receipt│
│  Tool 2: decode_revert_reason   │
│  Tool 3: get_contract_info      │
│  Tool 4: simulate_transaction   │
│  Tool 5: get_pool_info          │
└──────────┬──────────────────────┘
           │
     ┌─────┴──────┬──────────────┐
     ▼            ▼              ▼
Ethereum     Etherscan      4byte.directory
Public RPC   V2 API         (selector decode)
(publicnode) (optional)     Sourcify (ABI)
```

### Agent Loop

The agent runs an iterative Gemini 2.5 Flash call with function-calling enabled.
The model decides which MCP tools to invoke based on what it learns at each step.

**Typical flow for a slippage failure:**
```
Gemini → get_transaction_receipt  (sees selector 0x...)
Gemini → decode_revert_reason     (gets "INSUFFICIENT_OUTPUT_AMOUNT")
Gemini → get_contract_info        (confirms Uniswap, decodes selector)
Gemini → [done — enough to diagnose]
```
3 tool calls, ~20 seconds.

**Worst case (custom Solidity error on unknown contract):**
```
Gemini → get_transaction_receipt
Gemini → decode_revert_reason     (gets raw 0xa1148100)
Gemini → get_contract_info        (4byte lookup → fulfillAdvancedOrder)
Gemini → simulate_transaction     (confirms deterministic revert)
```
4 tool calls, ~35 seconds.

---

## MCP Tools

### `get_transaction_receipt(tx_hash)`
Fetches transaction and receipt from the Ethereum node. Returns: status, from/to addresses, ETH value, gas used/limit, gas price, block number, input selector (first 4 bytes of calldata), log count.

**Data sources:** Ethereum JSON-RPC (`eth_getTransaction`, `eth_getTransactionReceipt`)

### `decode_revert_reason(tx_hash)`
Replays the transaction via `eth_call` at the original block to extract the revert string. Handles:
- Standard Solidity `Error(string)` reverts: returns human-readable string
- `Panic(uint256)` reverts: returns panic code
- Custom errors: returns raw 4-byte selector
- State-dependent failures: reports that replay succeeded (price/balance moved)

**Data sources:** Ethereum JSON-RPC (`eth_call`)

### `get_contract_info(address, input_selector?)`
Returns contract name, verification status, and function/event signatures from Etherscan.
Falls back to Sourcify (free, no API key) when Etherscan key is unavailable.
Also decodes the `input_selector` via 4byte.directory regardless of verification.

**Data sources:** Etherscan V2 API → Sourcify V2 → 4byte.directory

### `simulate_transaction(tx_hash)`
Re-simulates the transaction to distinguish:
- **Out-of-gas:** gas_used ≥ 98% of gas_limit → recommends 1.5x gas increase
- **Deterministic revert:** `eth_call` at original block also reverts → logic error
- **State-dependent:** `eth_call` succeeds in replay → slippage/balance at tx time

**Data sources:** Ethereum JSON-RPC (`eth_call`)

### `get_pool_info(token_a, token_b)`
Queries Uniswap V2 factory for the pool address, then fetches reserves via `getReserves()`.
Useful for diagnosing swap failures where pool liquidity or price impact is the issue.

**Data sources:** Uniswap V2 Factory (`0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f`)

---

## Benchmark Results

Tested on 4 real mainnet failed transactions (June 8, 2026):

| TX Type | Hash prefix | Time | Calls | Result |
|---------|------------|------|-------|--------|
| Uniswap allowance | `0xaa780…` | 18.6s | 3 | ✅ `insufficient_allowance` |
| DEX slippage | `0x791cd…` | 21.4s | 3 | ✅ `slippage_exceeded` |
| USDC balance | `0xb7d9a…` | 11.9s | 3 | ✅ `insufficient_balance` |
| Seaport revert | `0xd5469…` | ~36s | 4 | ✅ `contract_revert` |

**100% accuracy · 21.8s average · 3.25 tool calls average**

---

## Failure Type Taxonomy

| Type | When | Trigger signals |
|------|------|-----------------|
| `slippage_exceeded` | DEX swap price moved | "INSUFFICIENT_OUTPUT_AMOUNT", "Too little received" |
| `insufficient_balance` | Sender lacks ETH/token | "transfer amount exceeds balance" |
| `insufficient_allowance` | ERC-20 approve not called | "TRANSFER_FROM_FAILED", "insufficient allowance" |
| `out_of_gas` | Gas limit too low | gas_used ≥ 98% of gas_limit |
| `contract_revert` | Contract logic rejected | require(), revert(), custom error |
| `unauthorized` | Access control failure | "not owner", "Ownable", role checks |
| `liquidity_issue` | Pool reserves too low | getReserves returns near-zero |
| `unknown` | Insufficient data | No clear signal from any tool |

---

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GEMINI_API_KEY` | Yes | — | Gemini 2.5 Flash API key |
| `ETH_RPC_URL` | No | `https://ethereum.publicnode.com` | Ethereum JSON-RPC endpoint |
| `ETHERSCAN_API_KEY` | No | — | Etherscan V2 (enables full ABI lookup) |
| `USE_VERTEX` | No | `false` | Use Vertex AI instead of AI Studio |
| `GCP_PROJECT` | No | — | GCP project ID (Vertex AI only) |
| `PORT` | No | `7860` | FastAPI server port |

---

## Quick Start

```bash
# Install
git clone https://github.com/observer-ai/chainobserver
cd chainobserver
pip install -e .

# Configure
cp .env.example .env
# edit .env: set GEMINI_API_KEY and ETH_RPC_URL

# CLI
chainobserver diagnose 0xYOUR_TX_HASH

# Server
python server.py
# → http://localhost:7860
```

---

## Design Decisions

**Why MCP over direct function calls?**
The MCP subprocess pattern (from PipelineGuard, proven at ETHGlobal) lets Gemini drive the tool-call loop through standard function-calling. Swapping backends (Ethereum mainnet → testnet → L2) requires only a different MCP server — the agent is untouched.

**Why public RPC by default?**
`https://ethereum.publicnode.com` works without an API key for the hackathon demo. For production, use Alchemy or Infura for archive access and higher rate limits.

**Why Sourcify + 4byte over Etherscan-only?**
Etherscan requires an API key even for basic contract info. Sourcify is a decentralised verification registry with no key requirement. 4byte.directory covers 99%+ of common function selectors. This makes ChainObserver usable out-of-the-box.
