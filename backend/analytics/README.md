# ARMS AI analytics

## Identified trade journal analytics (R26B)

`prop_firm_trade_journal_analytics.py` calculates read-only performance metrics for immutable, identified closed trades. It reports win rate, average win and loss, expectancy, profit factor with an explicit undefined state, R-multiple coverage and buckets, and session, instrument, account, and firm distributions.

Financial values use `Decimal`; floats, nonfinite values, zero or negative risk, duplicate IDs, mutable input containers, and missing identity tags are rejected. A missing initial risk leaves that trade out of R calculations and is listed by ID rather than receiving an invented value. Empty journals and zero-profit cases have stable results without division errors.

The module does not import the mutable journal, broker, PAPER, LIVE, position, account, payout, or execution services. Its output hard-codes `execution_authorized=False`.
