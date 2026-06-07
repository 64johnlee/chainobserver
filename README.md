---
title: ChainObserver
emoji: 🔍
colorFrom: purple
colorTo: indigo
sdk: docker
pinned: true
app_port: 7860
---

# ChainObserver

**AI agent that diagnoses failed Ethereum transactions in under 30 seconds.**

Paste a transaction hash → get root cause + actionable fix, powered by Gemini 2.5 Flash and 5 custom Ethereum MCP tools.

## Try It

```bash
POST /diagnose
{"tx_hash": "0x..."}
```

## What It Diagnoses

| Failure Type | Example |
|---|---|
| `slippage_exceeded` | Uniswap swap — price moved |
| `insufficient_balance` | ERC-20 transfer exceeds balance |
| `insufficient_allowance` | Router not approved to spend tokens |
| `out_of_gas` | Gas limit too low |
| `contract_revert` | Custom Solidity error, require() |
| `unauthorized` | Access control failure |

## Architecture

```
User → FastAPI Server → Gemini 2.5 Flash (agentic loop)
                             ↓
                    ChainObserver MCP Server
                    ├── get_transaction_receipt
                    ├── decode_revert_reason
                    ├── get_contract_info
                    ├── simulate_transaction
                    └── get_pool_info
                             ↓
                    Ethereum RPC + Etherscan + 4byte.directory
```

## Benchmarks

- **100% accuracy** on 4 real mainnet failed transactions
- **21.8s average** diagnosis time
- **3.25 tool calls** average

## Setup

```bash
pip install -e .
cp .env.example .env  # add GEMINI_API_KEY
python server.py       # starts at http://localhost:7860
```

## Built For

ETHGlobal Lisbon 2026 — on-chain observability track.
