"""Controlled operator client tests; no runtime, broker, or native process."""

from pathlib import Path

import pytest

import tools.request_current_paper_enable_v1 as operator


RUN_ID = "20261008T050000Z-oneclick-paper-test"
MARKET = dict(operator.phase1.REVIEWED_MARKET_IDENTITY)


def _install_valid_run(monkeypatch, tmp_path, *, state="RUNNING_DISABLED",
                       authority_overrides=None, market=None):
    run_directory = tmp_path / RUN_ID
    channel = tmp_path / "paper" / RUN_ID / "controller-command-v1"
    channel.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": RUN_ID,
        "targets": {"paper_run_namespace": str(channel.parent)},
    }
    validated = {
        "profile": {"market_identity": MARKET if market is None else market},
        "path_templates": {"command_channel": str(channel)},
    }
    phase2_state = {"state": state, **operator.ZERO_AUTHORITY}
    phase2_state.update(authority_overrides or {})
    monkeypatch.setattr(operator.phase1, "_load_and_verify",
        lambda directory, allow_runtime_targets: (
            Path(directory), manifest, {}, [], validated))
    monkeypatch.setattr(operator.phase1, "audit", lambda directory: (
        _ for _ in ()).throw(AssertionError('offline audit must not run')))
    monkeypatch.setattr(operator.phase1, "REVIEWED_MARKET_IDENTITY", MARKET)
    monkeypatch.setattr(
        operator.phase2, "validate_running_runtime",
        lambda directory, readiness_timeout: phase2_state)
    return run_directory, channel


def _accepted_response(**overrides):
    post = {
        "paper_enabled": True,
        "paper_ready": True,
        "readiness_blockers": [],
        "execution_mode": "SIMULATED / PAPER",
        "sim_execution_authority": "ENABLED",
        "live_execution_allowed": False,
        "external_order_authority": False,
        "broker_live_order_authority": False,
        "ninjatrader_control_authority": False,
        "thresholds_unchanged": True,
        "risk_unchanged": True,
    }
    post.update(overrides)
    return {
        "accepted": True,
        "reason": "PAPER_ENABLED",
        "post_enable_state": post,
    }


def test_controlled_enable_requires_explicit_operator_authorization(
        tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(operator, "request_enable", lambda **kwargs: called.append(kwargs))
    with pytest.raises(ValueError, match="EXPLICIT_OPERATOR_APPROVAL_REQUIRED"):
        operator.controlled_enable(run_directory=tmp_path, approved=False)
    assert called == []


def test_controlled_enable_uses_sealed_channel_once_from_running_disabled(
        tmp_path, monkeypatch):
    run_directory, channel = _install_valid_run(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(operator, "request_enable",
        lambda **kwargs: calls.append(kwargs) or _accepted_response())
    result = operator.controlled_enable(
        run_directory=run_directory, approved=True, timeout=4.0)
    assert len(calls) == 1
    assert calls[0]["directory"] == channel
    assert calls[0]["run_id"] == RUN_ID
    assert calls[0]["approved"] is True
    assert result == {
        "status": "PAPER_ENABLED",
        "run_id": RUN_ID,
        "pre_enable_state": "RUNNING_DISABLED",
        "paper_execution_enabled": True,
        "paper_ready": True,
        "execution_mode": "SIMULATED / PAPER",
        "live_execution_allowed": False,
        "external_order_authority": False,
        "broker_live_order_authority": False,
        "ninjatrader_control_authority": False,
    }


@pytest.mark.parametrize("state", ("PREPARED", "PAPER_ENABLED", "FAILED"))
def test_controlled_enable_rejects_any_state_other_than_running_disabled(
        tmp_path, monkeypatch, state):
    run_directory, _ = _install_valid_run(monkeypatch, tmp_path, state=state)
    called = []
    monkeypatch.setattr(operator, "request_enable", lambda **kwargs: called.append(kwargs))
    with pytest.raises(ValueError, match="RUNNING_DISABLED_REQUIRED"):
        operator.controlled_enable(run_directory=run_directory, approved=True)
    assert called == []


def test_controlled_enable_rejects_dead_or_revoked_runtime_health(
        tmp_path, monkeypatch):
    run_directory, _ = _install_valid_run(monkeypatch, tmp_path)
    monkeypatch.setattr(
        operator.phase2, 'validate_running_runtime',
        lambda *args, **kwargs: (_ for _ in ()).throw(
            operator.phase2.Phase2Blocked(
                'PAPER_RUNTIME_LIFECYCLE_UNHEALTHY')))
    called = []
    monkeypatch.setattr(
        operator, 'request_enable', lambda **kwargs: called.append(kwargs))
    with pytest.raises(
            operator.phase2.Phase2Blocked,
            match='PAPER_RUNTIME_LIFECYCLE_UNHEALTHY'):
        operator.controlled_enable(
            run_directory=run_directory, approved=True)
    assert called == []


@pytest.mark.parametrize("authority", tuple(operator.ZERO_AUTHORITY))
def test_controlled_enable_rejects_nonzero_precondition_authority(
        tmp_path, monkeypatch, authority):
    run_directory, _ = _install_valid_run(
        monkeypatch, tmp_path, authority_overrides={authority: True})
    called = []
    monkeypatch.setattr(operator, "request_enable", lambda **kwargs: called.append(kwargs))
    with pytest.raises(ValueError, match="ZERO_AUTHORITY_PRECONDITION_REQUIRED"):
        operator.controlled_enable(run_directory=run_directory, approved=True)
    assert called == []


def test_controlled_enable_rejects_market_or_channel_binding_drift(
        tmp_path, monkeypatch):
    run_directory, _ = _install_valid_run(
        monkeypatch, tmp_path, market={**MARKET, "contract": "MNQ DEC26"})
    with pytest.raises(ValueError, match="REVIEWED_NQ_MARKET_IDENTITY_REQUIRED"):
        operator.controlled_enable(run_directory=run_directory, approved=True)

    run_directory, _ = _install_valid_run(monkeypatch, tmp_path)
    monkeypatch.setattr(operator.phase1, "_absolute",
        lambda value, base: tmp_path / "different-channel")
    with pytest.raises(ValueError, match="COMMAND_CHANNEL_BINDING_MISMATCH"):
        operator.controlled_enable(run_directory=run_directory, approved=True)


@pytest.mark.parametrize("authority", (
    "live_execution_allowed", "external_order_authority",
    "broker_live_order_authority", "ninjatrader_control_authority",
))
def test_controlled_enable_rejects_unsafe_postcondition(
        tmp_path, monkeypatch, authority):
    run_directory, _ = _install_valid_run(monkeypatch, tmp_path)
    monkeypatch.setattr(operator, "request_enable",
        lambda **kwargs: _accepted_response(**{authority: True}))
    with pytest.raises(RuntimeError, match="PAPER_ENABLE_POSTCONDITION_FAILED"):
        operator.controlled_enable(run_directory=run_directory, approved=True)


def test_operator_client_has_no_live_broker_or_native_order_path():
    source = Path(operator.__file__).read_text(encoding="utf-8")
    for forbidden in ("ENABLE_LIVE", "SubmitOrder", "CreateOrder(",
                      "/orders", "broker.submit", "ninjatrader.control"):
        assert forbidden not in source

