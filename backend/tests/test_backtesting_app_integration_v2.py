from fastapi.testclient import TestClient
import pytest

from backend.api.admin_authorization_dependency_v2 import ADMIN_TOKEN_HEADER

from backend.api.app import create_app


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setenv("ARMS_ADMIN_TOKEN", "backtesting-integration-test-admin")


class FakeBacktestingResult:

    def to_dict(self):

        return {
            "backtest": {
                "total_candles": 1,
            },
            "backtest_score": {
                "score": 90.0,
                "grade": "A",
            },
            "certification": {
                "status": "CERTIFIED",
            },
            "institutional_report": {
                "executive_summary": {
                    "status": "CERTIFIED",
                },
            },
        }


class FakeBacktestingOrchestrator:

    def __init__(self):

        self.candles_received = None
        self.output_directory_received = None

    def run(
        self,
        *,
        candles,
        output_directory,
    ):

        self.candles_received = candles
        self.output_directory_received = (
            output_directory
        )

        return FakeBacktestingResult()


def valid_payload():

    return {
        "candles": [
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "timestamp": (
                    "2026-08-04T09:30:00Z"
                ),
                "open": 21000.0,
                "high": 21010.0,
                "low": 20995.0,
                "close": 21005.0,
                "volume": 1000.0,
            },
        ],
        "output_directory": "reports/test",
    }


def test_backtesting_endpoint_is_registered():

    client = TestClient(
        create_app()
    )

    response = client.get(
        "/openapi.json"
    )

    assert response.status_code == 200

    assert (
        "/api/v2/backtesting/run"
        in response.json()["paths"]
    )


def test_app_backtest_uses_supplied_candles_without_local_csv(monkeypatch):
    from backend.backtesting.csv_candle_loader_v2 import CsvCandleLoaderV2
    from backend.tests.test_backtest_engine import build_candles

    def unexpected_csv_load(self):
        raise AssertionError("Application composition must not load a local CSV")

    monkeypatch.setattr(CsvCandleLoaderV2, "load", unexpected_csv_load)
    app = create_app()
    engine = app.state.backtesting_orchestrator_v2.backtest_engine
    session = engine.pipeline.pipeline.backtest_session_v2
    assert session.backtest_runner_v2.replay_engine_v2.total() == 0

    candles = build_candles(6)
    result = engine.run(candles=candles)

    assert result.total_candles == 6
    assert session.strategy_runner_v2.calls == 5
    assert session.candle_history[-1]["timestamp"] == candles[-2].timestamp
    assert result.trades == []


def test_default_orchestrator_is_configured():

    app = create_app()

    assert hasattr(
        app.state,
        "backtesting_orchestrator_v2",
    )

    assert (
        app.state.backtesting_orchestrator_v2
        is not None
    )

    client = TestClient(app)

    response = client.post(
        "/api/v2/backtesting/run",
        headers={ADMIN_TOKEN_HEADER: "backtesting-integration-test-admin"},
        json=valid_payload(),
    )

    assert response.status_code == 200


def test_accepts_injected_orchestrator():

    orchestrator = (
        FakeBacktestingOrchestrator()
    )

    app = create_app(
        backtesting_orchestrator_v2=(
            orchestrator
        ),
    )

    client = TestClient(app)

    response = client.post(
        "/api/v2/backtesting/run",
        headers={ADMIN_TOKEN_HEADER: "backtesting-integration-test-admin"},
        json=valid_payload(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["backtest"]["total_candles"]
        == 1
    )

    assert (
        payload["certification"]["status"]
        == "CERTIFIED"
    )

    assert len(
        orchestrator.candles_received
    ) == 1

    assert (
        orchestrator.output_directory_received
        == "reports/test"
    )


def test_rejects_invalid_orchestrator():

    try:
        create_app(
            backtesting_orchestrator_v2=object(),
        )
    except TypeError as exc:
        assert (
            "backtesting_orchestrator_v2"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )
