# Phase 5 end-to-end local staging rehearsal (R62B)

The deterministic rehearsal executes one complete synthetic tenant flow through
the R62A local composition:

1. authenticate and authorize `tenant-a/account-1`;
2. ingest and persist a simulated account snapshot;
3. evaluate the canonical prop-firm profile;
4. build portfolio and journal analytics;
5. create one notification and transactional outbox event;
6. deliver it once to a local in-memory sink through the leased worker;
7. enqueue a bounded research job;
8. replay a traced four-bar dataset through the deterministic research backtest;
9. register the result as a research-only challenger;
10. evaluate complete healthy local metrics;
11. read and validate the tenant audit records;
12. copy the SQLite store, create and authenticate an encrypted local-test backup,
    restore it to a separate path, and verify database integrity and tenant rows.

The focused rehearsal and its dependent runtime, worker, research, backup, and
health suites pass. A separate denial case proves that missing authentication
creates no account, snapshot, evaluation, or outbox state.

Every composed result retains zero execution and production mutation authority.
The worker sink has no external delivery authority, the challenger has no PAPER
or LIVE authority, and no PostgreSQL, broker, network provider, cloud service, or
real credential is contacted. The staging status remains `HOLD`.
