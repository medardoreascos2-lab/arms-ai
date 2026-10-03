# ARMS AI notifications

## Event domain (R27A)

`event_domain.py` defines immutable events for signal candidates and rejections, PAPER trade opens and closes, risk and daily-limit blocks, drawdown warnings, account failures, payout eligibility, and system and data faults. Each event carries severity, an aware timestamp, optional account and complete profile identity, a deterministic dedupe identity, a unique content ID, an immutable safe payload, and an explicit redaction policy.

Payloads accept only scalar strings, integers, booleans, finite `Decimal` values, and `None`. Sensitive keys and recognizable credential text are redacted by default or rejected under the strict policy. Nested objects, floats, binary data, and partial profile identity are rejected.

This milestone contains no dispatcher, provider, credential, network call, message send, broker action, or execution authority.
