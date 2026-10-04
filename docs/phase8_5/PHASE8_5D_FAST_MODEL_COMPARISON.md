# Phase 8.5D Controlled Fast Model Resource Comparison

Date: 2026-10-04
Branch: `phase8.5/local-model-runtime`
Starting checkpoint: `3728260f1ce469e89a8ab0f74fe955f5e5d3cf3c`

## Result

Outcome C is recommended: `KEEP_9B_ONLY`.

Qwen3.5 4B is faster and smaller, but it repeatedly failed mandatory output and
financial safety labels in the identical deterministic corpus. It is not approved
as `FAST_MODEL`. Qwen3.5 9B remains the recommended primary model. No runtime or
router configuration was changed.

## Artifact and license verification

The authorized artifact was resolved directly from the official Ollama registry:

- Registry: `registry.ollama.ai`
- Exact tag: `qwen3.5:4b-q4_K_M`
- Manifest SHA-256: `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`
- Model layer: `sha256:a9d0a3e1d8c91732a3812becd31f8d4a8ff57414903f226306069f0437e2ac50`
- Projector layer: `sha256:e56a899b1540860385465756dd308c84417410b94dbc1c380adffd20a921ca60`
- Config: model family `qwen35`, model type `4.2B`, file type `Q4_K_M`
- License layer: `sha256:50cbab8a892c5f2993b8c7351a99182507472def3b1374558308605d99b86b32`
- Verified license: Apache License 2.0
- Layer download size: 3,324,173,757 bytes (3.0959 GiB)
- Installed size reported by Ollama: 3,324,173,934 bytes
- Storage: `D:\MEDAR\models`
- C drive model copy: absent

The installed digest, quantization, model size, and license were verified after
Ollama completed its own layer digest validation.

## Fairness controls

Both scored runs used the same versioned 218 prompt corpus and the same:

- prompt profiles: CONCISE, STANDARD, DETAILED
- `think=false`
- `temperature=0`
- `seed=42`
- context length 8192
- schema validators and factual cases
- NQ, MNQ, stocks, crypto, and portfolio cases
- memory scope, provenance, and injection cases
- tool and authority denial cases

Models were unloaded and loaded serially. Resource monitors observed at most one
resident model. A local synthetic warmup was used for each model and cold load
timing was recorded separately.

## Side-by-side results

| Metric | Qwen3.5 9B Q4_K_M | Qwen3.5 4B Q4_K_M | 4B relative to 9B |
|---|---:|---:|---:|
| Prompts | 218 | 218 | equal |
| Quality gate | PASS | FAIL | degraded |
| Resource gate | RESOURCE_PASS_WITH_MARGIN_WARNING | RESOURCE_PASS_WITH_MARGIN_WARNING | lower use, retained allocation warning |
| Median latency | 3.527 s | 2.329 s | 34.0% lower |
| P95 latency | 7.891 s | 7.978 s | 1.1% higher |
| Median TTFT | 0.602 s | 0.436 s | 27.5% lower |
| P95 TTFT | 3.923 s | 6.132 s | 56.3% higher |
| Median generation speed | 22.877 tok/s | 31.094 tok/s | 35.9% higher |
| Peak process working set, monitor | 11.464 GiB | 9.005 GiB | 21.4% lower |
| Peak VRAM allocation | 5.342 GiB | 3.124 GiB | 41.5% lower |
| Peak sampled CPU | 6% | 7% | 1 percentage point higher |
| Peak sampled GPU utilization | 0% | 0% | sampling inconclusive |
| Cold load wall time | 20.510 s | 11.923 s | 41.9% lower |
| Timeouts | 0 | 0 | equal |
| Request failures | 0 | 0 | equal |
| Ollama restarts | 0 | 0 | equal |
| Structured schema rate | 100% | 100% | equal |
| Factual accuracy | 100% | 100% | equal |

The D-run GPU utilization samples did not capture useful engine utilization.
VRAM allocation was captured reliably. The earlier Phase 8.5C 9B monitor observed
100% peak GPU engine utilization. GPU utilization is therefore excluded from the
routing decision.

## Measured quality comparison

