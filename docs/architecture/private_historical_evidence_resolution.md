# Private historical evidence resolution

The V31 evidence identifies each input by a stable role, original filename and
original SHA-256. Personal directory prefixes are not scientific evidence.
Privacy reconstruction changes those prefixes and necessarily dependent
evidence/code/commit hashes only. The 295 anomaly rows, external input hashes,
calendar, predeclaration times, thresholds, outcomes and certification results
remain unchanged. Existing certification results describe their original runs;
privacy recertification is a separate verification, not a new historical study.

Store a private mapping under ignored `.arms-dev/` or outside the repository.
Its JSON shape is `{"paths": {"<ARMS_AI_SOURCE_EXPORT>/filename.txt":
"absolute local filename"}}`. Include every source, baseline, control and
template identity required by the manifest. Do not commit this mapping.
Roles are `ARMS_AI_SOURCE_EXPORT`, `ARMS_AI_BASELINE_SOURCE`,
`ARMS_AI_PROVENANCE_CONTROL` and `NINJATRADER_TEMPLATE`.

Set `ARMS_AI_PRIVATE_PATH_MAP` to the private mapping file for offline research.
The research reader resolves a copy in memory and verifies every referenced
external file against its existing SHA-256. Missing mappings, unknown identities
and missing or changed inputs fail closed. No source file is rewritten.
Previously local manifests retain their existing behavior.

For the unchanged PAPER runtime, generate a private manifest:

```
py -m backend.tests.private_evidence_paths_v1 --manifest backend/tests/research_v31/sprint05/predeclared_experiment.json --mapping .arms-dev/source-map.json
```

Pass the returned ignored local file to the existing runtime `--manifest`
argument. The Sprint08 soak and Sprint09 process drivers do this automatically
when the private mapping environment variable is set. Public soak evidence
continues to identify the canonical portable manifest, not the private transport
copy. Runtime source/stream hash validation, PAPER authorization, strategy,
risk and accounting remain unchanged. Nothing here authorizes LIVE execution.

Evidence hash reconciliation follows the existing dependency graph, preserving
the byte/newline convention of each prior reference. External source/control/
calendar digests and scientific values are never replaced. Commit references
that identify a reconstructed ancestor follow the corresponding new commit;
Git author/committer identity and milestone messages are retained.
