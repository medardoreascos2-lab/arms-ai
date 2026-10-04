# NQ and MNQ staging instrument contract (R73A)

## Canonical definitions

| Field | NQ | MNQ |
| --- | --- | --- |
| Symbol family | `NASDAQ_100_EQUITY_INDEX_FUTURES` | `NASDAQ_100_EQUITY_INDEX_FUTURES` |
| Exchange / venue | CME / CME Globex | CME / CME Globex |
| Tick size | `0.25` index points | `0.25` index points |
| Point value / multiplier | `USD 20.00` per index point | `USD 2.00` per index point |
| Tick value | `USD 5.00` | `USD 0.50` |
| Listing cycle | March, June, September, December | March, June, September, December |
| Canonical identity | `NQ-YYYY-MM` | `MNQ-YYYY-MM` |

The definitions use exact Python `Decimal` values. NQ and MNQ share an
underlying symbol family and session template, but retain separate canonical
identities and a ten-to-one point-value difference.

## Session and contract resolution

The allowed session references CME Globex US Equity Index hours in
`America/New_York`, including the weekly boundary, daily maintenance period and
documented intraday halt. The exchange schedule remains external reference data
that an operator must revalidate before provisioning or any later market-data
connection.

No current delivery month is embedded. Callers supply a four-digit year and a
quarterly month to obtain a canonical identity. A future market-data adapter
must list eligible contracts and apply an approved liquidity-aware rollover
policy. Vendor exchange symbols remain adapter output because a one-digit year
code is not a globally unique stored identity.

## Official evidence reviewed 2026-10-03

- CME describes NQ as `USD 20 x Nasdaq-100 Index` with a `0.25` point minimum
  tick (`USD 5.00`):
  <https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.margins.html>.
- CME describes MNQ as `USD 2 x Nasdaq-100 Index` with a `0.25` point minimum
  tick (`USD 0.50`):
  <https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.options.html>.
- CME documents the quarterly cycle, five listed months and current Globex
  session information:
  <https://www.cmegroup.com/articles/faqs/micro-e-mini-equity-index-futures-frequently-asked-questions.html>.

These are contract metadata references, not real-time market data and not a
claim of historical or future performance.

`NQ_SUPPORT=TRUE`

`MNQ_SUPPORT=TRUE`

`CURRENT_CONTRACT_HARDCODED=FALSE`

`REAL_MARKET_DATA_USED=FALSE`

`BROKER_AUTHORITY=FALSE`

`PAPER_AUTHORITY=FALSE`

`LIVE_AUTHORITY=FALSE`
