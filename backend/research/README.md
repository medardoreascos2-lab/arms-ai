# Phase 3 research

The historical dataset registry is append-only and file-backed. Registration
requires an available regular file under an explicit allowed root, valid CSV
or JSONL structure, an exact observed bar count, and an exact SHA-256 digest.
The registry stores immutable metadata for instrument, contract, timeframe,
session template, UTC range, source, standard research window, certification
status, file identity, and registration identity.

The registry never creates, repairs, downloads, or substitutes data. Consumers
must call `require_verified` before use; a missing, invalid, or modified source
fails closed. Certification is descriptive provenance and grants no execution,
production mutation, or administrative authority.

The automated research backtest runner consumes only a currently verified
registry entry. Its identity binds the dataset record and byte hash, strategy
version and source hash, canonical parameter set, exact fee and slippage model,
and optional random seed. Strategies are constructed through an isolated
research factory and return typed decisions. Signals fill on the next bar, one
position at a time, with explicit adverse slippage and per-side fees. Missing,
changed, unordered, malformed, or temporally out-of-range data fails closed.

Results contain deterministic hashes, exact-decimal metrics, a complete trade
list, and an action/block summary. Every run replays the same immutable bars
through a fresh strategy instance a second time and rejects divergent output.
The runner has no broker, PAPER, LIVE, portfolio, or
production state integration and every authority flag remains false.
