# Phase 8.5 Local Model Progress Ledger

Date: 2026-10-04
Branch: phase8.5/local-model-runtime
Phase 8 base: d750298ab35f40f894a08a3e50a244c13e5454ba

| Milestone | State | Evidence | Gate |
|---|---|---|---|
| Phase 8.5A hardware/runtime selection | COMPLETE | Read-only hardware and runtime evaluation | PASS |
| Phase 8.5B controlled runtime/model installation | COMPLETE | Ollama 0.35.1 and qwen3.5:9b-q4_K_M on D:\MEDAR | PASS_WITH_LIMITATIONS |
| Phase 8.5C local soak and prompt tuning | COMPLETE | 218-prompt v3 soak; 504 dependent tests | FAIL: 12.963 GiB working set exceeds 12 GiB guard |

## Current decision

Functional quality, structured output, factual scoring, NQ/MNQ separation,
financial safety, memory isolation, authority denial, adapter integration, and
runtime stability passed. The installed 9B model exceeded the fixed aggregate
RAM guard without showing a memory leak.

No second model was downloaded. The next controlled comparison candidate is
QWEN3.5-4B, subject to separate approval.

- BROKER_AUTHORITY=FALSE
- PAPER_AUTHORITY=FALSE
- LIVE_AUTHORITY=FALSE
- PRODUCTION_AUTONOMY=FALSE
- UNRESTRICTED_COMPUTER_CONTROL=FALSE
- PUSH_PERFORMED=FALSE
