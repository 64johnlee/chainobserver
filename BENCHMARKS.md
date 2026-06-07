# ChainObserver Benchmarks

Testing across 4 real failed mainnet transactions covering the main failure categories.

## Target Metrics
- Diagnosis time: < 2 minutes (excluding API rate-limit waits)
- Tool calls: ≤ 5
- Classification accuracy: correct failure_type

---

## Test Results

### TX-1: INSUFFICIENT_ALLOWANCE — Uniswap Universal Router
**Hash:** `0xaa78010df34b38c16b5168ada399b840162bbf3566b398025cad7ba69581bab5`  
**Contract:** `0x66a9893c…` (Uniswap Universal Router — `execute(bytes,bytes[],uint256)`)  
**Revert:** `TRANSFER_FROM_FAILED`

| Metric | Result |
|--------|--------|
| Diagnosis Time | **18.6s** |
| Tool Calls | **3** |
| failure_type | `insufficient_allowance` ✅ |
| Confidence | **high** |
| Root Cause | "Contract not approved to spend ERC-20 tokens from sender's address" |
| Fix | "Call `approve()` on the token contract first" |

---

### TX-2: SLIPPAGE — DEX swap
**Hash:** `0x791cddd199261dbca8562001c55a0b11aa51cf22ba0681d926dfe85c9274f7d5`  
**Contract:** `0x278d858f…` (DEX aggregator — `0x70521ae9`)  
**Revert:** `INSUFFICIENT_OUTPUT_AMOUNT`

| Metric | Result |
|--------|--------|
| Diagnosis Time | **21.4s** |
| Tool Calls | **3** |
| failure_type | `slippage_exceeded` ✅ |
| Confidence | **high** |
| Root Cause | "Actual output amount from DEX swap was less than the minimum acceptable (slippage tolerance exceeded)" |
| Fix | "Increase slippage tolerance in DEX settings and retry" |

---

### TX-3: INSUFFICIENT_BALANCE — USDC direct transfer
**Hash:** `0xb7d9acfa1450a0d54fe09c1d83c87598220fc97af44b81669dac6eedff997f19`  
**Contract:** `0xA0b869…` (USDC — `transfer(address,uint256)`)  
**Revert:** `ERC20: transfer amount exceeds balance`

| Metric | Result |
|--------|--------|
| Diagnosis Time | **11.9s** |
| Tool Calls | **3** |
| failure_type | `insufficient_balance` ✅ |
| Confidence | **high** |
| Root Cause | "Sender attempted to transfer more USDC than they hold in their wallet" |
| Fix | "Ensure sender address has sufficient USDC balance before calling transfer()" |

---

### TX-4: CONTRACT_REVERT — OpenSea Seaport custom error
**Hash:** `0xd546940038094f8a50254f8d75ed9dfba2c692d38b0c857a167d2f941982cde8`  
**Contract:** `0x000000…68` (Seaport — `fulfillAdvancedOrder(…)`)  
**Revert:** custom error `0xa1148100` (InvalidSignature / TransferFromIncorrectOwner)

| Metric | Result |
|--------|--------|
| Diagnosis Time | **~36s** (166s wall including 2×65s rate-limit wait) |
| Tool Calls | **4** |
| failure_type | `contract_revert` ✅ |
| Confidence | **high** |
| Root Cause | "Signature for the advanced Seaport order was invalid — order signature mismatch" |
| Fix | "Verify the order signature matches the order parameters; NFT may have been transferred or sold" |

---

## Summary

| Test | Hash (prefix) | Time | Calls | Type | Result |
|------|--------------|------|-------|------|--------|
| TX-1 Allowance | `0xaa780…` | 18.6s | 3 | `insufficient_allowance` | ✅ PASS |
| TX-2 Slippage | `0x791cd…` | 21.4s | 3 | `slippage_exceeded` | ✅ PASS |
| TX-3 Balance | `0xb7d9a…` | 11.9s | 3 | `insufficient_balance` | ✅ PASS |
| TX-4 Revert | `0xd5469…` | ~36s* | 4 | `contract_revert` | ✅ PASS |

**Overall: 4/4 correct (100% accuracy)**  
**Avg time (net): 21.8s**  
**Avg tool calls: 3.25 / 5 target**

*TX-4 elapsed 166s due to free-tier rate-limit waits (2×65s). Net diagnosis was ~36s.

---

## Notes

- Gemini 2.5 Flash free tier: 5 RPM. Space tests ≥60s apart to avoid rate limits.
- Agent correctly decoded custom Solidity error (`0xa1148100`) via contract context inference.
- 4byte.directory resolved `0xe7acab24` → `fulfillAdvancedOrder(…)` enabling correct Seaport identification.
- All 3 standard tools fired per diagnosis: `get_transaction_receipt` → `decode_revert_reason` → `get_contract_info`.
- TX-4 used 4 tools (added `simulate_transaction`) for the ambiguous custom error case.

---

*Generated Day 10 of ETHGlobal Lisbon 25-day sprint (June 8, 2026)*
