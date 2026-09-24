"""R5.4-C native repair evidence verifier.

Validates the bounded file/JSON/hash contract only.
It does not attest that NinjaTrader produced the files.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import uuid


EVIDENCE = "session-query-domain-repair.json"
SEAL = "session-query-domain-repair.done.json"

MAX_EVIDENCE = 65536
MAX_SEAL = 8192


def need(value: bool) -> None:
    if not value:
        raise ValueError("INVALID_R54_REPAIR_EVIDENCE")


def exact_keys(value: dict, expected: set[str]) -> None:
    need(type(value) is dict)
    need(set(value) == expected)


def no_links(path: Path) -> None:
    for item in (path, *path.parents):
        stat = item.lstat()

        need(not item.is_symlink())

        attrs = getattr(
            stat,
            "st_file_attributes",
            0,
        )

        need(not (attrs & 0x400))


def read_limited(path: Path, maximum: int) -> bytes:
    no_links(path)

    need(path.is_file())

    size = path.stat().st_size

    need(0 < size <= maximum)

    data = path.read_bytes()

    need(len(data) == size)

    return data


def timestamp(value: dict) -> dict:
    exact_keys(
        value,
        {"clock", "ticks", "kind"},
    )

    need(
        type(value["clock"]) is str
        and len(value["clock"]) == 27
    )

    need(
        type(value["ticks"]) is int
        and value["ticks"] >= 0
    )

    need(
        value["kind"]
        in {"Unspecified", "Utc", "Local"}
    )

    return value


def verify_capture(capture: Path) -> dict:
    capture = Path(capture).absolute()

    no_links(capture)
    need(capture.is_dir())

    need(
        {x.name for x in capture.iterdir()}
        == {EVIDENCE, SEAL}
    )

    evidence_raw = read_limited(
        capture / EVIDENCE,
        MAX_EVIDENCE,
    )

    seal_raw = read_limited(
        capture / SEAL,
        MAX_SEAL,
    )

    evidence = json.loads(
        evidence_raw.decode("utf-8")
    )

    seal = json.loads(
        seal_raw.decode("utf-8")
    )

    evidence_keys = {
        "schema",
        "version",
        "classification",
        "origin",
        "probe_uuid",
        "diagnostic_complete",
        "source_before",
        "source_after",
        "source_preserved",
        "adapter",
        "observations",
        "iterator_constructor_attempts",
        "getnextsession_attempts",
        "expected_pattern_confirmed",
        "native_provenance_attested",
        "certification_evidence",
        "runtime_admission",
        "execution_authority",
        "exporter_change",
        "stored_timestamp_mutation",
    }

    seal_keys = {
        "schema",
        "version",
        "classification",
        "origin",
        "probe_uuid",
        "diagnostic_complete",
        "writer_closed",
        "evidence_file",
        "evidence_bytes",
        "evidence_sha256",
        "expected_pattern_confirmed",
        "source_preserved",
        "iterator_constructor_attempts",
        "getnextsession_attempts",
        "native_provenance_attested",
        "certification_evidence",
        "runtime_admission",
        "execution_authority",
    }

    exact_keys(evidence, evidence_keys)
    exact_keys(seal, seal_keys)

    need(
        evidence["schema"]
        == "arms.r54.native-repair.record.v1"
    )

    need(
        seal["schema"]
        == "arms.r54.native-repair.seal.v1"
    )

    need(
        evidence["version"]
        == seal["version"]
        == "R5.4-C/native-repair-host/1"
    )

    need(
        evidence["classification"]
        == seal["classification"]
        == "DIAGNOSTIC_ONLY"
    )

    need(
        evidence["origin"]
        == seal["origin"]
        == "OPERATOR_NATIVE_RUN_UNATTESTED"
    )

    probe = uuid.UUID(
        evidence["probe_uuid"]
    )

    need(
        str(probe)
        == evidence["probe_uuid"]
        == seal["probe_uuid"]
    )

    need(
        evidence["diagnostic_complete"]
        is True
    )

    need(
        seal["diagnostic_complete"]
        is True
        and seal["writer_closed"] is True
    )

    need(
        seal["evidence_file"]
        == EVIDENCE
    )

    need(
        seal["evidence_bytes"]
        == len(evidence_raw)
    )

    need(
        seal["evidence_sha256"]
        == sha256(evidence_raw).hexdigest()
    )

    before = timestamp(
        evidence["source_before"]
    )

    after = timestamp(
        evidence["source_after"]
    )

    preserved = (
        before["ticks"] == after["ticks"]
        and before["kind"] == after["kind"]
    )

    need(
        evidence["source_preserved"]
        is preserved
    )

    need(
        seal["source_preserved"]
        is preserved
    )

    adapter = evidence["adapter"]

    exact_keys(
        adapter,
        {
            "source_ticks",
            "source_kind",
            "query_ticks",
            "query_kind",
            "source_offset_ticks",
            "zone_id",
            "zone_fingerprint_sha256",
            "policy",
            "provenance",
            "conversion_performed",
        },
    )

    need(
        adapter["source_ticks"]
        == before["ticks"]
    )

    need(
        adapter["source_kind"]
        == before["kind"]
        == "Unspecified"
    )

    need(
        adapter["query_kind"] == "Utc"
    )

    need(
        type(adapter["source_offset_ticks"])
        is int
    )

    need(
        adapter["zone_id"]
        == "Central Standard Time"
    )

    need(
        type(adapter["zone_fingerprint_sha256"])
        is str
        and len(
            adapter["zone_fingerprint_sha256"]
        ) == 64
    )

    need(
        adapter["policy"]
        == "TradingHoursWallClockToUtc"
    )

    need(
        adapter["provenance"]
        == "R53_NATIVE_REGRESSION"
    )

    need(
        adapter["conversion_performed"]
        is True
    )

    observations = evidence["observations"]

    need(
        type(observations) is list
        and len(observations) == 3
    )

    expected_ids = (
        "C_RAW",
        "C_SAME_TICKS",
        "C_ADAPTER",
    )

    normalized = []

    for index, item in enumerate(observations):
        exact_keys(
            item,
            {
                "case_id",
                "query",
                "returned",
                "begin",
                "end",
                "bounds_readable",
                "bounds_valid",
                "constructor_attempts",
                "call_attempts",
            },
        )

        need(
            item["case_id"]
            == expected_ids[index]
        )

        query = timestamp(item["query"])

        need(
            type(item["returned"]) is bool
        )

        need(
            type(item["bounds_readable"])
            is bool
        )

        need(
            type(item["bounds_valid"])
            is bool
        )

        need(
            item["constructor_attempts"]
            == index + 1
        )

        need(
            item["call_attempts"]
            == index + 1
        )

        if item["returned"]:
            need(
                item["begin"] is not None
                and item["end"] is not None
            )

            begin = timestamp(item["begin"])
            end = timestamp(item["end"])

            need(
                item["bounds_readable"]
                is True
            )

            need(
                item["bounds_valid"]
                is True
            )

            need(
                end["ticks"] > begin["ticks"]
            )
        else:
            need(
                item["begin"] is None
                and item["end"] is None
            )

            need(
                item["bounds_readable"]
                is False
            )

            need(
                item["bounds_valid"]
                is False
            )

        normalized.append(
            (item, query)
        )

    raw, raw_query = normalized[0]
    relabel, relabel_query = normalized[1]
    adapted, adapted_query = normalized[2]

    need(
        raw_query["ticks"]
        == relabel_query["ticks"]
        == before["ticks"]
    )

    need(
        raw_query["kind"]
        == "Unspecified"
    )

    need(
        relabel_query["kind"]
        == "Utc"
    )

    need(
        adapted_query["ticks"]
        == adapter["query_ticks"]
    )

    need(
        adapted_query["kind"]
        == "Utc"
    )

    need(
        adapted_query["ticks"]
        != relabel_query["ticks"]
    )

    pattern = (
        raw["returned"] is False
        and relabel["returned"] is False
        and adapted["returned"] is True
        and adapted["bounds_readable"] is True
        and adapted["bounds_valid"] is True
    )

    need(
        evidence[
            "expected_pattern_confirmed"
        ] is pattern
    )

    need(
        seal[
            "expected_pattern_confirmed"
        ] is pattern
    )

    need(
        evidence[
            "iterator_constructor_attempts"
        ] == 3
    )

    need(
        evidence[
            "getnextsession_attempts"
        ] == 3
    )

    need(
        seal[
            "iterator_constructor_attempts"
        ] == 3
    )

    need(
        seal[
            "getnextsession_attempts"
        ] == 3
    )

    for obj in (evidence, seal):
        need(
            obj["native_provenance_attested"]
            is False
        )

        need(
            obj["certification_evidence"]
            is False
        )

        need(
            obj["runtime_admission"]
            is False
        )

        need(
            obj["execution_authority"]
            is False
        )

    need(
        evidence["exporter_change"]
        is False
    )

    need(
        evidence["stored_timestamp_mutation"]
        is False
    )

    return {
        "status":
            "PASS_R54_REPAIR_DIAGNOSTIC_CONTRACT_ONLY",
        "origin_claim":
            evidence["origin"],
        "probe_uuid":
            evidence["probe_uuid"],
        "source_preserved":
            preserved,
        "expected_pattern_confirmed":
            pattern,
        "iterator_constructor_attempts":
            3,
        "getnextsession_attempts":
            3,
        "evidence_sha256":
            sha256(evidence_raw).hexdigest(),
        "native_provenance_attested":
            False,
        "certification_evidence":
            False,
        "runtime_admission":
            False,
        "execution_authority":
            False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--capture",
        required=True,
    )

    args = parser.parse_args()

    try:
        result = verify_capture(
            Path(args.capture)
        )
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        UnicodeError,
        json.JSONDecodeError,
    ):
        print(
            json.dumps(
                {"status": "REJECTED"},
                sort_keys=True,
            )
        )

        return 1

    print(
        json.dumps(
            result,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
