"""Local synthetic benchmark harness; results are not intelligence claims."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from time import perf_counter
from typing import Callable

from backend.medar.deterministic_model import DeterministicModelProvider
from backend.medar.model_output_validation import validate_model_output
from backend.medar.model_performance import (
    ModelEvaluationEvent, ModelEvidenceOrigin, ModelFailureClass,
)
from backend.medar.model_profiles import CostClass, ModelLocality
from backend.medar.model_provider import ModelInvocation, ModelKind


class BenchmarkCategory(str, Enum):
    GENERAL = "GENERAL"
    CODING = "CODING"
    FINANCIAL = "FINANCIAL"
    PLANNING = "PLANNING"
    STRUCTURED_OUTPUT = "STRUCTURED_OUTPUT"


@dataclass(frozen=True)
class SyntheticBenchmarkCase:
    case_id: str
    category: BenchmarkCategory
    prompt: str
    model_kind: ModelKind
    schema: dict[str, str] | None = None


@dataclass(frozen=True)
class SyntheticBenchmarkResult:
    provider_id: str
    model_id: str
    events: tuple[ModelEvaluationEvent, ...]
    average_quality_score: float
    synthetic_only: bool = True
    external_calls_performed: bool = False
    human_intelligence_claimed: bool = False
    production_performance_claimed: bool = False

    def __post_init__(self) -> None:
        if (
            not self.synthetic_only or self.external_calls_performed
            or self.human_intelligence_claimed or self.production_performance_claimed
        ):
            raise ValueError("synthetic benchmark cannot claim external or production validity")


def default_synthetic_benchmark() -> tuple[SyntheticBenchmarkCase, ...]:
    return (
        SyntheticBenchmarkCase("general-1", BenchmarkCategory.GENERAL, "Synthetic general summary", ModelKind.LOCAL_LLM),
        SyntheticBenchmarkCase("coding-1", BenchmarkCategory.CODING, "Synthetic coding explanation", ModelKind.CODE_MODEL),
        SyntheticBenchmarkCase("financial-1", BenchmarkCategory.FINANCIAL, "Synthetic financial classification", ModelKind.REASONING_MODEL),
        SyntheticBenchmarkCase("planning-1", BenchmarkCategory.PLANNING, "Synthetic bounded plan", ModelKind.REASONING_MODEL),
        SyntheticBenchmarkCase(
            "structured-1", BenchmarkCategory.STRUCTURED_OUTPUT,
            "Return synthetic structured output", ModelKind.LOCAL_LLM,
            {"answer": "string", "score": "number", "valid": "boolean"},
        ),
    )


def run_local_synthetic_benchmark(
    provider: DeterministicModelProvider,
    *,
    tenant_id: str,
    owner_id: str,
    observed_at: datetime,
    timer: Callable[[], float] = perf_counter,
) -> SyntheticBenchmarkResult:
    if type(provider) is not DeterministicModelProvider:
        raise TypeError("exact deterministic local test provider is required")
    for name, value in (("tenant_id", tenant_id), ("owner_id", owner_id)):
        if not isinstance(value, str) or not value.strip() or len(value) > 240:
            raise ValueError(f"{name} must be bounded non-empty text")
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("benchmark observation time must be timezone-aware")
    events = []
    for case in default_synthetic_benchmark():
        invocation = ModelInvocation(
            f"benchmark-{case.case_id}", provider.descriptor.model_id,
            case.model_kind, case.prompt, case.schema,
        )
        started = timer()
        successful = False
        structured_valid = False
        quality = 0.0
        failure = ModelFailureClass.UNKNOWN
        try:
            result = provider.invoke(invocation)
        except TimeoutError:
            failure = ModelFailureClass.TIMEOUT
        except RuntimeError:
            failure = ModelFailureClass.PROVIDER_ERROR
        else:
            if result.external_call_performed:
                raise PermissionError("synthetic benchmark performed an external call")
            try:
                validated = validate_model_output(invocation, result)
            except ValueError:
                failure = ModelFailureClass.STRUCTURED_INVALID
            else:
                structured_valid = case.schema is None or validated.structured is not None
                successful = structured_valid
                quality = 1.0 if successful else 0.0
                failure = ModelFailureClass.NONE if successful else ModelFailureClass.STRUCTURED_INVALID
        elapsed_ms = max(0.0, (timer() - started) * 1000.0)
        events.append(ModelEvaluationEvent(
            f"benchmark-event-{case.case_id}", tenant_id, owner_id,
            provider.provider_id, provider.descriptor.model_id, case.category.value,
            successful, structured_valid, elapsed_ms, quality, failure,
            CostClass.FREE, ModelLocality.LOCAL,
            f"synthetic-test:benchmark:{case.case_id}",
            ModelEvidenceOrigin.SYNTHETIC_LOCAL, observed_at,
        ))
    average = sum(event.quality_score for event in events) / len(events)
    return SyntheticBenchmarkResult(
        provider.provider_id, provider.descriptor.model_id, tuple(events), average,
    )
