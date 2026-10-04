"""Deterministic Phase 6 gate for future operator-controlled provisioning."""

from dataclasses import dataclass, fields, replace
from enum import Enum
from pathlib import Path

from backend.phase6.config_security import scan_phase6_configuration
from backend.phase6.failure_rehearsal import rehearse_provider_failure
from backend.phase6.iac_static_validation import validate_iac_tree
from backend.phase6.instrument_registry import get_instrument
from backend.phase6.least_privilege import validate_phase6_least_privilege
from backend.phase6.provider_emulator import LocalProviderEmulator, ProviderDependency
from backend.phase6.synthetic_market_data import SyntheticScenario, build_synthetic_fixture_catalog


class ProvisioningGateStatus(str, Enum):
    READY_FOR_OPERATOR_PROVISIONING = "READY_FOR_OPERATOR_PROVISIONING"
    HOLD = "HOLD"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ProvisioningEvidence:
    iac_validated: bool
    security_review_green: bool
    nq_mnq_semantics_green: bool
    cost_model_present: bool
    secret_strategy_present: bool
    identity_strategy_present: bool
    failure_rehearsal_green: bool
    prior_branches_unchanged: bool

    def __post_init__(self) -> None:
        if any(not isinstance(getattr(self, item.name), bool) for item in fields(self)):
            raise TypeError("provisioning evidence must contain explicit booleans")


@dataclass(frozen=True)
class ProvisioningGateResult:
    status: ProvisioningGateStatus
    missing_evidence: tuple[str, ...]
    reasons: tuple[str, ...]
    operator_action_required: bool = True
    provisioning_authorized: bool = False
    external_actions_performed: bool = False
    broker_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    production_deployment_authority: bool = False


_CRITICAL_EVIDENCE = (
    "iac_validated",
    "security_review_green",
    "nq_mnq_semantics_green",
    "secret_strategy_present",
    "identity_strategy_present",
    "failure_rehearsal_green",
    "prior_branches_unchanged",
)


def collect_local_provisioning_evidence(
    repo_root: Path,
    *,
    prior_branches_unchanged: bool,
) -> ProvisioningEvidence:
    """Collect reproducible local evidence without cloud credentials or calls."""

    root = Path(repo_root)
    iac = root / "infra" / "phase6" / "aws"
    deploy = root / "deploy" / "phase6" / "aws"
    docs = root / "docs" / "phase6"

    iac_report = validate_iac_tree(iac)
    security_report = scan_phase6_configuration(iac, deploy)
    privilege_report = validate_phase6_least_privilege(iac, deploy)
    threat_review = docs / "EXTERNAL_STAGING_THREAT_REVIEW_R76A.md"
    threat_green = threat_review.is_file() and (
        "THREAT_REVIEW_STATUS=PASS_WITH_OPERATOR_ACTIONS"
        in threat_review.read_text(encoding="utf-8")
    )

    nq = get_instrument("NQ")
    mnq = get_instrument("MNQ")
    fixtures = build_synthetic_fixture_catalog()
    semantics_green = (
        nq.tick_size == mnq.tick_size
        and nq.point_value == mnq.point_value * 10
        and set(fixtures) == {"NQ", "MNQ"}
        and all(set(fixtures[name]) == set(SyntheticScenario) for name in fixtures)
        and all(
            fixture.execution_authorized is False
            for scenarios in fixtures.values()
            for fixture in scenarios.values()
        )
    )

    failure_green = True
    for dependency in ProviderDependency:
        outcome = rehearse_provider_failure(LocalProviderEmulator(), dependency)
        failure_green = failure_green and not outcome.execution_authorized
        failure_green = failure_green and not outcome.external_side_effects_attempted

    cost_model = docs / "STAGING_COST_MODEL_R74C.md"
    cost_present = cost_model.is_file() and "COST_APPROVAL_REQUIRED=TRUE" in cost_model.read_text(encoding="utf-8")
    secret_text = (iac / "modules" / "secrets" / "main.tf").read_text(encoding="utf-8")
    secret_strategy = (
        "aws_secretsmanager_secret" in secret_text
        and "aws_secretsmanager_secret_version" not in secret_text
        and "GetSecretValue" in secret_text
    )
    identity_text = (iac / "modules" / "identity" / "main.tf").read_text(encoding="utf-8")
    identity_strategy = (
        "service_identities" in identity_text
        and "required_claims" in identity_text
        and "workload_policy_attachments" in identity_text
    )

    return ProvisioningEvidence(
        iac_validated=iac_report.passed,
        security_review_green=security_report.passed and privilege_report.passed and threat_green,
        nq_mnq_semantics_green=semantics_green,
        cost_model_present=cost_present,
        secret_strategy_present=secret_strategy,
        identity_strategy_present=identity_strategy,
        failure_rehearsal_green=failure_green,
        prior_branches_unchanged=prior_branches_unchanged,
    )


def evaluate_provisioning_gate(evidence: ProvisioningEvidence) -> ProvisioningGateResult:
    """Return READY, HOLD or BLOCKED without granting provisioning authority."""

    if not isinstance(evidence, ProvisioningEvidence):
        raise TypeError("evidence must be ProvisioningEvidence")
    missing = tuple(item.name for item in fields(evidence) if not getattr(evidence, item.name))
    critical_missing = tuple(name for name in missing if name in _CRITICAL_EVIDENCE)
    if critical_missing:
        return ProvisioningGateResult(
            ProvisioningGateStatus.BLOCKED,
            missing,
            tuple(f"CRITICAL_EVIDENCE_MISSING:{name}" for name in critical_missing),
        )
    if missing:
        return ProvisioningGateResult(
            ProvisioningGateStatus.HOLD,
            missing,
            tuple(f"PLANNING_EVIDENCE_MISSING:{name}" for name in missing),
        )
    return ProvisioningGateResult(
        ProvisioningGateStatus.READY_FOR_OPERATOR_PROVISIONING,
        (),
        (
            "LOCAL_PREPARATION_COMPLETE",
            "OPERATOR_APPROVAL_AND_EXTERNAL_ACTIONS_STILL_REQUIRED",
        ),
    )


def with_missing_evidence(evidence: ProvisioningEvidence, name: str) -> ProvisioningEvidence:
    """Test/helper function for deterministic missing-evidence evaluation."""

    if name not in {item.name for item in fields(evidence)}:
        raise ValueError("unknown provisioning evidence")
    return replace(evidence, **{name: False})
