"""V13 proof for the operator-maintained certified economic-news boundary."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config.api_settings import APISettings
from backend.services.certified_economic_news_runtime_refresh_service_v2 import (
    CertifiedEconomicNewsRuntimeRefreshServiceV2,
)
from backend.tests.runtime_market_fixture_v81 import publish_test_market
from backend.tests.test_account_runtime_transition_v2 import hosted
from backend.tests.test_phase1_consolidated_acceptance_v8 import submission
from backend.tests.test_runtime_admission_v81 import economic_state


def _news(path: Path, *, version="operator-v1", event=None, end="2026-09-08T16:00:00+00:00"):
    path.write_text(json.dumps({
        "snapshot_version": version,
        "generated_at": "2026-09-08T14:00:00+00:00",
        "coverage_start": "2026-09-08T14:00:00+00:00",
        "coverage_end": end,
        "high_impact_events": [] if event is None else [event],
    }), encoding="utf-8")
    return path


def _hours(path: Path):
    path.write_text(json.dumps({
        "covered_dates": ["2026-09-08"],
        "closed_dates": [],
        "special_hours": [],
    }), encoding="utf-8")
    return path


def _app(news_path=None, hours_path=None):
    return create_app(settings=APISettings(
        admin_token="admin-secret",
        certified_market_hours_path=None if hours_path is None else str(hours_path),
        certified_economic_news_path=None if news_path is None else str(news_path),
    ))


def test_missing_news_is_fail_closed_and_exposes_empty_lifecycle():
    app = _app()
    lifecycle = app.state.economic_news_data_lifecycle_v2
    assert lifecycle.get_status() == lifecycle.STATUS_EMPTY
    assert app.state.economic_news_runtime_provider_v2.is_timestamp_covered(
        timestamp=datetime.now(timezone.utc)
    ) is False
    assert app.state.economic_news_authority_v2.is_news_blocked(
        symbol="MNQ", timestamp=datetime.now(timezone.utc)
    ) is True


def test_operator_refresh_publishes_version_provenance_and_coverage(tmp_path):
    path = _news(tmp_path / "news-v1.json", version="operator-v1")
    app = _app()
    service = app.state.economic_news_runtime_refresh_service_v2
    assert isinstance(service, CertifiedEconomicNewsRuntimeRefreshServiceV2)

    report = service.refresh_from_file(file_path=path)

    assert report["runtime_published"] is True
    assert report["snapshot_version"] == "operator-v1"
    assert app.state.economic_news_data_lifecycle_v2.get_active_path() == path
    assert app.state.economic_news_runtime_provider_v2.snapshot.snapshot_version == "operator-v1"
    assert app.state.economic_news_authority_v2 is (
        app.state.economic_news_runtime_provider_v2.get_economic_news_authority()
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v2/economic-news/coverage",
            params={"timestamp": "2026-09-08T15:00:00+00:00"},
        )
        assert response.status_code == 200
        assert response.json()["covered"] is True
        status = client.get("/api/v2/economic-news/status")
        assert status.json()["last_activation_report"]["snapshot_version"] == "operator-v1"


def test_invalid_replacement_preserves_last_valid_news_state(tmp_path):
    valid = _news(tmp_path / "valid.json", version="operator-valid")
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{not-json", encoding="utf-8")
    app = _app()
    service = app.state.economic_news_runtime_refresh_service_v2
    service.refresh_from_file(file_path=valid)
    previous_provider = app.state.economic_news_runtime_provider_v2

    with pytest.raises(ValueError):
        service.refresh_from_file(file_path=invalid)

    assert app.state.economic_news_runtime_provider_v2 is previous_provider
    assert app.state.economic_news_data_lifecycle_v2.get_status() == "READY"
    assert app.state.economic_news_data_lifecycle_v2.get_active_path() == valid


def test_protected_operator_refresh_rejects_missing_auth_and_accepts_authorized(tmp_path):
    path = _news(tmp_path / "news.json")
    app = _app()
    with TestClient(app) as client:
        missing = client.post("/api/v2/economic-news/refresh", json={"file_path": str(path)})
        assert missing.status_code == 401
        authorized = client.post(
            "/api/v2/economic-news/refresh",
            json={"file_path": str(path)},
            headers={"X-ARMS-ADMIN-TOKEN": "admin-secret"},
        )
        assert authorized.status_code == 200, authorized.text
        assert authorized.json()["snapshot_version"] == "operator-v1"


def test_news_block_rejects_before_fill_and_financial_mutation(hosted, tmp_path):
    runtime = hosted.c.published.runtime
    before = economic_state(runtime)
    publish_test_market(
        runtime.trade_lifecycle_service,
        directory=tmp_path,
        news_blocked=True,
    )

    response = hosted.client.post("/v2/trades/submit", json=submission(hosted))

    assert response.status_code == 200
    assert response.json()["accepted"] is False
    assert runtime.trade_lifecycle_service.broker_connector_v2.get_fills() == []
    assert runtime.trade_lifecycle_service.get_active_positions() == []
    assert runtime.trade_lifecycle_service.trade_journal_v2.get_trades() == []
    assert economic_state(runtime) == before
