from fastapi.testclient import TestClient

from backend.api.app import create_app


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


def test_default_orchestrator_returns_503():

    client = TestClient(
        create_app()
    )

    response = client.post(
        "/api/v2/backtesting/run",
        json=valid_payload(),
    )

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "backtesting_orchestrator_not_configured"
    )


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
