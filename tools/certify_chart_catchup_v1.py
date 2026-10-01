"""Build one hash-pinned base + loaded-chart catch-up bootstrap bundle.

Offline only: no feed watcher, account access, order routing or runtime arming.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from backend.market_data.certified_bootstrap_v1 import (
    certify_bootstrap,
)
from backend.market_data.chart_catchup_bridge_v1 import (
    SCHEMA,
)
from backend.market_data.chart_catchup_source_identity_v1 import (
    verify_chart_catchup_source,
)
from backend.market_data.native_historical_bootstrap_v1 import (
    report,
)
from backend.market_data.fresh_native_adapter_v1 import (
    local_path,
)
from tools.certify_analysis_bootstrap_v1 import (
    bounded_read,
)


def build_bundle(
    base,
    bridge,
    seal,
    source,
):
    source_identity = (
        verify_chart_catchup_source(
            source
        )
    )

    source_hash = (
        source_identity[
            "authored_sha256"
        ]
    )

    base_sha = sha256(
        base
    ).hexdigest()

    certify_bootstrap(
        base,
        expected_sha256=
            base_sha,
    )

    raw = json.dumps(
        {
            "schema":
                SCHEMA,
            "authored_sha256":
                source_hash,
            "base_sha256":
                base_sha,
            "base_utf8":
                base.decode(
                    "utf-8"
                ),
            "bridge_utf8":
                bridge.decode(
                    "utf-8"
                ),
            "seal_utf8":
                seal.decode(
                    "utf-8"
                ),
        },
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )

    digest = sha256(
        raw
    ).hexdigest()

    data = certify_bootstrap(
        raw,
        expected_sha256=digest,
    )

    return (
        raw,
        report(data),
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    for name in (
        "base",
        "bridge",
        "seal",
        "exporter-source",
        "output",
    ):
        parser.add_argument(
            "--" + name,
            type=Path,
            required=True,
        )

    args = parser.parse_args()

    base = bounded_read(
        args.base.resolve()
    )

    bridge = bounded_read(
        args.bridge.resolve()
    )

    seal = bounded_read(
        args.seal.resolve()
    )

    source = bounded_read(
        args.exporter_source.resolve()
    )

    raw, result = build_bundle(
        base,
        bridge,
        seal,
        source,
    )

    output = local_path(
        args.output.resolve()
    )

    with output.open(
        "xb"
    ) as handle:
        handle.write(raw)

    print(
        json.dumps(
            {
                "status":
                    "OFFLINE_VALIDATED_CHART_CATCHUP",
                **result,
            }
        )
    )


if __name__ == "__main__":
    main()
