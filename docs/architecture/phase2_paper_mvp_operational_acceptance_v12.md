# Phase 2 PAPER MVP Operational Acceptance V12

This runbook exercises the local deterministic PAPER acceptance harness. It does not connect to a broker or enable LIVE execution.

## Safe environment

Set local-only values in the shell. Never commit credential values.

```text
ARMS_ADMIN_TOKEN=<local-only-admin-token>
ARMS_WEBHOOK_TOKEN=<local-only-webhook-token>
ARMS_MAXIMUM_QUOTE_AGE_SECONDS=30
ARMS_MINIMUM_REWARD_RISK_RATIO=2
ARMS_MINIMUM_STOP_POINTS=1
ARMS_MAXIMUM_STOP_POINTS=100
ARMS_MAXIMUM_SPREAD_POINTS=5
ARMS_MINIMUM_ATR_POINTS=1
ARMS_MINIMUM_A_PLUS_PROBABILITY=0.8
ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE=0.8
ARMS_MAXIMUM_SIGNAL_AGE_SECONDS=300
ARMS_MAXIMUM_OPEN_POSITIONS=1
```

The acceptance fixture supplies isolated PAPER account profiles, certified test hours/news JSON, and deterministic market input. Production startup may additionally set `ARMS_CERTIFIED_MARKET_HOURS_PATH` and `ARMS_CERTIFIED_ECONOMIC_NEWS_PATH` to operator-maintained certified files. Missing or invalid required policy values fail closed.

## Backend

From `C:/Development/ARMS-AI`, run the canonical ASGI entry point:

```text
python -m uvicorn backend.api.asgi:app --host 127.0.0.1 --port 8000
```

Readiness check:

```text
curl http://127.0.0.1:8000/health
```

Expected PAPER checks are performed by:

```text
python -m pytest backend/tests/test_phase2_paper_mvp_operational_acceptance_v12.py -q
```

The suite proves no-trade rejection, risk rejection without broker/fill/financial mutation, one valid PAPER fill and close, dashboard HTTP/WebSocket projection, account switch socket retirement, and durable restart recovery. The market fixture enters through the canonical admission owner; it does not call a broker.

## Frontend

In a second shell:

```text
cd frontend
npm run dev
```

Open `http://127.0.0.1:3000/dashboard-v2`, enter the same local-only admin token, and select `Conectar PAPER`. The dashboard uses protected HTTP and the authorized WebSocket. Stop the backend and frontend with `Ctrl+C`; no order is sent outside the PAPER test/runtime boundary.

## Evidence boundary

V12 proves the controlled local PAPER path and records it for MVP-023. MVP-010 remains open because certified calendar/news coverage and its operator renewal process require maintained operator-supplied inputs. MVP-024 remains P2 because arbitrary empirical strategy/dataset certification is not proven by the deterministic operational fixture.
