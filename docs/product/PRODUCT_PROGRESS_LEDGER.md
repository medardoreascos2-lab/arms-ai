# Product Track C progress ledger

Branch: `product/premium-experience`. Local commits only. No push.

| Milestone | Status | Evidence |
| --- | --- | --- |
| P102A1–P102A2 | Complete, local test boundary | HEAD `2572794`; 62 focused backend tests passed |
| P102A3 thin adapter | Complete | `867f636`; canonical core adapter tests passed |
| P102A4 local mount | Complete | `e7d1599`; disabled, LOCAL, and TEST mount cases passed |
| P102A5 usage limits | Complete | `9b2d90e`; input, output, rate, concurrency, and plan gate tests passed |
| P102A6 degraded states | Complete | `ee7d8e8`; 27 focused backend tests passed |
| P102A7 conversation UI | Complete | Product page and loopback proxy; TypeScript, lint, build, and Product frontend tests passed |
| P102A8 trust panel | Complete | Explicit evidence sections; 8 backend and 5 frontend focused tests, TypeScript, lint, and build passed |
| P102A9 memory context UI | Complete | Evidence-linked categories, provenance, and sensitivity; no memory mutation |
| P102A10 security matrix | Complete | Synthetic allow case and 10 denied cases assert zero downstream invocation |
| P102A11 UI test matrix | Complete | Send/loading state, response evidence, five degraded states, and network failure tested |
| P102A12 final boundary document | Complete | End-to-end local test architecture and no legacy fallback documented |
| P103A Daily Intelligence preview | UI shell complete; data integration pending | Read-only route and Home link with verified-source unavailable states |
| P104-PRE1 customer financial scope | Complete | Immutable trusted-session scope; account and portfolio mutation authority fixed false |
| P104-PRE2 financial read provider | Complete | Provider-neutral protocol exposes nine GET-style observation methods only |
| P104-PRE3 financial projections | Complete | Product-only trading, portfolio, coach, shadow, alert, and daily models require provenance and freshness |
| P104-PRE4 synthetic financial provider | Complete | Deterministic NQ, MNQ, portfolio, coach, shadow, alert, and daily local fixtures |
| P104-PRE5 financial authorization | Complete | Session, active membership, entitlement, tenant/user, account, portfolio, and scope gates precede reads |
| P104-PRE6 financial entitlements | Complete | Five current Product financial features canonical; future unfinished features absent |
| P104-PRE7 financial GET API | Complete | Five loopback local-test routes authorize trusted scope before read-only provider calls |
| P104-PRE8 degraded financial states | Complete | Explicit disabled, unavailable, scope, portfolio, stale, entitlement, and session states |
| P104-PRE9 zero mutation proof | Complete | Contract, HTTP verbs, fixed-false authority, and forbidden dependency imports tested |
| P104-PRE10 Financial Track seam | Complete | Pending adapter and documented public-contract path; no Financial implementation import |
| P104B Trading Coach | Complete, local synthetic | Read-only review summary, strengths, and review items; no advice or execution authority |
| P104C Shadow MEDAR | Complete, local synthetic | Read-only summary, confidence, and evidence; no advice, tool, memory-write, or execution authority |
| P104D Portfolio Guardian | Complete, local synthetic | Read-only value, allocation, concentration, drawdown, and alerts; mutation controls absent |
| P105A Notification domain | Complete | Immutable tenant/user-scoped records, canonical categories/priorities/statuses, and no delivery authority |
| P105B Notification store | Complete, local SQLite | Provider-neutral scoped store, idempotent append, safe state transitions, no delete or delivery operation |
| P105C Notification preferences | Complete, local SQLite | Scoped category thresholds, quiet hours, critical override, six allowed channels, and no external sending |
| P105D Notification Center | Complete, local synthetic | Trusted-session inbox, filters, provenance, degraded states, and explicit status transitions; no external delivery |
| P105E Notification safety matrix | Complete | Wrong tenant/user denied, critical state preserved, no external transport dependency, and all financial authority fixed false |
| P106A Onboarding state | Complete, local SQLite | Durable scoped status/step record, resumable persistence, and optimistic version protection |
| P106B Onboarding goals | Complete | Six optional explicit goals, confirmed-empty support, and no sensitive inference |
| P106C Memory consent | Complete | Four explicit choices, unselected state preserved, and confirmation cannot be inferred or forced |
| P106D Onboarding UI | Complete, local preview | Seven-step resumable flow, optional goals, explicit memory choice, and no forced consent |
| P107A Profile preferences | Complete, local SQLite | Scoped display, language, timezone, theme, accessibility, response, and notification preferences |
| P107B Privacy Center | Complete, provider seams | Memory, retention, export, removal-review, connected-service, and activity projections; no direct deletion |
| P107C Security Center | Complete, read-only | Session/event/permission projections and future MFA/passkey seams; no auth or credential provisioning |
| P108A Membership catalog | Complete | FREE/PRO/PREMIUM/ELITE catalog with configurable non-final prices and no purchase/payment authority |
| P108B Membership entitlements | Complete | Backend-authoritative current feature mapping; future VOICE/VIDEO canonical but disabled from all plans |
| P108C Membership usage limits | Complete | Configurable MEDAR/research/portfolio/notification/memory limits; future voice/video quotas unavailable |
| P109A Billing domain | Complete | Customer/subscription/plan/status/trial/invoice-reference models with payment and charge authority fixed false |
| P109B Billing provider contract | Complete | Provider-neutral interface reserves future STRIPE/OTHER adapters while connection, webhook, and charge capabilities remain false |
| P109C Synthetic billing lifecycle | Complete, local synthetic | Deterministic trial/subscribe/upgrade/downgrade/cancel/expire simulation with idempotency and no charge |
| P109D Billing webhook contract | Complete, interface only | Signed event envelope, idempotency, per-stream ordering, and replay protection with no external endpoint |
| P110A Content-free analytics events | Complete | Seven allowed event types use fixed categorical dimensions and reject conversation, memory, financial, health, and message content |
| P110B Product analytics metrics | Complete | Deterministic DAU/WAU/MAU, D1/D7/D30 retention, adoption, time-to-value, conversion, and churn aggregates |
| P110C Product value metrics | Complete | Content-free repeated-use rates for MEDAR, Daily Intelligence, Trading Coach, Portfolio Guardian, and Research |
| P111A Closed-beta access model | Complete, local projection | Scoped INVITED/ACTIVE/PAUSED/REVOKED/EXPIRED records with optimistic version protection |
| P111B Closed-beta capacity policy | Complete | Configurable admission policy defaults to a 10–30 active-user target and closes at capacity |
| P111C Closed-beta feedback | Complete, local projection | Six feedback types capture scoped categorical metadata while private comments/content remain structurally disabled |
| P112A Responsive Product shell | Complete | Mobile-first shell expands through tablet spacing to a bounded desktop sidebar/content grid |
| P112B Mobile navigation | Complete | Native keyboard-accessible disclosure navigation on mobile/tablet with a sticky desktop sidebar |
| P112C PWA readiness | Complete, installability seam | Next.js manifest and truthful static offline shell; no service worker, offline data, or native app is claimed |
| P103 Daily Intelligence data contract | Complete, local synthetic | Same-origin GET proxy renders trusted daily projection or explicit unavailable state |
| P104A Trading workspace | Complete, local synthetic | Read-only market, session, freshness, and risk views; execution controls absent |

The local Product MEDAR route remains unavailable in the default ARMS API. The
standalone preview binds to loopback and uses synthetic sessions and the canonical
deterministic MEDAR core. No Product path enables tools, memory writes, broker,
PAPER, LIVE, or payment authority.
