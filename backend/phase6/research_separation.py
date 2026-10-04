"""Instrument-scoped Phase 6 research records and explicitly labeled reports."""

from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from backend.phase6.instrument_registry import get_instrument


class ResearchSeparationError(ValueError):
    """Raised before records from different instruments can be mixed silently."""


def _nonempty(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchSeparationError(f"{name} must be nonempty text")
    return value.strip()


@dataclass(frozen=True)
class ResearchRunIdentity:
    run_id: str
    instrument: str
    contract_id: str
    dataset_id: str

    def __post_init__(self) -> None:
        instrument = get_instrument(self.instrument).root_symbol
        run_id = _nonempty(self.run_id, "run_id")
        contract_id = _nonempty(self.contract_id, "contract_id")
        dataset_id = _nonempty(self.dataset_id, "dataset_id")
        if not contract_id.startswith(f"{instrument}-"):
            raise ResearchSeparationError("contract identity does not match instrument")
        object.__setattr__(self, "instrument", instrument)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "contract_id", contract_id)
        object.__setattr__(self, "dataset_id", dataset_id)

    @property
    def storage_key(self) -> str:
        return f"research/{self.instrument}/{self.dataset_id}/{self.run_id}.json"


@dataclass(frozen=True)
class InstrumentResearchResult:
    identity: ResearchRunIdentity
    metrics: Mapping[str, Decimal]
    synthetic_data: bool = True
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if not self.synthetic_data:
            raise ResearchSeparationError("Phase 6 staging research must be synthetic")
        if self.execution_authorized:
            raise ResearchSeparationError("research cannot authorize execution")
        normalized: dict[str, Decimal] = {}
        for name, value in self.metrics.items():
            metric_name = _nonempty(name, "metric name")
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ResearchSeparationError("metrics must contain finite Decimal values")
            normalized[metric_name] = value
        if not normalized:
            raise ResearchSeparationError("metrics must not be empty")
        object.__setattr__(self, "metrics", MappingProxyType(normalized))


@dataclass(frozen=True)
class InstrumentResearchReport:
    instrument: str
    label: str
    results: tuple[InstrumentResearchResult, ...]
    aggregated: bool = False
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        instrument = get_instrument(self.instrument).root_symbol
        if self.aggregated:
            raise ResearchSeparationError("single-instrument report cannot be aggregated")
        if not self.results:
            raise ResearchSeparationError("instrument report requires results")
        if any(result.identity.instrument != instrument for result in self.results):
            raise ResearchSeparationError("instrument report contains mixed results")
        expected_label = f"{instrument}_ONLY"
        if self.label != expected_label:
            raise ResearchSeparationError(f"instrument report label must be {expected_label}")
        if self.execution_authorized:
            raise ResearchSeparationError("research report cannot authorize execution")
        object.__setattr__(self, "instrument", instrument)


@dataclass(frozen=True)
class LabeledAggregateReport:
    label: str
    reports: tuple[InstrumentResearchReport, ...]
    methodology: str
    instruments: tuple[str, ...] = field(init=False)
    combined_performance: None = field(default=None, init=False)
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if len(self.reports) < 2:
            raise ResearchSeparationError("aggregate report requires multiple instrument reports")
        instruments = tuple(sorted(report.instrument for report in self.reports))
        if len(set(instruments)) != len(instruments):
            raise ResearchSeparationError("aggregate report cannot repeat instrument scope")
        expected_label = f"AGGREGATED[{'+'.join(instruments)}]"
        if self.label != expected_label:
            raise ResearchSeparationError(f"aggregate report label must be {expected_label}")
        _nonempty(self.methodology, "methodology")
        if self.execution_authorized:
            raise ResearchSeparationError("aggregate report cannot authorize execution")
        object.__setattr__(self, "instruments", instruments)


def build_instrument_report(
    instrument: str,
    results: tuple[InstrumentResearchResult, ...],
) -> InstrumentResearchReport:
    canonical = get_instrument(instrument).root_symbol
    return InstrumentResearchReport(
        instrument=canonical,
        label=f"{canonical}_ONLY",
        results=results,
    )


def build_labeled_aggregate(
    reports: tuple[InstrumentResearchReport, ...],
    *,
    label: str,
    methodology: str,
) -> LabeledAggregateReport:
    return LabeledAggregateReport(
        label=label,
        reports=reports,
        methodology=methodology,
    )
