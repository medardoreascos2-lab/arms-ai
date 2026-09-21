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
import re


def native_sim_status():
    """Fixed public projection; never initializes discovery or accepts proof claims."""
    return dict(sim_discovery_status="NOT_IMPLEMENTED_AUTHORITY_UNPROVEN",
        sim_classification_status="UNKNOWN", sim_binding_status="NOT_CONFIGURED",
        sim_runtime_revalidation="NOT_PERFORMED", future_sim_eligible=False,
        sim_execution_authority="DISABLED", external_order_authority=False)


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


def validate_private_binding(document):
    """Validate an inert, single-account draft, not authority. No file/account access.

    Caller owns private storage/ACLs. References must be keyed HMACs supplied by
    a future reviewed collector; syntactic validation cannot attest their origin.
    """
    fields = set(PrivateBindingV1.__dataclass_fields__)
    if type(document) is not dict:
        return None
    if any(type(k) is not str or (type(v) is not bool if k == "enabled" else type(v) is not str)
           for k, v in document.items()):
        return None
    if set(document) != fields | {"schema", "configuration_sha256"}:
        return None
    if (document["schema"] != "arms.private-sim-binding.v1" or document["enabled"] is not False
            or document["proof_contract"] != "UNRESOLVED_NATIVE_PROOF"
            or not re.fullmatch(r"(?:Provider[0-9]+|Simulator|Playback)", document["provider"])):
        return None
    for key in ("account_ref", "connection_ref", "label_digest", "installation_ref", "configuration_sha256"):
        if type(document[key]) is not str or not re.fullmatch(r"[a-f0-9]{64}", document[key]):
            return None
    binding = PrivateBindingV1(**{key: document[key] for key in fields})
    return binding if document["configuration_sha256"] == binding.digest() else None


def assess_sim_binding(snapshot, binding, now, *, synthetic=False):
    """A scalar evidence contract, NOT an adapter. Native claims remain UNKNOWN."""
    result = dict(sim_discovery_status="NOT_IMPLEMENTED_AUTHORITY_UNPROVEN",
        sim_classification_status="UNKNOWN", sim_binding_status="INELIGIBLE",
        future_sim_eligible=False, sim_execution_authority="DISABLED", external_order_authority=False,
        sim_runtime_revalidation="NOT_PERFORMED",
        evidence_kind="SYNTHETIC_OFFLINE" if synthetic is True else "UNPROVEN_NATIVE")
    if synthetic is not True or type(snapshot) is not dict or type(binding) is not PrivateBindingV1:
        return result
    # Reject nested handles/callables without invoking their attributes or hooks.
    if any(type(k) is not str or type(v) not in (str, bool, int) for k, v in snapshot.items()):
        return result
    if any(type(getattr(binding, key)) is not str for key in (
            "account_ref", "connection_ref", "provider", "label_digest", "installation_ref", "proof_contract")):
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
            result.update(sim_binding_status="SYNTHETIC_BINDING_MATCH")
    except (KeyError, TypeError, ValueError, OverflowError):
        pass
    return result


class OfflineBindingLatchV1:
    """Synthetic lifecycle model only. Never persisted or used for native admission.

    Each explicitly reviewed process/connection epoch starts a fresh latch.
    Restart/reconnect evidence cannot reuse a previous epoch or auto-rebind.
    """
    def __init__(self, binding, *, runtime_ref, connection_epoch):
        self.binding = binding
        self.runtime_ref = runtime_ref
        self.connection_epoch = connection_epoch
        self.revoked = any(type(v) is not str or not v or "*" in v for v in (runtime_ref, connection_epoch))
        self.last_sequence = -1
        self.last_observed = None

    def revoke(self):
        self.revoked = True

    def observe(self, snapshot, now):
        result = assess_sim_binding(snapshot,self.binding,now,synthetic=True)
        valid = result["sim_binding_status"] == "SYNTHETIC_BINDING_MATCH"
        if valid and not self.revoked:
            sequence = snapshot.get("discovery_sequence")
            observed = datetime.fromisoformat(snapshot["observed_at"])
            valid = (snapshot.get("runtime_ref") == self.runtime_ref
                and snapshot.get("connection_epoch") == self.connection_epoch
                and snapshot.get("connected") is True
                and type(sequence) is int and sequence == self.last_sequence + 1
                and (self.last_observed is None or observed >= self.last_observed))
            if valid:
                self.last_sequence, self.last_observed = sequence, observed
        self.revoked |= not valid
        if self.revoked:
            result.update(sim_binding_status="REVOKED_REVIEW_REQUIRED", sim_runtime_revalidation="REVOKED")
        else:
            result.update(future_sim_eligible=True, sim_runtime_revalidation="SYNTHETIC_PASS")
        return result
