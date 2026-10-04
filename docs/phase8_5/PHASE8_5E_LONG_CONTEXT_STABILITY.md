# Phase 8.5E Long-Context Allocation Stability Study

Date: 2026-10-04
Branch: `phase8.5/local-model-runtime`
Starting checkpoint: `be005c0517baa39900bb7d93900bebeab1d5fb39`

## Result

`qwen3.5:9b-q4_K_M` passed the controlled long-context study across
2K, 4K, 8K, 12K, and 16K contexts. The final run completed 100 synthetic
cycles and all required 30, 60, and 120 second idle observations without a
failed request, timeout, model restart, Ollama restart, or resource-pressure
stop.

Memory is classified as `STABLE_HIGH_WATER_MARK`. The runner retained its
largest allocation at idle, but allocation did not continue growing during any
idle window. Repeated medium workloads were flat at each context. Larger prompt
groups raised the retained high water mark as expected.

## Scope and controls

The study used only:

- Primary model: `qwen3.5:9b-q4_K_M`
- Exact digest: `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`
- Local endpoint: `http://127.0.0.1:11434`
- Ollama: `0.35.1`
- `think=false`
- `temperature=0`
- `seed=42`
- One resident model
- Synthetic prompts and ephemeral runtime state

The installed 4B model was checked only in inventory. It was never routed,
loaded, or used for inference. Both models were unloaded when the study ended.

The unchanged safety thresholds were:

- Model process working set: 12 GiB
- Model VRAM: 7 GiB
- Early VRAM pressure stop: 6.75 GiB
- Minimum available host RAM: 8 GiB
- Minimum commit headroom: 8 GiB

The harness would stop with `STOP_RESOURCE_PRESSURE` if any safety threshold
was crossed. No threshold was crossed.

## Test matrix

Each context ran exactly 20 cycles:

1. cold start
2. warm start
3. Spanish
4. English
5. structured JSON
6. NQ separation
7. MNQ separation
8. scoped memory retrieval
9. authority denial
10. four repeated short prompts
11. four repeated medium prompts
12. long context
13. long-context memory retrieval
14. long-context authority denial

Each level then remained loaded for cumulative 30, 60, and 120 second idle
observations.

## Resource evidence

| Context | Peak model WS GiB | Post-idle 120s GiB | Peak prompt tokens | Median latency s | Median TTFT s | Median tok/s |
|---:|---:|---:|---:|---:|---:|---:|
| 2,048 | 7.906 | 7.906 | 1,887 | 2.198 | 0.616 | 24.905 |
| 4,096 | 8.054 | 8.032 | 3,615 | 2.382 | 0.639 | 23.131 |
| 8,192 | 8.425 | 8.385 | 7,071 | 2.337 | 0.628 | 23.332 |
| 12,288 | 8.385 | 8.290 | 10,527 | 2.317 | 0.630 | 24.373 |
| 16,384 | 8.601 | 8.474 | 14,019 | 2.594 | 0.672 | 21.322 |

Run-wide observations:

- Peak model working set: 8.601 GiB
- Peak Ollama total working set: 8.698 GiB
- Peak VRAM allocation: 5.486 GiB
- Peak sampled GPU engine utilization: 100%
- Peak system commit: 28.312 GiB
- Minimum available host RAM: 11.347 GiB
- Model reloads: 5 expected cold loads
- Model restarts: 0
- Ollama restarts: 0
- Timeouts: 0
- Failed requests: 0

Windows GPU engine counters are bounded to 100% in the harness. Ollama
`/api/ps` supplies the model-specific VRAM allocation used for the safety
decision.

## Quality and safety evidence

All final v2 cases passed at every context:

- Spanish: pass
- English: pass
- structured JSON: pass
- NQ separation: pass
- MNQ separation: pass
- scoped memory retrieval: pass
- long-context retrieval: pass
- authority denial: pass
- quality regression: false

The model had no tools and no broker, PAPER, LIVE, production, or unrestricted
computer authority. No execution adapter or trading path was invoked.

## Guard recommendation

Outcome A is recommended: `12 GiB remains appropriate`.

The measured 8.601 GiB model-process peak leaves 3.399 GiB under the current
guard. The current guard was not changed. A future total MEDAR runtime guard of
16 GiB is recommended to bound the model process plus local application workers
as a separate host-level control.

- Recommended model process guard: 12 GiB
- Recommended total MEDAR runtime guard: 16 GiB
- Recommended initial context: 8,192
- Recommended maximum context: 16,384

These are local-development recommendations only. No runtime configuration,
router, or execution authority changed.

## Evidence

Final evidence:

- `D:\MEDAR\benchmarks\phase8_5e_qwen3_5_9b_long_context_20261004_v2.json`
- SHA-256: `1d66ba06d73996a842537e3337225092a927cb7e3de6bccaff023cd9cdb1968e`
- Duration: 1,468.856 seconds

The first diagnostic report,
`D:\MEDAR\benchmarks\phase8_5e_qwen3_5_9b_long_context_20261004.json`,
is excluded from the final decision. Its prompt said"��y��y�copy exactl{�u���] before the
instruction clause, causing the model to copy that clause rather than the
following labels. Its initial classifier also compared deliberately increasing
prompt groups as identical workloads and counted a prior runner shutdown as a
restart. The v2 harness corrected those evidence defects, passed focused tests,
and repeated the complete matrix.

## Final fields

- QWEN_9B_LONG_CONTEXT_STATUS=PASS
- MEMORY_LEAK_CLASSIFICATION=STABLE_HIGH_WATER_MARK
- PEAK_2K_GB=7.906
- PEAK_4K_GB=8.054
- PEAK_8K_GB=8.425
- PEAK_12K_GB=8.385
- PEAK_16K_GB=8.601
- POST_IDLE_2K_GB=7.906
- POST_IDLE_4K_GB=8.032
- POST_IDLE_8K_GB=8.385
- POST_IDLE_12K_GB=8.290
- POST_IDLE_16K_GB=8.474
- PEAK_VRAM_GB=5.486
- MIN_AVAILABLE_HOST_RAM_GB=11.347
- MODEL_RESTARTS=0
- OLLAMA_RESTARTS=0
- TIMEOUTS=0
- FAILED_REQUESTS=0
- QUALITY_REGRESSION=FALSE
- NQ_SEPARATION=TRUE
- MNQ_SEPARATION=TRUE
- CURRENT_12_GIB_GUARD_RECOMMENDATION=A: 12 GiB remains appropriate
- RECOMMENDED_MODEL_PROCESS_GUARD_GB=12
- RECOMMENDED_TOTAL_MEDAR_RUNTIME_GUARD_GB=16
- RECOMMENDED_INITIAL_CONTEXT=8192
- RECOMMENDED_MAX_CONTEXT=16384
- PRIMARY_MODEL=qwen3.5:9b-q4_K_M
- FAST_MODEL=NONE
- BROKER_AUTHORITY=FALSE
- PAPER_AUTHORITY=FALSE
- LIVE_AUTHORITY=FALSE
- PRODUCTION_AUTONOMY=FALSE
- UNRESTRICTED_COMPUTER_CONTROL=FALSE
- TOOL_SUPPORT=FALSE
- PUSH_PERFORMED=FALSE
- NEXT_ACTION=Keep 9B at an 8K initial context, permit 16K only within the tested local guard envelope, and add separate model-process and total-runtime enforcement in a later approved phase.
