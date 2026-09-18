# Phase 2 Certified Calendar and News Operationalization V13

V13 operationalizes the local certified-data lifecycle for PAPER. It does not acquire external data, select a vendor, or connect to LIVE execution.

## Canonical owners

- Economic news: `CertifiedEconomicNewsDataLifecycleV2` and `EconomicNewsRuntimeProviderV2`
- Market hours: `CertifiedMarketHoursDataLifecycleV2` and `CertifiedMarketHoursRuntimeProviderV2`
- Admission block: `RuntimeAdmissionV2`, which consumes the lifecycle providers
- Operator refresh: protected `/api/v2/economic-news/refresh` and `/api/v2/market-hours/refresh`

## Input contract

Economic-news JSON must contain exactly:

```json
{
  "snapshot_version": "operator-2026-09-08-v1",
  "generated_at": "2026-09-08T14:00:00+00:00",
  "coverage_start": "2026-09-08T14:00:00+00:00",
  "coverage_end": "2026-09-08T16:00:00+00:00",
  "high_impact_events": ["2026-09-08T14:30:00+00:00"]
}
```

Market-hours JSON must contain exactly `covered_dates`, `closed_dates`, and `special_hours` with the schema enforced by `CertifiedMarketHoursSnapshotLoaderV2`.

The operator obtains and certifies these files outside ARMS AI, places them at local paths, and configures `ARMS_CERTIFIED_ECONOMIC_NEWS_PATH` and `ARMS_CERTIFIED_MARKET_HOURS_PATH`. No vendor credentials or external acquisition is part of this package.

## Startup and inspection

Start the canonical PAPER backend with the V12 environment and paths:

```text
ARMS_CERTIFIED_ECONOMIC_NEWS_PATH=C:/certified/economic-news.json
ARMS_CERTIFIED_MARKET_HOURS_PATH=C:/certified/market-hours.json
python -m uvicorn backend.api.asgi:app --host 127.0.0.1 --port 8000
```

Invalid or missing configured files fail startup. Without an active certified snapshot, news and market-hours authorities fail closed.

Inspect active provenance and coverage:

```text
curl http://127.0.0.1:8000/api/v2/economic-news/status
curl "http://127.0.0.1:8000/api/v2/economic-news/coverage?timestamp=2026-09-08T15:00:00Z"
curl http://127.0.0.1:8000/api/v2/market-hours/status
curl "http://127.0.0.1:8000/api/v2/market-hours/coverage?date=2026-09-08"
```

The refresh endpoints require the configured `X-ARMS-ADMIN-TOKEN` and accept a local file path. Each candidate is fully validated before replacing the active provider. A failed replacement preserves the last valid provider and activation report.

```text
POST /api/v2/economic-news/refresh
{"file_path":"C:/certified/economic-news-next.json"}

POST /api/v2/market-hours/refresh
{"file_path":"C:/certified/market-hours-next.json"}
```

Verify the returned `snapshot_version`, source path, coverage, and activation report, then query status and coverage again. Keep the prior valid file until the replacement has been validated and observed.

## Safety behavior

A timestamp outside explicit economic-news coverage is blocked. A high-impact event is blocked. Missing, malformed, unsupported, stale-by-coverage, or invalid replacement data never becomes an implicit clear/no-news state. Market-hours dates outside explicit coverage are closed.

The V13 regression suite proves schema rejection, missing-input fail-closed behavior, atomic invalid replacement rollback, protected activation, provenance, runtime coverage, high-impact news rejection, and no PAPER fill/position/P&L/journal mutation:

```text
python -m pytest backend/tests/test_certified_economic_news_operationalization_v13.py -q
```

## Roll-forward and recovery

1. Obtain and independently certify a new file.
2. Validate it offline against the exact schema.
3. Place it beside the active file, without overwriting the active file.
4. Activate it through the protected refresh endpoint.
5. Check version, source, coverage, and runtime status.
6. If activation fails, retain the prior file and investigate the reported validation error.
7. If the active file is stale or missing after restart, keep the runtime fail closed and restore the last certified file before restarting.

MVP-010 is closed for this local operator-maintained lifecycle. External acquisition remains intentionally separate and is not claimed as implemented.
