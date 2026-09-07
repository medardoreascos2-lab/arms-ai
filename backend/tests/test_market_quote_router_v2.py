from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config.api_settings import APISettings


TOKEN = "gap-2k-quote-test-token"


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv(
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS",
        "5.0",
    )

    settings = APISettings(
        webhook_token=TOKEN,
    )

    return TestClient(
        create_app(
            settings=settings,
        )
    )


def _headers() -> dict[str, str]:
    return {
        "X-ARMS-TOKEN": TOKEN,
    }


def _payload(
    *,
    bid: float = 21690.75,
    ask: float = 21691.00,
    timestamp: datetime | None = None,
) -> dict[str, object]:
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    return {
        "symbol": "NQ",
        "bid": bid,
        "ask": ask,
        "timestamp": timestamp.isoformat(),
    }


def test_market_quote_accepts_valid_l1_quote(
    monkeypatch,
) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/market/quote",
        json=_payload(),
        headers=_headers(),
    )

    assert response.status_code == 201

    body = response.json()

    assert body["status"] == "stored"
    assert body["symbol"] == "NQ"
    assert body["bid"] == 21690.75
    assert body["ask"] == 21691.00

    quote = (
        client.app.state.runtime_quote_authority_v2
        .get_quote(symbol="NQ")
    )

    assert quote is not None
    assert quote["bid"] == 21690.75
    assert quote["ask"] == 21691.00


def test_market_quote_requires_authentication(
    monkeypatch,
) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/market/quote",
        json=_payload(),
    )

    assert response.status_code == 401

    quote = (
        client.app.state.runtime_quote_authority_v2
        .get_quote(symbol="NQ")
    )

    assert quote is None


def test_market_quote_rejects_wrong_token(
    monkeypatch,
) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/market/quote",
        json=_payload(),
        headers={
            "X-ARMS-TOKEN": "wrong-token",
        },
    )

    assert response.status_code == 401

    quote = (
        client.app.state.runtime_quote_authority_v2
        .get_quote(symbol="NQ")
    )

    assert quote is None


def test_market_quote_crossed_quote_is_controlled_4xx(
    monkeypatch,
) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/market/quote",
        json=_payload(
            bid=21691.00,
            ask=21690.75,
        ),
        headers=_headers(),
    )

    assert 400 <= response.status_code < 500

    quote = (
        client.app.state.runtime_quote_authority_v2
        .get_quote(symbol="NQ")
    )

    assert quote is None


def test_market_quote_naive_timestamp_is_controlled_4xx(
    monkeypatch,
) -> None:
    client = _client(monkeypatch)

    naive_timestamp = (
        datetime.now(timezone.utc)
        .replace(tzinfo=None)
    )

    response = client.post(
        "/market/quote",
        json=_payload(
            timestamp=naive_timestamp,
        ),
        headers=_headers(),
    )

    assert 400 <= response.status_code < 500

    quote = (
        client.app.state.runtime_quote_authority_v2
        .get_quote(symbol="NQ")
    )

    assert quote is None


def test_market_quote_older_quote_is_controlled_4xx_and_preserves_newer(
    monkeypatch,
) -> None:
    client = _client(monkeypatch)

    newer_timestamp = datetime.now(timezone.utc)

    first = client.post(
        "/market/quote",
        json=_payload(
            bid=21690.75,
            ask=21691.00,
            timestamp=newer_timestamp,
        ),
        headers=_headers(),
    )

    assert first.status_code == 201

    older = client.post(
        "/market/quote",
        json=_payload(
            bid=21000.00,
            ask=21000.25,
            timestamp=(
                newer_timestamp
                - timedelta(seconds=1)
            ),
        ),
        headers=_headers(),
    )

    assert 400 <= older.status_code < 500

    quote = (
        client.app.state.runtime_quote_authority_v2
        .get_quote(symbol="NQ")
    )

    assert quote is not None
    assert quote["bid"] == 21690.75
    assert quote["ask"] == 21691.00
    assert quote["timestamp"] == newer_timestamp


def test_market_quote_normalizes_symbol(
    monkeypatch,
) -> None:
    client = _client(monkeypatch)

    payload = _payload()
    payload["symbol"] = " nq "

    response = client.post(
        "/market/quote",
        json=payload,
        headers=_headers(),
    )

    assert response.status_code == 201
    assert response.json()["symbol"] == "NQ"

    quote = (
        client.app.state.runtime_quote_authority_v2
        .get_quote(symbol="NQ")
    )

    assert quote is not None


def test_market_quote_does_not_mutate_authority_after_rejected_quote(
    monkeypatch,
) -> None:
    client = _client(monkeypatch)

    accepted_timestamp = datetime.now(timezone.utc)

    accepted = client.post(
        "/market/quote",
        json=_payload(
            bid=21690.75,
            ask=21691.00,
            timestamp=accepted_timestamp,
        ),
        headers=_headers(),
    )

    assert accepted.status_code == 201

    rejected = client.post(
        "/market/quote",
        json=_payload(
            bid=22000.50,
            ask=22000.25,
            timestamp=(
                accepted_timestamp
                + timedelta(seconds=1)
            ),
        ),
        headers=_headers(),
    )

    assert 400 <= rejected.status_code < 500

    quote = (
        client.app.state.runtime_quote_authority_v2
        .get_quote(symbol="NQ")
    )

    assert quote is not None
    assert quote["bid"] == 21690.75
    assert quote["ask"] == 21691.00
    assert quote["timestamp"] == accepted_timestamp
