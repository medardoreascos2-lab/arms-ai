from __future__ import annotations

import json
import sys
from datetime import datetime
from datetime import timezone
from urllib.error import HTTPError
from urllib.request import Request
from urllib.request import urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_TOKEN = "development-secret"

EXPECTED_PROFIT = 39.0


def request_json(
    *,
    method: str,
    url: str,
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, object]]:
    body = None

    request_headers = {
        "Accept": "application/json",
    }

    if headers:
        request_headers.update(
            headers
        )

    if payload is not None:
        body = json.dumps(
            payload,
            allow_nan=False,
        ).encode(
            "utf-8"
        )

        request_headers[
            "Content-Type"
        ] = "application/json"

    request = Request(
        url=url,
        data=body,
        headers=request_headers,
        method=method,
    )

    try:
        with urlopen(
            request,
            timeout=15,
        ) as response:
            status_code = int(
                response.status
            )

            response_text = (
                response.read()
                .decode(
                    "utf-8"
                )
            )

    except HTTPError as error:
        status_code = int(
            error.code
        )

        response_text = (
            error.read()
            .decode(
                "utf-8"
            )
        )

    try:
        response_payload = json.loads(
            response_text
        )

    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"{method} {url} no devolvió JSON: "
            f"{response_text[:500]}"
        ) from error

    if not isinstance(
        response_payload,
        dict,
    ):
        raise RuntimeError(
            f"{method} {url} devolvió "
            "un JSON que no es objeto."
        )

    return (
        status_code,
        response_payload,
    )


def get_dashboard(
    *,
    base_url: str,
) -> dict[str, object]:
    status_code, snapshot = request_json(
        method="GET",
        url=(
            f"{base_url}"
            "/api/v2/dashboard/live"
        ),
    )

    if status_code != 200:
        raise RuntimeError(
            "Dashboard Live respondió "
            f"{status_code}: {snapshot}"
        )

    json.dumps(
        snapshot,
        allow_nan=False,
    )

    return snapshot


def account_state(
    snapshot: dict[str, object],
) -> dict[str, object]:
    value = snapshot.get(
        "account_state"
    )

    if not isinstance(
        value,
        dict,
    ):
        raise RuntimeError(
            "account_state no está disponible."
        )

    return value


def account_overview(
    snapshot: dict[str, object],
) -> dict[str, object]:
    value = snapshot.get(
        "account_overview"
    )

    if not isinstance(
        value,
        dict,
    ):
        raise RuntimeError(
            "account_overview no está disponible."
        )

    return value


def journal_summary(
    snapshot: dict[str, object],
) -> dict[str, object]:
    value = snapshot.get(
        "trade_journal_summary"
    )

    if not isinstance(
        value,
        dict,
    ):
        raise RuntimeError(
            "trade_journal_summary "
            "no está disponible."
        )

    return value


def performance_overview(
    snapshot: dict[str, object],
) -> dict[str, object]:
    value = snapshot.get(
        "performance_overview"
    )

    if not isinstance(
        value,
        dict,
    ):
        raise RuntimeError(
            "performance_overview "
            "no está disponible."
        )

    return value


