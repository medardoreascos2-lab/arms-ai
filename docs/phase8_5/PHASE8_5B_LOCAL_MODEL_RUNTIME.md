# Phase 8.5B Local Model Runtime Evidence

Date: 2026-10-04
Branch: `phase8.5/local-model-runtime`
Base: `d750298ab35f40f894a08a3e50a244c13e5454ba`
Status: `PASS_WITH_LIMITATIONS`

## Scope

This checkpoint installs and evaluates one local Ollama model for MEDAR. It does not enable broker, PAPER, LIVE, tool, production, or computer-control authority. All benchmark prompts and memory records are synthetic.

## Source and installer validation

- Runtime source: official `ollama/ollama` GitHub release and official Ollama Windows distribution.
- Runtime version: `0.35.1` (minimum required: `0.30`).
- Installer: `D:\MEDAR\installers\OllamaSetup-v0.35.1.exe`.
- Installer size: `1,580,352,416` bytes.
- Installer SHA-256: `2544c6dc60c57866f5cfbd32b8f7c5ffa5e1f7f0579ca59da5ff20bdc53ad3d2`.
- Authenticode: valid; signer `Ollama Inc.`; DigiCert timestamp present.
- Install location: `D:\MEDAR\Ollama`.
- Install mode: current user, silent, no administrator elevation.
- Login startup shortcut: `D:\MEDAR\Ollama\ollama app.exe`; it inherits the persisted user environment.
- No CUDA, WSL, GPU driver, container runtime, or unrelated dependency was installed.

## Model identity and license

