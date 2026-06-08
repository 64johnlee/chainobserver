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

[![Tests](https://github.com/64johnlee/chainobserver/actions/workflows/test.yml/badge.svg)](https://github.com/64johnlee/chainobserver/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![ETHGlobal Lisbon 2026](https://img.shields.io/badge/ETHGlobal-Lisbon%202026-purple)](https://ethglobal.com)
[![Demo Video](https://img.shields.io/badge/Demo-YouTube-red)](https://youtu.be/Z5fpDfPj6fU)

> **AI agent that diagnoses failed Ethereum transactions in under 30 seconds**

Paste a failed tx hash → get root cause + fix, powered by **Gemini 2.5 Flash** and 5 custom Ethereum MCP tools. Supports mainnet, Arbitrum, Base, Optimism, and Polygon.

## Demo



## Supported Failure Types

| Type | Signal | Example |
|------|--------|---------|
|  | INSUFFICIENT_OUTPUT_AMOUNT | Uniswap swap price moved |
|  | transfer amount exceeds balance | USDC transfer |
|  | TRANSFER_FROM_FAILED | ERC-20 approve not called |
|  | gas_used ≥ 98% of limit | complex DeFi tx |
|  | custom error / require() | Seaport, ParaSwap |
|  | not owner / missing role | Access control |
|  | low pool reserves | thin DEX pool |

## Quick Start

Obtaining file:///mnt/c/WINDOWS/system32
╭──────────────────────────────────────────────────────────────────────────────╮
│ ChainObserver · tx 0xYOUR_TX_HASH                                            │
│ Gemini 2.5 Flash · Ethereum MCP tools                                        │
╰──────────────────────────────────────────────────────────────────────────────╯


✓ Diagnosis complete in 2.5s · 0 tool calls

╭────────────────────────── ChainObserver Diagnosis ───────────────────────────╮
│  Root cause    See full analysis below                                       │
│  Failure type  unknown                                                       │
│  Confidence    medium                                                        │
│  Affected      —                                                             │
│  Fix           —                                                             │
│  Time          2.47s · 0 tool calls                                          │
╰──────────────────────────────────────────────────────────────────────────────╯

── Full Analysis ──
Please replace `0xYOUR_TX_HASH` with a real transaction hash. I cannot diagnose 
the transaction without it.

## API



Response:


## Supported Chains

| Chain | ID | RPC Default |
|-------|----|-------------|
| Ethereum | 1 |  |
| Arbitrum One | 42161 |  |
| Base | 8453 |  |
| Optimism | 10 |  |
| Polygon | 137 |  |

## Architecture



## Benchmarks

**4/4 agent diagnoses correct · 21.8s avg · 3.25 tool calls**

| TX | Type | Time | Calls |
|----|------|------|-------|
| Uniswap Universal Router |  | 18.6s | 3 |
| DEX swap |  | 21.4s | 3 |
| USDC transfer |  | 11.9s | 3 |
| Seaport order |  | ~36s | 4 |

**79 tests · 8 real mainnet txs · all 7 failure types verified**

## Configuration

| Env Var | Required | Default | Description |
|---------|----------|---------|-------------|
|  | Yes | — | Gemini 2.5 Flash key |
|  | No | publicnode | Ethereum JSON-RPC |
|  | No | — | For full ABI lookup |
|  | No | false | Vertex AI instead of AI Studio |
|  | No | 7860 | Server port |

## Development



## Built For

**ETHGlobal Lisbon 2026** — On-chain observability track.

Powered by [Gemini 2.5 Flash](https://ai.google.dev/) · [MCP Protocol](https://modelcontextprotocol.io/) · web3.py

---
*Diagnose your failed transactions at [johnlee007/chainobserver](https://huggingface.co/spaces/johnlee007/chainobserver)*
