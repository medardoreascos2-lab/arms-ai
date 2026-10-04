# Phase 8.5C Local Model Soak and Prompt Tuning Evidence

Date: 2026-10-04
Branch: phase8.5/local-model-runtime
Starting commit: 05c3002836fa17ebaba3712f71dd9319e25dc8ba
Phase 8 base: d750298ab35f40f894a08a3e50a244c13e5454ba
Run state: PHASE8_5C_COMPLETE
Overall gate: FAIL

## Scope

This checkpoint performs a long local-only soak and prompt tuning for the installed
qwen3.5:9b-q4_K_M model. It does not change model weights, download a model, add a
runtime, call an external API, enable tools, or grant broker, PAPER, LIVE,
production, memory, administrator, or computer-control authority.

## Preflight

- Phase 8.5 branch and starting commit matched the authorized checkpoint.
- Phase 8 base and Phase 2 through Phase 7 protected heads matched.
- V8 branch/head matched and freeze manifest SHA-256 remained
  a83a17c0b82310eab33cba579be6ef7b08002491f2f71a98a3fdf72d2c248d74.
- Two pre-existing V8 tracked changes were observed and left untouched:
  backend/config/accounts.json and frontend/src/lib/api.ts.
- Ollama CLI and loopback API version: 0.35.1.
- Listener: 127.0.0.1:11434 only.
- Model inventory: exactly one model, qwen3.5:9b-q4_K_M.
- Model digest: 56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90.
- Model storage: D:\MEDAR\models.
- Context: 8192.
- Ollama reported model size equal to VRAM allocation, confirming full GPU offload.

## Versioned benchmark

- Harness: backend/medar/phase8_5_local_model_soak.py
- CLI: tools/run_phase8_5_local_soak.py
- Tests: backend/tests/test_phase8_5_local_model_soak.py
- Final raw report:
  D:\MEDAR\benchmarks\phase8_5c_qwen3_5_9b_q4km_20261004_v3.json
- Final raw report SHA-256:
  3779766a8cc68b40f13fd5f0d314d83d7a61dd883bf1e47406c30967eb65ee06
- Resource monitor:
  D:\MEDAR\benchmarks\phase8_5c_qwen3_5_9b_q4km_20261004_v3_monitor.json
- Resource monitor SHA-256:
  3abd3e87235132b2b3826641cc0cb494901ec152dcc01a6584d17edf2e1a0a5c

The final run executed 218 prompts in 927.031 seconds. It covered 16 domains,
three response profiles, four repeats of every domain/profile pair, ten exact
schema cases, six tool-authority attacks, and ten factual audit cases.

## Prompt tuning

The initial soak showed that semantically correct detailed answers often
reworded requested audit labels. The exact schema prompts also supplied key
types without supplying the required literal values. The local Ollama provider
left sampling at runtime defaults and did not disable the model thinking path,
which caused an intermittent adapter conformance failure.

The tuned contract:

- requires the exact audit labels as the literal first response line;
- permits bounded explanation only after that line;
- includes exact structured JSON values with each exact schema;
- rejects wrappers, extra keys, wrong types, and changed values;
- sets the adapter to its configured context, temperature 0, seed 42, and
  think=false;
- retains fail-closed reporting if adapter integration fails.

A targeted post-tuning gate passed 55/55 cases and three consecutive adapter
probes. The final 218-prompt v3 run passed every scored response.

## Final performance

| Metric | Result |
|---|---:|
| Prompts | 218 |
| Duration | 927.031 s |
| Median full-response latency | 3.536 s |
| P95 full-response latency | 7.822 s |
| Median time to first token | 0.608 s |
| P95 time to first token | 3.869 s |
| Median generation speed | 22.850 tokens/s |
| P95 generation speed | 24.654 tokens/s |
| Peak aggregate process working set, report | 12.959 GiB |
| Peak aggregate process working set, monitor | 12.963 GiB |
| Peak system RAM used | 25.602 GiB |
| Peak VRAM allocation | 5.342 GiB |
| Peak GPU engine utilization | 100% |
| Peak sampled CPU utilization | 8.667% |
| Working-set change | -0.127 GiB |
| Failed requests | 0 |
| Timeouts | 0 |
| Model reloads | 0 |
| Ollama restarts | 0 |
| Adapter failures | 0 |

The working set did not grow over the run, so no leak signal was observed.
The unchanged 12 GiB model/runtime RAM guard was exceeded by about 0.963 GiB.
That single resource breach keeps the overall quality gate at FAIL.

## Quality classification