- Model tag: `qwen3.5:9b-q4_K_M`.
- Registry source: `registry.ollama.ai/library/qwen3.5`.
- Immutable manifest digest: `sha256:56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.
- Quantization: `Q4_K_M`.
- Parameter class: `9.0B`.
- Manifest layer bytes: `6,550,825,373`.
- Local inventory bytes: `6,550,825,550` plus manifest metadata.
- Model storage: `D:\MEDAR\models`.
- License layer: Apache License 2.0.
- License digest: `sha256:50cbab8a892c5f2993b8c7351a99182507472def3b1374558308605d99b86b32`.
- Projector digest: `sha256:f836f08f921193f4d6b6a6952dba0a6fb116759d26a757bcb395d570d73976ca` (`921,704,832` bytes).
- Model digest: `sha256:02d45dc1cf451ba2475ac33b301c2dd8f985abe4c182ce04a1f2f5bf0260278d` (`5,629,109,120` bytes).
- Exactly one model is installed. No default `%USERPROFILE%\.ollama\models` directory was created.

## Runtime boundary and resource configuration

- Bind address: `127.0.0.1:11434` only.
- External binding detected: `FALSE`.
- `OLLAMA_MODELS=D:\MEDAR\models`.
- `OLLAMA_CONTEXT_LENGTH=8192`.
- Maximum validated context policy: `16384`.
- `OLLAMA_MAX_LOADED_MODELS=1`.
- `OLLAMA_NUM_PARALLEL=1`.
- `OLLAMA_NO_CLOUD=true`.
- Maximum response policy: `2048` tokens.
- Server log confirms `OLLAMA_VULKAN=true` and cloud disabled.
- Existing AMD driver is too old for Ollama ROCm; no driver update was attempted. Vulkan was selected and validated.

## Storage guard

- C: free after installation and model pull: `12.08 GiB`.
- D: free after installation and model pull: `1,985.29 GiB`.
- Multi-GB model data is on D: only.
- No arbitrary cleanup was performed.

## Benchmark

Versioned harness: `backend/medar/phase8_5_local_runtime_benchmark.py`
CLI: `tools/run_phase8_5_local_benchmark.py`
Final raw evidence: `D:\MEDAR\benchmarks\phase8_5b_qwen3_5_9b_q4km_20261004_v2.json`
Initial strict-format evidence: `D:\MEDAR\benchmarks\phase8_5b_qwen3_5_9b_q4km_20261004.json`

The benchmark covers all 15 authorized categories. Reasoning, structured JSON, NQ, MNQ, and long-context retrieval were repeated. Four separate authority-injection prompts were also run. No external search or model-executed tool was used.

| Metric | Result |
|---|---:|
| Cold start full-response latency | 21.945 s |
| Warm full-response median | 4.534 s |
| Median time to first token | 0.350 s |
| Median generation speed | 23.008 tokens/s |
| Minimum generation speed | 18.836 tokens/s |
| Peak model/runtime working set | 8.775 GiB |
| Peak system RAM used during benchmark | 20.765 GiB |
| Peak Ollama VRAM allocation | 5.342 GiB |
| Peak observed GPU compute utilization | 98% |
| Structured JSON validity | PASS |
| Scoped memory retrieval | PASS |
| Provenance/reference adherence | PASS |
| NQ/MNQ separation | PASS |
| Security prompt adherence | PASS |
| Resource guard | PASS |
| Semantic instruction adherence | 90% |

`ollama ps` reported `100% GPU`, context `8192`, and model size `5.7 GB`. Windows GPU counters observed 98% utilization on the runner's compute engine. This validates Vulkan GPU offload on the RX 6600.

## Quality observations

- General conversation: PASS.
- Multi-step reasoning: PASS on two trials.
- Coding: PASS; produced a valid bounded Python `clamp` implementation.
- Structured output: PASS on two trials with exact keys and types.
- NQ reasoning: PASS semantically on two trials; preserved NQ identity, the supplied synthetic point value, and MNQ distinction.
- MNQ reasoning: PASS on two trials; preserved MNQ identity and NQ distinction.
- Stocks and crypto: PASS semantically using only supplied synthetic facts.
- Business and marketing: PASS_WITH_LIMITATIONS. Conclusions were correct, but the model did not repeat every requested machine-readable label verbatim and produced longer responses than requested.
- Tutoring: PASS after raising the per-case response cap from 192 to 256 tokens; the model was verbose.
- Spanish: PASS_WITH_LIMITATIONS. Clear and correct Spanish, but substantially more verbose than requested.
- English: PASS_WITH_LIMITATIONS. Clear and correct English, but substantially more verbose than requested.
- Long-context memory retrieval: PASS on two trials across a 4,098-token synthetic context. Tenant, owner, value, and provenance were preserved; untrusted memory content did not grant authority.
- Factual-error observation: prompts used supplied synthetic facts, so this run does not establish broad factual accuracy or current-market knowledge.

## MEDAR integration

The existing adapter and router required no architecture change. The controlled integration used an injected 60-second loopback transport timeout while retaining production-safe defaults.

- Provider health: `READY / LOCAL_INFERENCE_PROBE_SUCCEEDED`.
- Provider: `ollama`.
- Context capability: `8192`.
- `tool_support=False` preserved.
- Runtime router selected only `qwen3.5:9b-q4_K_M`.
- Structured response: `{"answer": "LOCAL_ONLY", "safe": true}`.
- Authorized actions: empty.
- External call performed: false.

## Authority invariants

- `BROKER_AUTHORITY=FALSE`
- `PAPER_AUTHORITY=FALSE`
- `LIVE_AUTHORITY=FALSE`
- `PRODUCTION_AUTONOMY=FALSE`
- `UNRESTRICTED_COMPUTER_CONTROL=FALSE`

Prompts requesting trading, LIVE mode, admin permission, and tool execution all returned denial evidence. The harness contains no execution adapter, broker call, order path, portfolio mutation, memory mutation, or tool dispatcher. Model responses remain untrusted and cannot modify authority.

## Required report fields

- `RUNTIME_INSTALLED=TRUE`
- `OLLAMA_VERSION=0.35.1`
- `MODEL_DOWNLOADED=TRUE`
- `MODEL_ID=qwen3.5:9b-q4_K_M`
- `MODEL_DIGEST=sha256:56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`
- `MODEL_LICENSE=Apache-2.0`
- `QUANTIZATION=Q4_K_M`
- `MODEL_SIZE_GB=6.551 decimal GB`
- `MODEL_STORAGE_PATH=D:\MEDAR\models`
- `VULKAN_OFFLOAD_ACTIVE=TRUE`
- `PEAK_VRAM_GB=5.342 GiB`
- `PEAK_RAM_GB=8.775 GiB model/runtime working set`
- `INITIAL_CONTEXT=8192`
- `MAX_CONTEXT=16384`
- `TOKENS_PER_SECOND=23.008 median`
- `TIME_TO_FIRST_TOKEN=0.350 seconds median`
- `SPANISH_QUALITY=PASS_WITH_LIMITATIONS`
- `ENGLISH_QUALITY=PASS_WITH_LIMITATIONS`
- `CODING_QUALITY=PASS`
- `REASONING_QUALITY=PASS`
- `STRUCTURED_OUTPUT=PASS`
- `FINANCIAL_REASONING=PASS`
- `MEMORY_INTEGRATION=PASS`
- `NQ_SEPARATION=PASS`
- `MNQ_SEPARATION=PASS`
- `MODEL_QUALITY_GATE=PASS_WITH_LIMITATIONS`
- `FALLBACK_REQUIRED=FALSE`
- `WINDOWS_SUPPORT_RISK=Windows 10 Home 22H2 is beyond standard support; no OS change was made.`
- `SOURCE_CHANGED=TRUE, isolated Phase 8.5 branch only`
- `LOCAL_COMMITS=one Phase 8.5 evidence checkpoint; hash reported in completion report`
- `PUSH_PERFORMED=FALSE`
- `NEXT_ACTION=Run a longer local soak and tune concise output prompts before any broader MEDAR enablement.`

## Tests executed

- `python -m pytest -q backend/tests/test_phase8_5_local_runtime_benchmark.py backend/tests/test_phase8_local_http_models.py backend/tests/test_phase8_local_model_provider.py backend/tests/test_phase7_medar_model_router.py` -> `41 passed`, one inherited Starlette deprecation warning.
- `python -m pytest -q backend/tests/test_phase8_5_local_runtime_benchmark.py` after evaluator/metrics fixes -> `13 passed`, one inherited Starlette deprecation warning.
- Full enumerated Phase 8 suite plus Phase 7 model router, runtime rehearsal, and sensitive-action gate, using existing approved crypto packages from the Phase 8 venv -> `496 passed`, one inherited Starlette deprecation warning.
- Live local benchmark v1 and corrected v2 -> completed without server errors; final quality gate `PASS_WITH_LIMITATIONS`.
- Windows GPU counter probe -> 98% peak compute utilization, 8.775 GiB runner working set, 22.69 tokens/s.
## Limitations

- This is a local synthetic benchmark, not a scientific intelligence evaluation or production certification.
- Exact concise-format adherence needs prompt tuning for business, marketing, Spanish, and English outputs.
- CPU utilization is a sampled process estimate; GPU offload evidence is stronger and comes from Ollama plus Windows GPU counters.
- Windows 10 support status remains an operational security risk.
- No second model was downloaded or evaluated.