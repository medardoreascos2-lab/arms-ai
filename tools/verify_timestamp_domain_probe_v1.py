"""Offline verifier for ArmsTimestampDomainProbeV1 diagnostic evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path

VERSION = "ArmsTimestampDomainProbeV1/1"
RECORD_SCHEMA = "arms.nt.timestamp-domain-probe.record.v1"
SEAL_SCHEMA = "arms.nt.timestamp-domain-probe.seal.v1"

NORMAL_STAGES = [
    "ATTEMPT_STARTED",
    "REQUEST_SUBMITTING",
    "REQUEST_RETURNED",
    "SNAPSHOT_VERIFIED",
    "TIMESTAMP_DOMAIN_CHARACTERIZED",
    "EXPERIMENT_COMPLETE",
]

INLINE_STAGES = [
    "ATTEMPT_STARTED",
    "REQUEST_SUBMITTING",
    "SNAPSHOT_VERIFIED",
    "TIMESTAMP_DOMAIN_CHARACTERIZED",
    "REQUEST_RETURNED",
    "EXPERIMENT_COMPLETE",
]

DIGEST = re.compile(r"^[0-9a-f]{64}$")


def require(value: bool) -> None:
    if not value:
        raise ValueError("invalid timestamp-domain evidence")


def exact_int(value, minimum=None, maximum=None):
    require(type(value) is int)
    if minimum is not None:
        require(value >= minimum)
    if maximum is not None:
        require(value <= maximum)
    return value


def exact_bool(value):
    require(type(value) is bool)
    return value


def parse_uuid(value):
    require(type(value) is str)
    uuid.UUID(value)
    return value


def decode_unique(raw: bytes):
    require(type(raw) is bytes)
    require(raw)

    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out)
            out[key] = value
        return out

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
        )
    except Exception as exc:
        raise ValueError("invalid json") from exc


def verify_evidence(raw: bytes, seal_raw: bytes):
    require(type(raw) is bytes)
    require(type(seal_raw) is bytes)

    require(0 < len(raw) <= 262144)
    require(0 < len(seal_raw) <= 4096)

    require(raw.endswith(b"\n"))

    lines = raw.splitlines()
    require(len(lines) == 6)

    rows = [decode_unique(line) for line in lines]
    seal = decode_unique(seal_raw)

    require(type(seal) is dict)
    require(seal.get("schema") == SEAL_SCHEMA)
    require(seal.get("classification") == "DIAGNOSTIC_ONLY")
    require(seal.get("probe_version") == VERSION)

    probe_uuid = parse_uuid(seal.get("probe_uuid"))
    request_uuid = parse_uuid(seal.get("request_uuid"))

    require(seal.get("sha256") == hashlib.sha256(raw).hexdigest())
    require(seal.get("records") == len(rows))
    require(seal.get("bytes") == len(raw))

    returned_rows = exact_int(
        seal.get("returned_rows"),
        3,
        10002,
    )

    require(seal.get("request_count") == 1)
    require(seal.get("session_iterator_calls") == 0)
    require(seal.get("account_access") is False)
    require(seal.get("order_calls") == 0)
    require(seal.get("execution_authority") is False)
    require(seal.get("timestamp_conversion") is False)
    require(seal.get("diagnostic_complete") is True)
    require(seal.get("writer_closed") is True)
    require(seal.get("certification_evidence") is False)
    require(seal.get("runtime_admission") is False)

    observed_stages = [
        row.get("stage")
        for row in rows
    ]

    require(
        observed_stages == NORMAL_STAGES
        or observed_stages == INLINE_STAGES
    )

    inline = observed_stages == INLINE_STAGES

    snapshot = None

    for index, row in enumerate(rows):
        require(type(row) is dict)

        require(row.get("schema") == RECORD_SCHEMA)
        require(row.get("classification") == "DIAGNOSTIC_ONLY")
        require(row.get("certification_evidence") is False)
        require(row.get("runtime_admission") is False)

        require(row.get("probe_uuid") == probe_uuid)
        require(row.get("probe_version") == VERSION)
        require(row.get("request_uuid") == request_uuid)

        require(row.get("sequence") == index)

        require(row.get("maximum_requests") == 1)
        require(row.get("session_iterator_calls") == 0)
        require(row.get("account_access") is False)
        require(row.get("order_calls") == 0)
        require(row.get("execution_authority") is False)
        require(row.get("timestamp_conversion") is False)

        require(row.get("exception_type") == "NONE")
        require(row.get("exception_message") == "NONE")

        if index == 0:
            require(row.get("request_count") == 0)
            require(row.get("returned_rows") == -1)
            require(row.get("snapshot_sha256") is None)
        else:
            require(row.get("request_count") == 1)

            pre_snapshot = (
                row.get("stage")
                in (
                    "REQUEST_SUBMITTING",
                    "REQUEST_RETURNED",
                )
                and not (
                    inline
                    and row.get("stage")
                    == "REQUEST_RETURNED"
                )
            )

            if pre_snapshot:
                require(row.get("returned_rows") == -1)
                require(row.get("snapshot_sha256") is None)
            else:
                require(row.get("returned_rows") == returned_rows)

                digest = row.get("snapshot_sha256")
                require(
                    type(digest) is str
                    and DIGEST.fullmatch(digest)
                )

                if snapshot is None:
                    snapshot = digest
                else:
                    require(digest == snapshot)

    characterized = next(
        row
        for row in rows
        if row.get("stage")
        == "TIMESTAMP_DOMAIN_CHARACTERIZED"
    )

    payload = characterized.get("payload")
    require(type(payload) is dict)

    require(
        payload.get("interpretation")
        == "RAW_DATETIME_DATE_NO_TIMEZONE_INTERPRETATION"
    )
    require(payload.get("conversion_performed") is False)
    require(payload.get("timestamp_conversion") is False)
    require(payload.get("session_iterator_calls") == 0)
    require(payload.get("account_access") is False)
    require(payload.get("order_calls") == 0)

    require(payload.get("returned_rows") == returned_rows)

    utc = exact_int(payload.get("utc_count"), 0, returned_rows)
    unspecified = exact_int(
        payload.get("unspecified_count"),
        0,
        returned_rows,
    )
    local = exact_int(payload.get("local_count"), 0, returned_rows)

    require(utc + unspecified + local == returned_rows)

    transitions = exact_int(
        payload.get("transition_count"),
        0,
        16,
    )
    require(payload.get("transition_limit") == 16)

    transition_rows = payload.get("transition_rows")
    require(type(transition_rows) is list)
    require(len(transition_rows) == transitions)

    previous_index = -1

    for ordinal, transition in enumerate(
        transition_rows,
        start=1,
    ):
        require(type(transition) is dict)
        require(transition.get("ordinal") == ordinal)

        index = exact_int(
            transition.get("index"),
            1,
            returned_rows - 1,
        )

        require(
            transition.get("previous_index")
            == index - 1
        )
        require(index > previous_index)
        previous_index = index

        previous_kind = transition.get("previous_kind")
        current_kind = transition.get("current_kind")

        require(
            previous_kind
            in ("Utc", "Unspecified", "Local")
        )
        require(
            current_kind
            in ("Utc", "Unspecified", "Local")
        )
        require(previous_kind != current_kind)

        previous_ticks = exact_int(
            transition.get("previous_ticks"),
            0,
        )
        current_ticks = exact_int(
            transition.get("current_ticks"),
            0,
        )

        require(
            transition.get("tick_delta")
            == current_ticks - previous_ticks
        )

    increasing = exact_int(
        payload.get("increasing_adjacent_pairs"),
        0,
        returned_rows - 1,
    )
    duplicates = exact_int(
        payload.get("duplicate_adjacent_timestamps"),
        0,
        returned_rows - 1,
    )
    decreasing = exact_int(
        payload.get("decreasing_adjacent_timestamps"),
        0,
        returned_rows - 1,
    )

    require(
        increasing + duplicates + decreasing
        == returned_rows - 1
    )

    misaligned = exact_int(
        payload.get("minute_misalignment_count"),
        0,
        returned_rows,
    )

    buckets = payload.get("raw_date_buckets")
    require(type(buckets) is dict)

    bucket_count = exact_int(
        payload.get("raw_date_bucket_count"),
        1,
        32,
    )

    require(len(buckets) == bucket_count)

    total = 0
    for key, value in buckets.items():
        require(
            type(key) is str
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", key)
        )
        total += exact_int(value, 1, returned_rows)

    require(total == returned_rows)

    require(rows[5].get("payload") is None)

    return {
        "status": "PASS",
        "classification": "DIAGNOSTIC_ONLY",
        "probe_uuid": probe_uuid,
        "request_uuid": request_uuid,
        "returned_rows": returned_rows,
        "snapshot_sha256": snapshot,
        "utc_count": utc,
        "unspecified_count": unspecified,
        "local_count": local,
        "transition_count": transitions,
        "duplicate_count": duplicates,
        "decreasing_count": decreasing,
        "minute_misalignment_count": misaligned,
        "session_iterator_calls": 0,
        "timestamp_conversion": False,
        "certification_evidence": False,
        "runtime_admission": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", required=True, type=Path)
    parser.add_argument("--seal", required=True, type=Path)
    args = parser.parse_args()

    result = verify_evidence(
        args.diagnostic.read_bytes(),
        args.seal.read_bytes(),
    )

    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