def main() -> int:
    base_url = (
        sys.argv[1].rstrip("/")
        if len(sys.argv) > 1
        else DEFAULT_BASE_URL
    )

    token = (
        sys.argv[2]
        if len(sys.argv) > 2
        else DEFAULT_TOKEN
    )

    print(
        "======================================"
    )
    print(
        "LIVE HTTP SMOKE TEST V2"
    )
    print(
        "======================================"
    )

    health_status, health = request_json(
        method="GET",
        url=f"{base_url}/health",
    )

    if health_status != 200:
        raise RuntimeError(
            f"Health respondió {health_status}: "
            f"{health}"
        )

    print(
        "Health:",
        health.get(
            "status"
        ),
    )

    initial = get_dashboard(
        base_url=base_url
    )

    initial_state = account_state(
        initial
    )

    initial_account = account_overview(
        initial
    )

    initial_journal = journal_summary(
        initial
    )

    initial_performance = (
        performance_overview(
            initial
        )
    )

    initial_open_positions = int(
        initial_state[
            "open_positions"
        ]
    )

    if initial_open_positions != 0:
        raise RuntimeError(
            "Ya existe una posición abierta. "
            "Ciérrala o reinicia el backend "
            "antes de ejecutar esta prueba."
        )

    initial_balance = float(
        initial_account[
            "balance"
        ]
    )

    initial_closed_positions = int(
        initial_state[
            "closed_positions"
        ]
    )

    initial_journal_closed = int(
        initial_journal[
            "closed_trades"
        ]
    )

    initial_total_trades = int(
        initial_performance[
            "total_trades"
        ]
    )

    print(
        "Balance inicial:",
        initial_balance,
    )

    print(
        "Trades iniciales:",
        initial_total_trades,
    )

    submit_status, submitted = request_json(
        method="POST",
        url=(
            f"{base_url}"
            "/v2/trades/submit"
        ),
        payload={
            "signal": {
                "approved": True,
                "status": "READY",
                "decision": "SEND_SIGNAL",
                "symbol": "NQ",
                "timeframe": "5M",
                "direction": "LONG",
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 110.0,
                "contracts": 2,
                "probability": 0.92,
                "confluence_score": 0.90,
                "grade": "A+",
                "blocking_reasons": [],
                "warnings": [],
                "summary": (
                    "NQ LONG LIVE HTTP "
                    "SMOKE TEST"
                ),
            },
            "order_type": "MARKET",
        },
    )

    if submit_status != 200:
        raise RuntimeError(
            "Submit Trade respondió "
            f"{submit_status}: {submitted}"
        )

    if submitted.get(
        "accepted"
    ) is not True:
        raise RuntimeError(
            f"Operación rechazada: {submitted}"
        )

    position_id = submitted.get(
        "active_position_id"
    )

    if not position_id:
        raise RuntimeError(
            "No se recibió active_position_id."
        )

    print(
        "Posición abierta:",
        position_id,
    )

    opened = get_dashboard(
        base_url=base_url
    )

    opened_state = account_state(
        opened
    )

    opened_journal = journal_summary(
        opened
    )

    assert (
        int(
            opened_state[
                "open_positions"
            ]
        )
        == initial_open_positions + 1
    )

    assert (
        int(
            opened_journal[
                "open_trades"
            ]
        )
        == 1
    )

    print(
        "Dashboard abierto: OK"
    )

    webhook_status, webhook = request_json(
        method="POST",
        url=(
            f"{base_url}"
            "/market/webhook"
        ),
        headers={
            "X-ARMS-TOKEN": token,
        },
        payload={
            "symbol": "NQ",
            "timeframe": "1M",
            "open": 109.0,
            "high": 111.0,
            "low": 108.0,
            "close": 110.0,
            "volume": 1000.0,
            "timestamp": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "directional_momentum": 0.0,
            "adverse_structure": False,
        },
    )

    if webhook_status != 201:
        raise RuntimeError(
            "Market Webhook respondió "
            f"{webhook_status}: {webhook}"
        )

    price_feed = webhook.get(
        "price_feed"
    )

    if not isinstance(
        price_feed,
        dict,
    ):
        raise RuntimeError(
            "price_feed no está disponible."
        )

    monitor = price_feed.get(
        "monitor_result"
    )

    if not isinstance(
        monitor,
        dict,
    ):
        raise RuntimeError(
            "monitor_result no está disponible."
        )

    assert (
        int(
            monitor[
                "closed_positions"
            ]
        )
        == 1
    )

    print(
        "Webhook y cierre: OK"
    )

    final = get_dashboard(
        base_url=base_url
    )

    final_state = account_state(
        final
    )

    final_account = account_overview(
        final
    )

    final_journal = journal_summary(
        final
    )

    final_performance = (
        performance_overview(
            final
        )
    )

    final_balance = float(
        final_account[
            "balance"
        ]
    )

    expected_balance = round(
        initial_balance
        + EXPECTED_PROFIT,
        10,
    )

    result = {
        "dashboard_status": final.get(
            "dashboard_status"
        ),
        "initial_balance": (
            initial_balance
        ),
        "final_balance": (
            final_balance
        ),
        "balance_change": round(
            final_balance
            - initial_balance,
            10,
        ),
        "open_positions": int(
            final_state[
                "open_positions"
            ]
        ),
        "closed_positions": int(
            final_state[
                "closed_positions"
            ]
        ),
        "journal_open": int(
            final_journal[
                "open_trades"
            ]
        ),
        "journal_closed": int(
            final_journal[
                "closed_trades"
            ]
        ),
        "total_trades": int(
            final_performance[
                "total_trades"
            ]
        ),
        "win_rate": final_performance[
            "win_rate"
        ],
        "net_profit": final_performance[
            "net_profit"
        ],
        "profit_factor": (
            final_performance[
                "profit_factor"
            ]
        ),
    }

    assert (
        result[
            "dashboard_status"
        ]
        == "READY"
    )

    assert (
        final_balance
        == expected_balance
    )

    assert (
        result[
            "open_positions"
        ]
        == 0
    )

    assert (
        result[
            "closed_positions"
        ]
        == initial_closed_positions + 1
    )

    assert (
        result[
            "journal_open"
        ]
        == 0
    )

    assert (
        result[
            "journal_closed"
        ]
        == initial_journal_closed + 1
    )

    assert (
        result[
            "total_trades"
        ]
        == initial_total_trades + 1
    )

    json.dumps(
        result,
        allow_nan=False,
    )

    print()
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
    )

    print()
    print(
        "LIVE HTTP SMOKE TEST COMPLETADO."
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )

    except Exception as error:
        print()
        print(
            "LIVE HTTP SMOKE TEST FALLÓ:"
        )
        print(
            f"{type(error).__name__}: "
            f"{error}"
        )

        raise
