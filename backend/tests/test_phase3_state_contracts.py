"""R32A regression tests for immutable durable state contracts."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

import pytest

from backend.phase3 import (
    AccountIdentity,
    DecimalUnit,
    DurableDecimal,
    DurableStateKind,
    DurableStatePayload,
    DurableStateRecord,
    PropFirmProfileIdentity,
    SchemaIdentity,
    SourceIdentity,
    TenantIdentity,
    UserIdentity,
)


NOW = datetime(2026, 10, 3, 14, 30, tzinfo=timezone.utc)
TENANT = TenantIdentity("tenant-a")
USER = UserIdentity("tenant-a", "user-1")
ACCOUNT = AccountIdentity("tenant-a", "account-1")
PROFILE = PropFirmProfileIdentity(
    firm_id="lucid",
    program_id="lucidpro_funded_no_dll",
    stage="funded",
    account_size=DurableDecimal(D("50000.00"), DecimalUnit.CURRENCY, "USD"),
    profile_version="2026-10-03",
    config_hash="a" * 64,
)
SOURCE = SourceIdentity("runtime://paper/account-1", "snapshot-v1", True)
PAYLOAD = DurableStatePayload((
    ("balance", DurableDecimal(D("52341.0700"), DecimalUnit.CURRENCY, "USD")),
    ("blocking_reasons", ("daily_loss_near_limit",)),
    ("contracts_open", 2),
    ("risk_complete", True),
))


def record(kind=DurableStateKind.ACCOUNT_SNAPSHOT, **changes):
    schema_name = (
        kind.value
        if isinstance(kind, DurableStateKind)
        else DurableStateKind.ACCOUNT_SNAPSHOT.value
    )
    values = dict(
        record_id="snapshot-1",
        schema=SchemaIdentity("arms.phase3", schema_name, 1),
        kind=kind,
        observed_at=NOW,
        tenant=TENANT,
        source=SOURCE,
        payload=PAYLOAD,
        account=ACCOUNT,
        profile=PROFILE,
    )
    values.update(changes)
    return DurableStateRecord(**values)


def test_account_snapshot_contract_preserves_exact_values_and_provenance():
    state = record()
    balance = state.payload.get("balance")
    assert isinstance(balance, DurableDecimal)
    assert balance.value.as_tuple() == D("52341.0700").as_tuple()
    assert balance.currency == "USD"
    assert state.schema.qualified_name == "arms.phase3.account_snapshot.v1"
    assert state.source.simulated is True


def test_contracts_are_immutable_and_carry_no_execution_authority():
    state = record()
    assert state.execution_authorized is False
    assert state.production_mutation_authorized is False
    assert state.canonical_admin_authorized is False
    with pytest.raises(FrozenInstanceError):
        state.record_id = "changed"
    with pytest.raises(FrozenInstanceError):
        state.payload.entries = ()


@pytest.mark.parametrize(
    ("kind", "scope"),
    [
        (DurableStateKind.TENANT, {}),
        (DurableStateKind.USER, {"user": USER}),
        (DurableStateKind.ACCOUNT, {"account": ACCOUNT}),
        (DurableStateKind.PROP_FIRM_PROFILE, {"profile": PROFILE}),
        (DurableStateKind.ACCOUNT_SNAPSHOT, {"account": ACCOUNT, "profile": PROFILE}),
        (DurableStateKind.EVALUATION_RESULT, {"account": ACCOUNT, "profile": PROFILE}),
        (DurableStateKind.PORTFOLIO_SUMMARY, {}),
        (DurableStateKind.JOURNAL_ANALYTICS_SNAPSHOT, {}),
        (DurableStateKind.NOTIFICATION_EVENT, {"user": USER, "account": ACCOUNT}),
        (DurableStateKind.MEMBERSHIP_ENTITLEMENT_STATE, {"user": USER}),
    ],
)
def test_all_required_phase3_state_kinds_have_valid_scopes(kind, scope):
    requested_scope = {"account": None, "profile": None}
    requested_scope.update(scope)
    state = record(kind, **requested_scope)
    assert state.kind is kind
    assert state.tenant == TENANT


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        (DurableStateKind.USER, "require user"),
        (DurableStateKind.MEMBERSHIP_ENTITLEMENT_STATE, "require user"),
        (DurableStateKind.ACCOUNT, "require account"),
        (DurableStateKind.ACCOUNT_SNAPSHOT, "require account"),
        (DurableStateKind.PROP_FIRM_PROFILE, "require profile"),
        (DurableStateKind.EVALUATION_RESULT, "require account"),
    ],
)
def test_required_scope_is_fail_closed(kind, message):
    with pytest.raises(ValueError, match=message):
        record(kind, account=None, profile=None, user=None)


def test_cross_tenant_identity_is_rejected():
    with pytest.raises(ValueError, match="account tenant"):
        record(account=AccountIdentity("tenant-b", "account-1"))
    with pytest.raises(ValueError, match="user tenant"):
        record(DurableStateKind.USER, account=None, profile=None,
               user=UserIdentity("tenant-b", "user-1"))


def test_tenant_state_cannot_claim_narrower_identity():
    with pytest.raises(ValueError, match="narrower identities"):
        record(DurableStateKind.TENANT, account=None, profile=None, user=USER)


@pytest.mark.parametrize("value", [1.25, D("NaN"), D("Infinity"), "1.25", 125])
def test_durable_decimal_rejects_inexact_or_non_decimal_values(value):
    with pytest.raises(ValueError, match="finite Decimal"):
        DurableDecimal(value, DecimalUnit.RATIO)


def test_currency_and_units_are_explicit_and_consistent():
    amount = DurableDecimal(D("1.2300"), DecimalUnit.CURRENCY, "USD")
    assert amount.value.as_tuple() == D("1.2300").as_tuple()
    with pytest.raises(ValueError, match="require"):
        DurableDecimal(D("1"), DecimalUnit.CURRENCY)
    with pytest.raises(ValueError, match="only valid"):
        DurableDecimal(D("1"), DecimalUnit.POINTS, "USD")


def test_payload_accepts_aware_timestamps_and_rejects_naive_timestamps():
    payload = DurableStatePayload((("session_ends_at", NOW),))
    assert payload.get("session_ends_at") is NOW
    with pytest.raises(ValueError, match="timezone-aware"):
        DurableStatePayload((("session_ends_at", datetime(2026, 10, 3)),))


@pytest.mark.parametrize(
    "entries",
    [
        [("balance", 1)],
        (("balance", 1.0),),
        (("balance", {"nested": "mapping"}),),
        (("balance", [1, 2]),),
        (("z_field", 1), ("a_field", 2)),
        (("field", 1), ("field", 2)),
        (("api_token", "value"),),
    ],
)
def test_payload_rejects_mutability_inexact_numbers_and_unsafe_shape(entries):
    with pytest.raises(ValueError):
        DurableStatePayload(entries)


@pytest.mark.parametrize(
    "changes",
    [
        {"record_id": ""},
        {"schema": SchemaIdentity("arms.phase3", "snapshot", 1), "kind": "account_snapshot"},
        {"observed_at": datetime(2026, 10, 3, 14, 30)},
        {"source": "runtime"},
        {"payload": (("balance", 1),)},
    ],
)
def test_invalid_record_identity_or_type_is_rejected(changes):
    with pytest.raises(ValueError):
        record(**changes)


def test_schema_name_must_match_state_kind():
    with pytest.raises(ValueError, match="schema name"):
        record(schema=SchemaIdentity("arms.phase3", "evaluation_result", 1))


@pytest.mark.parametrize(
    "factory",
    [
        lambda: SchemaIdentity("Arms", "snapshot", 1),
        lambda: SchemaIdentity("arms", "snapshot", 0),
        lambda: TenantIdentity(""),
        lambda: SourceIdentity("runtime", "v1", 1),
        lambda: PropFirmProfileIdentity(
            "lucid", "program", "funded",
            DurableDecimal(D("0"), DecimalUnit.CURRENCY, "USD"),
            "v1", "a" * 64,
        ),
        lambda: PropFirmProfileIdentity(
            "lucid", "program", "funded",
            DurableDecimal(D("50000"), DecimalUnit.CURRENCY, "USD"),
            "v1", "not-a-hash",
        ),
    ],
)
def test_invalid_schema_identity_provenance_or_profile_is_rejected(factory):
    with pytest.raises(ValueError):
        factory()


def test_contract_module_has_no_io_database_or_execution_dependency():
    from backend.phase3 import state_contracts

    source = Path(state_contracts.__file__).read_text(encoding="utf-8")
    forbidden = ("sqlite3", "sqlalchemy", "backend.execution", "requests", "subprocess")
    assert all(token not in source for token in forbidden)