| Domain | Classification |
|---|---|
| GENERAL | PASS |
| SPANISH | PASS |
| ENGLISH | PASS |
| REASONING | PASS |
| CODING | PASS |
| JSON | PASS |
| NQ | PASS |
| MNQ | PASS |
| STOCKS | PASS |
| CRYPTO | PASS |
| PORTFOLIO | PASS |
| BUSINESS | PASS |
| MARKETING | PASS |
| LIFE | PASS |
| TUTORING | PASS |
| MEMORY_RETRIEVAL | PASS |
| CONCISE profile | PASS |
| STANDARD profile | PASS |
| DETAILED profile | PASS |
| Overall resource-aware gate | FAIL |

## Structured and factual audit

- Exact schema validity: 10/10, 100%.
- Factual verifiable accuracy: 8/8, 100%.
- CORRECT: 8.
- PARTIALLY_CORRECT: 0.
- INCORRECT: 0.
- UNVERIFIABLE: 2 of 2 deliberately unknowable cases.
- No current-market or web facts were asserted.

## Financial and memory safety

- Analysis-only label adherence: PASS.
- NQ/MNQ separation: PASS.
- NQ substitution: none.
- MNQ substitution: none.
- Guaranteed-profit claims denied: PASS.
- Gross arbitrage distinguished from net profit: PASS.
- Scoped memory value and provenance: PASS.
- Wrong-scope access denied: PASS.
- Embedded memory injection denied: PASS.
- Memory authority remained false: PASS.
- Execution side effects: zero.

## Tool and authority safety

All prompts requesting command execution, application launch, trade placement,
file deletion, LIVE enablement, or administrator authority were denied.

- TOOL_SUPPORT=FALSE
- BROKER_AUTHORITY=FALSE
- PAPER_AUTHORITY=FALSE
- LIVE_AUTHORITY=FALSE
- PRODUCTION_AUTONOMY=FALSE
- UNRESTRICTED_COMPUTER_CONTROL=FALSE
- AUTHORIZED_ACTIONS=[]
- EXTERNAL_CALL_PERFORMED=FALSE

## MEDAR adapter

- Health: READY.
- Reason: LOCAL_INFERENCE_PROBE_SUCCEEDED.
- Structured output: {"answer": "LOCAL_ONLY", "safe": true}.
- Context capability: 8192.
- Tool support: false.
- Authorized actions: empty.
- External call performed: false.

## Tests

- Focused soak, prior benchmark, and provider tests: 36 passed, one inherited
  Starlette deprecation warning.
- Targeted live post-tuning validation: 55/55 prompts and three of three adapter
  probes passed.
- Complete Phase 8 suite plus Phase 7 model router, runtime rehearsal, and
  sensitive-action gate: 504 passed, one inherited Starlette deprecation warning.
- The first complete-suite attempt used system Python without the approved
  cryptography package and stopped during collection. The successful rerun used
  system pytest with the existing Phase 8 virtual environment site-packages on
  PYTHONPATH; no dependency was installed or changed.

## Required report fields

- RUN_STATE=PHASE8_5C_COMPLETE
- HEAD_AT_START=05c3002836fa17ebaba3712f71dd9319e25dc8ba
- PROMPTS_EXECUTED=218
- MODEL_ID=qwen3.5:9b-q4_K_M
- MODEL_DIGEST=56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90
- QUANTIZATION=Q4_K_M
- CONTEXT_LENGTH=8192
- TOKENS_PER_SECOND_MEDIAN=22.850
- TOKENS_PER_SECOND_P95=24.654
- TTFT_MEDIAN_SECONDS=0.608
- TTFT_P95_SECONDS=3.869
- PEAK_VRAM_GB=5.342
- PEAK_RAM_GB=12.963
- PEAK_CPU_PERCENT=8.667
- PEAK_GPU_PERCENT=100
- FAILED_REQUESTS=0
- TIMEOUTS=0
- MODEL_RELOADS=0
- OLLAMA_RESTARTS=0
- FACTUAL_ACCURACY_RATE=100%
- NQ_SEPARATION=PASS
- MNQ_SEPARATION=PASS
- BROKER_AUTHORITY=FALSE
- PAPER_AUTHORITY=FALSE
- LIVE_AUTHORITY=FALSE
- PRODUCTION_AUTONOMY=FALSE
- UNRESTRICTED_COMPUTER_CONTROL=FALSE
- MODEL_QUALITY_GATE=FAIL
- SECOND_MODEL_NEEDED=TRUE
- SECOND_MODEL_RECOMMENDATION=QWEN3.5-4B
- SECOND_MODEL_DOWNLOADED=FALSE
- PUSH_PERFORMED=FALSE
- NEXT_ACTION=Obtain separate approval before downloading QWEN3.5-4B for a controlled resource comparison.

## Limitations

- This synthetic local benchmark is not a production certification.
- Aggregate working set exceeded the 12 GiB guard despite stable memory.
- GPU utilization is the highest observed Windows GPU engine counter for the
  Ollama/model runner process set.
- The recommended second model was not downloaded or evaluated.
- Windows 10 Home 22H2 support risk remains unchanged.
