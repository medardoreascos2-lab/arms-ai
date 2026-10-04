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
| Phase 8.5E long-context stability | COMPLETE | 100 cycles across 2K/4K/8K/12K/16K plus 30/60/120s idle observations | PASS; STABLE_HIGH_WATER_MARK |

## Current decision

Qwen3.5 9B remains the only approved local model. The corrected Phase 8.5E
matrix passed all Spanish, English, JSON, NQ, MNQ, memory, long-context, and
authority-denial cases at every tested context. Its model-process peak was
8.601 GiB, peak VRAM was 5.486 GiB, and minimum available host RAM was
11.347 GiB. Every idle window was flat.

The current 12 GiB model-process guard remains appropriate. Keep 8,192 as the
initial context and permit up to 16,384 only within the tested local resource
envelope. A separate 16 GiB total MEDAR runtime guard is recommended for a
later approved enforcement phase. No guard, router, or execution configuration
changed in Phase 8.5E.

Qwen3.5 4B remains installed for inventory only. It is not approved as a fast
model and was not loaded or invoked during the final study.

- QWEN_9B_LONG_CONTEXT_STATUS=PASS
- MEMORY_LEAK_CLASSIFICATION=STABLE_HIGH_WATER_MARK
- RECOMMENDED_PRIMARY_MODEL=qwen3.5:9b-q4_K_M
- RECOMMENDED_FAST_MODEL=NONE
- RECOMMENDED_INITIAL_CONTEXT=8192
- RECOMMENDED_MAX_CONTEXT=16384
- CURRENT_MODEL_PROCESS_GUARD_GB=12
- RECOMMENDED_TOTAL_MEDAR_RUNTIME_GUARD_GB=16
- SIMULTANEOUS_RESIDENT_MODELS=1
- BROKER_AUTHORITY=FALSE
- PAPER_AUTHORITY=FALSE
- LIVE_AUTHORITY=FALSE
- PRODUCTION_AUTONOMY=FALSE
- UNRESTRICTED_COMPUTER_CONTROL=FALSE
- PUSH_PERFORMED=FALSE
