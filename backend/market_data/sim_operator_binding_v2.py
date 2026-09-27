"""Operator-bound native SIM identity contract.

This module is intentionally pure:
- no NinjaTrader account objects
- no file or environment access
- no broker/order operations
- no execution authority

A valid binding may establish future SIM eligibility only.
External order authority remains disabled in this revision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import re


_HEX64 = re.compile(r"[0-9a-f]{64}")
_MAX_EVIDENCE_AGE = timedelta(seconds=15)


def derive_private_ref(
    secret: bytes,
    *,
    domain: str,
    value: str,
) -> str:
    """Derive an installation-keyed, domain-separated opaque reference."""
    if type(secret) is not bytes or not secret:
        raise ValueError("secret must be non-empty bytes")

    if type(domain) is not str or not domain.strip():
        raise ValueError("domain must be a non-empty string")

    if type(value) is not str or not value:
        raise ValueError("value must be a non-empty string")

    payload = (
        "arms.sim.operator-binding.v2"
        + "\0"
        + domain.strip()
        + "\0"
        + value
    ).encode("utf-8")

    return hmac.new(
        secret,
        payload,
        hashlib.sha256,
    ).hexdigest()


@dataclass(frozen=True)
class OperatorSimBindingV2:
    installation_ref: str
    account_ref: str
    connection_ref: str
    label_ref: str
    provider: str
    connection_mode: str
    enabled: bool
    operator_approved: bool


def _valid_ref(value: object) -> bool:
    return (
        type(value) is str
        and _HEX64.fullmatch(value) is not None
    )


def _base_result() -> dict[str, object]:
    return {
        "sim_discovery_status": "OPERATOR_BOUND_NATIVE",
        "sim_classification_status": "UNKNOWN",
        "sim_binding_status": "INELIGIBLE",
        "sim_runtime_revalidation": "NOT_PERFORMED",
        "future_sim_eligible": False,
        "sim_execution_authority": "DISABLED",
        "external_order_authority": False,
        "evidence_kind": "NATIVE_OPERATOR_BOUND",
    }


def assess_operator_sim_binding(
    snapshot: object,
    binding: object,
    now: object,
) -> dict[str, object]:
    """Assess scalar native-SIM evidence without granting order authority."""
    result = _base_result()

    if type(snapshot) is not dict:
        return result

    if type(binding) is not OperatorSimBindingV2:
        return result

    if type(now) is not datetime or now.tzinfo is None:
        return result

    # Reject handles, nested objects and callable surfaces.
    if any(
        type(key) is not str
        or type(value) not in (str, bool, int)
        for key, value in snapshot.items()
    ):
        return result

    refs = (
        binding.installation_ref,
        binding.account_ref,
        binding.connection_ref,
        binding.label_ref,
    )

    if not all(_valid_ref(value) for value in refs):
        return result

    if (
        type(binding.provider) is not str
        or binding.provider != "Simulator"
        or type(binding.connection_mode) is not str
        or binding.connection_mode not in {"Live", "Simulation"}
        or binding.enabled is not True
        or binding.operator_approved is not True
    ):
        return result

    try:
        observed = datetime.fromisoformat(
            snapshot["observed_at"]
        )
    except (KeyError, TypeError, ValueError):
        return result

    if observed.tzinfo is None:
        return result

    age = now - observed

    if not timedelta(0) <= age <= _MAX_EVIDENCE_AGE:
        return result

    if (
        type(snapshot.get("account_count")) is not int
        or snapshot["account_count"] != 1
        or snapshot.get("connected") is not True
        or snapshot.get("revoked") is not False
        or snapshot.get("provider") != binding.provider
        or snapshot.get("connection_mode")
            != binding.connection_mode
    ):
        return result

    for key in (
        "installation_ref",
        "account_ref",
        "connection_ref",
        "label_ref",
    ):
        observed_ref = snapshot.get(key)
        expected_ref = getattr(binding, key)

        if (
            not _valid_ref(observed_ref)
            or not hmac.compare_digest(
                observed_ref,
                expected_ref,
            )
        ):
            return result

    runtime_ref = snapshot.get("runtime_ref")
    connection_epoch = snapshot.get("connection_epoch")

    if (
        type(runtime_ref) is not str
        or not runtime_ref
        or type(connection_epoch) is not str
        or not connection_epoch
    ):
        return result

    result.update(
        sim_classification_status="PROVEN_SIMULATION",
        sim_binding_status="BOUND",
        future_sim_eligible=True,
    )

    return result


class OperatorSimBindingLatchV2:
    """Runtime/connection-epoch latch; any mismatch revokes permanently."""

    def __init__(
        self,
        binding: OperatorSimBindingV2,
        *,
        runtime_ref: str,
        connection_epoch: str,
    ) -> None:
        self.binding = binding
        self.runtime_ref = runtime_ref
        self.connection_epoch = connection_epoch

        self.revoked = (
            type(binding) is not OperatorSimBindingV2
            or type(runtime_ref) is not str
            or not runtime_ref
            or type(connection_epoch) is not str
            or not connection_epoch
        )

        self.last_sequence = -1
        self.last_observed: datetime | None = None

    def revoke(self) -> None:
        self.revoked = True

    def observe(
        self,
        snapshot: object,
        now: object,
    ) -> dict[str, object]:
        result = assess_operator_sim_binding(
            snapshot,
            self.binding,
            now,
        )

        valid = (
            result["future_sim_eligible"] is True
            and not self.revoked
            and type(snapshot) is dict
        )

        observed = None

        if valid:
            try:
                observed = datetime.fromisoformat(
                    snapshot["observed_at"]
                )
            except (KeyError, TypeError, ValueError):
                valid = False

        if valid:
            sequence = snapshot.get(
                "discovery_sequence"
            )

            valid = (
                snapshot.get("runtime_ref")
                == self.runtime_ref
                and snapshot.get("connection_epoch")
                == self.connection_epoch
                and type(sequence) is int
                and sequence == self.last_sequence + 1
                and (
                    self.last_observed is None
                    or observed >= self.last_observed
                )
            )

        if valid:
            self.last_sequence = snapshot[
                "discovery_sequence"
            ]
            self.last_observed = observed
        else:
            self.revoked = True

        if self.revoked:
            result.update(
                sim_binding_status=(
                    "REVOKED_REVIEW_REQUIRED"
                ),
                sim_runtime_revalidation="REVOKED",
                future_sim_eligible=False,
                sim_execution_authority="DISABLED",
                external_order_authority=False,
            )
        else:
            result.update(
                sim_runtime_revalidation="PASS",
                future_sim_eligible=True,
                sim_execution_authority="DISABLED",
                external_order_authority=False,
            )

        return result
