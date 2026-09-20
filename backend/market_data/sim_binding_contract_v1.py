"""Offline SIM binding design. No account objects, discovery or execution API.

There is deliberately NO accepted native proof mechanism in this revision.
Synthetic proof tests exercise the future contract without enabling discovery.
Opaque references in these tests are fictional; future private references must
be installation-keyed HMACs, not unsalted hashes of account names.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json


@dataclass(frozen=True)
class PrivateBindingV1:
    account_ref: str
    connection_ref: str
    provider: str
    label_digest: str
    installation_ref: str
    proof_contract: str
    enabled: bool = False

    def digest(self):
        return sha256(json.dumps(asdict(self),sort_keys=True,separators=(",", ":")).encode()).hexdigest()


def assess_sim_binding(snapshot, binding, now, *, synthetic=False):
    """A scalar evidence contract, NOT an adapter. Native claims remain UNKNOWN."""
    result = dict(sim_discovery_status="NOT_IMPLEMENTED_AUTHORITY_UNPROVEN",
        sim_classification_status="UNKNOWN", sim_binding_status="INELIGIBLE",
        future_sim_eligible=False, sim_execution_authority="DISABLED", external_order_authority=False,
        evidence_kind="SYNTHETIC_OFFLINE" if synthetic is True else "UNPROVEN_NATIVE")
    if synthetic is not True or type(snapshot) is not dict or type(binding) is not PrivateBindingV1:
        return result
    result["sim_discovery_status"] = "SYNTHETIC_CONTRACT_ONLY"
    if snapshot.get("proof_contract") != "SYNTHETIC_PLATFORM_CLASS_V1":
        return result
    classification = snapshot.get("classification")
    if type(classification) is not str or classification not in {"PROVEN_SIMULATION","PROVEN_NON_SIMULATION"}:
        return result
    result["sim_classification_status"] = classification
    try:
        if type(now) is not datetime:
            return result
        observed = datetime.fromisoformat(snapshot["observed_at"])
        if now.tzinfo is None or observed.tzinfo is None or not timedelta(0) <= now-observed <= timedelta(seconds=15):
            return result
        if (type(snapshot.get("account_count")) is not int or snapshot["account_count"] != 1
                or binding.enabled is not True or snapshot.get("revoked") is not False
                or snapshot.get("configuration_sha256") != binding.digest()):
            return result
        for key in ("account_ref","connection_ref","provider","label_digest","installation_ref","proof_contract"):
            value = getattr(binding,key)
            if type(value) is not str or not value or value == "*" or snapshot.get(key) != value:
                return result
        if classification == "PROVEN_SIMULATION":
            result.update(sim_binding_status="SYNTHETIC_BINDING_MATCH", future_sim_eligible=True)
    except (KeyError, TypeError, ValueError, OverflowError):
        pass
    return result


class OfflineBindingLatchV1:
    """Changed configuration, stale evidence or mismatch revokes until new review."""
    def __init__(self, binding):
        self.binding = binding
        self.revoked = False

    def observe(self, snapshot, now):
        result = assess_sim_binding(snapshot,self.binding,now,synthetic=True)
        self.revoked |= not result["future_sim_eligible"]
        if self.revoked:
            result.update(future_sim_eligible=False,sim_binding_status="REVOKED_REVIEW_REQUIRED")
        return result
