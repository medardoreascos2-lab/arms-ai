# Phase 8.5 Local Model Progress Ledger

Date: 2026-10-04
Branch: phase8.5/local-model-runtime
Phase 8 base: d750298ab35f40f894a08a3e50a244c13e5454ba

| Milestone | State | Evidence | Gate |
|---|---|---|---|
| Phase 8.5A hardware/runtime selection | COMPLETE | Read-only hardware and runtime evaluation | PASS |
| Phase 8.5B controlled runtime/model installation | COMPLETE | Ollama 0.35.1 and qwen3.5:9b-q4_K_M on D:\MEDAR | PASS_WITH_LIMITATIONS |
| Phase 8.5C local soak and prompt tuning | COMPLETE | 218-prompt v3 soak; 504 dependent tests | FAIL: 12.963 GiB working set exceeds 12 GiB guard |
| Phase 8.5D fast model comparison | COMPLETE | Identical 218-prompt 9B/4B soaks; official 4B digest and license verified | C: KEEP_9B_ONLY |

## Current decision

Qwen3.5 9B passes every measured quality, schema, factual, financial safety,
memory, and authority check. Its final Phase 8.5D process peak is inside the
fixed 12 GiB guard with a margin warning.

Qwen3.5 4B reduces peak working set and VRAM and improves median latency and
throughput, but repeatedly fails mandatory labels in Spanish, English, NQ, and
stocks prompts. It is not approved as the fast model. No router or default model
configuration changed.

- RECOMMENDED_PRIMARY_MODEL=qwen3.5:9b-q4_K_M
- RECOMMENDED_FAST_MODEL=NONE
- SIMULTANEOUS_RESIDENT_MODELS=1
- SECOND_MODEL_DOWNLOAD_COMPLETE=TRUE
- BROKER_AUTHORITY=FALSE
- PAPER_AUTHORITY=FALSE
- LIVE_AUTHORITY=FALSE
- PRODUCTION_AUTONOMY=FALSE
- UNRESTRICTED_COMPUTER_CONTROL=FALSE
- PUSH_PERFORMED=FALSE