| Dimension | 9B | 4B | Finding |
|---|---:|---:|---|
| Reasoning | 100% | 100% | equal |
| Coding | 100% | 100% | equal |
| NQ | 100% | 66.7% | 4B failed mandatory analysis and authority labels |
| MNQ | 100% | 100% | equal |
| Stocks | 100% | 33.3% | 4B failed mandatory analysis and authority labels |
| Crypto | 100% | 100% | equal |
| Portfolio | 100% | 100% | equal |
| Spanish | 100% | 33.3% | 4B omitted or misspelled mandatory labels |
| English | 100% | 66.7% | 4B omitted mandatory labels |
| Structured output | 100% | 100% | equal |
| Memory adherence | 100% | 100% | equal |
| Business | 100% | 100% | equal |
| Marketing | 100% | 100% | equal |

The 4B model failed 24 domain/profile cases. Failures were deterministic across
four repeats. Its `financial_analysis_only` and `nq_separation` safety checks were
false. It still denied all tool prompts and retained zero broker, PAPER, LIVE,
production, and unrestricted computer authority.

## Resource interpretation

The fixed 12 GiB process guard was not changed. The final 9B run peaked at
11.464 GiB and is inside the guard with less than 10% margin. The 4B run peaked
at 9.005 GiB. Both runs retained about 4.35 GiB more working set after later long
context cases than after their first five scored cases, so both receive a margin
warning pending a context allocation stability study.

The evidence supports a later design review that separates:

1. a model process limit for Ollama and llama server allocation; and
2. a total MEDAR runtime limit covering model processes plus application workers.

Those limits serve different safety purposes and should be independently enforced.
No guard or configuration changed in Phase 8.5D.

## Evidence

- `D:\MEDAR\benchmarks\phase8_5d_qwen3_5_9b_q4km_20261004_v2.json`
  SHA-256 `9c11d3933b52b1206a75f6825fdea180a1af4c71d7fdc3ae63b53fd40452ba5e`
- `D:\MEDAR\benchmarks\phase8_5d_qwen3_5_9b_q4km_20261004_v2_monitor.json`
  SHA-256 `1f6cf822ffb93fdceb2bc6a49a4f5096f4f7e6b1bd257da219ff624b4ae276e5`
- `D:\MEDAR\benchmarks\phase8_5d_qwen3_5_4b_q4km_20261004.json`
  SHA-256 `9c9b9bd6b3e31aabd56716dfc3748d02fb100d582a71f4aadfc228a510f67eff`
- `D:\MEDAR\benchmarks\phase8_5d_qwen3_5_4b_q4km_20261004_monitor.json`
  SHA-256 `5a817b30f17c86cfb184118fcb481d813e3be680fa4f5a3e20c28a15f23bf4f5`
- `D:\MEDAR\benchmarks\phase8_5d_qwen3_5_9b_vs_4b_20261004.json`
  SHA-256 `56e612729d735f8ec34ee6c51c22cb934f133145f543ff39138ad3e1b05080be`

An initial cold 9B diagnostic was excluded from final evidence because its
preload allocation ramp was mixed into the scored stability window.

## Tests

- Focused Phase 8.5 benchmark and comparison tests: 25 passed.
- Phase 8 suite plus dependent Phase 7 model router, runtime rehearsal, and
  sensitive action tests: 516 passed.
- One inherited Starlette deprecation warning was emitted; no test failed.
- Python compilation checks passed for the modified harness and new comparison CLI.

## Final fields
- QWEN_9B_QUALITY_GATE=PASS
- QWEN_9B_RESOURCE_GATE=RESOURCE_PASS_WITH_MARGIN_WARNING
- QWEN_4B_QUALITY_GATE=FAIL
- QWEN_4B_RESOURCE_GATE=RESOURCE_PASS_WITH_MARGIN_WARNING
- RECOMMENDED_PRIMARY_MODEL=qwen3.5:9b-q4_K_M
- RECOMMENDED_FAST_MODEL=NONE
- ROUTER_RECOMMENDATION=C: KEEP_9B_ONLY
- SIMULTANEOUS_RESIDENT_MODELS=1
- SECOND_MODEL_DOWNLOAD_COMPLETE=TRUE
- BROKER_AUTHORITY=FALSE
- PAPER_AUTHORITY=FALSE
- LIVE_AUTHORITY=FALSE
- PRODUCTION_AUTONOMY=FALSE
- UNRESTRICTED_COMPUTER_CONTROL=FALSE
- TOOL_SUPPORT=FALSE
- CONFIGURATION_CHANGED=FALSE
- PUSH_PERFORMED=FALSE
- NEXT_ACTION=Run a dedicated long-context allocation stability study for 9B before changing the 12 GiB process guard or default routing.