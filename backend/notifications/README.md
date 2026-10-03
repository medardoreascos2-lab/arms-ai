# ARMS AI notifications

## Event domain (R27A)

`event_domain.py` defines immutable events for signal candidates and rejections, PAPER trade opens and closes, risk and daily-limit blocks, drawdown warnings, account failures, payout eligibility, and system and data faults. Each event carries severity, an aware timestamp, optional account and complete profile identity, a deterministic dedupe identity, a unique content ID, an immutable safe payload, and an explicit redaction policy.

Payloads accept only scalar strings, integers, booleans, finite `Decimal` values, and `None`. Sensitive keys and recognizable credential text are redacted by default or rejected under the strict policy. Nested objects, floats, binary data, and partial profile identity are rejected.

This milestone contains no dispatcher, provider, credential, network call, message send, broker action, or execution authority.

## Dispatch foundation (R27B)

`dispatch.py` adds provider-independent delivery contracts, disabled and deterministic fake providers, bounded process-local deduplication, fixed-window rate limiting, explicit retry scheduling, and immutable delivery results. Telegram, WhatsApp, email, and in-app are provider seams only.

The dispatcher validates the already-redacted event before a provider sees it. Dedupe and rate-limit failures stop before provider delivery. A delivery whose dedupe commit cannot be confirmed is reported as `DELIVERY_UNCONFIRMED` and its in-flight claim remains reserved to prevent an automatic resend.

There are no credentials, network clients, background workers, live transports, broker calls, trading state mutations, or execution authority in this package. Process-local dedupe state does not survive restart; persistent delivery state remains a future integration concern.

## Telegram foundation (R27C)

`telegram.py` defines a Telegram configuration restricted to `DISABLED` and `TEST`, a deterministic plain-text formatter, a transport protocol, a fake recording transport, and a provider adapter that uses the R27B retry result seam. The configuration deliberately has no bot token, endpoint, numeric chat ID, or live mode.

Disabled configuration builds the global disabled provider. Test mode requires an explicit transport and logical channel alias. The formatter revalidates the event payload, escapes string control characters through JSON representation, and rejects oversized output before the transport is called.

No HTTP client, Telegram SDK, network transport, real credential, or actual message send is implemented.
