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
