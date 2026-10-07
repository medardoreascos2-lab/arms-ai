"""ArmsChartCatchupBridgeV1 source identity contract."""

from hashlib import sha256
from pathlib import Path
import re

import pytest

import backend.market_data.chart_catchup_source_identity_v1 as identity
from backend.market_data.chart_catchup_bridge_v1 import (
    CURRENT_EXPORTER_SHA256,
    LEGACY_EXPORTER_SHA256,
)


SOURCE = Path(
    "integrations/ninjatrader/"
    "ArmsChartCatchupBridgeV1.cs"
).resolve()


def normalized_source():
    return (
        SOURCE.read_bytes()
        .replace(
            b"\r\n",
            b"\n",
        )
    )


def wrapped_source(body):
    authored = (
        normalized_source()
        .rstrip(b"\n")
        + b"\n\n"
    )

    return (
        authored
        + identity.BOUNDARY.encode()
        + b"\n"
        + body.encode()
        + b"\n#endregion\n"
    )


def token_hash(body):
    tokens = re.findall(
        r"[A-Za-z_][A-Za-z_0-9]*"
        r"|[0-9]+"
        r"|==|!=|\+\+|\S",
        body,
    )

    return sha256(
        "\n".join(tokens).encode()
    ).hexdigest()


def test_authored_source_is_certified():
    result = (
        identity
        .verify_chart_catchup_source(
            normalized_source()
        )
    )

    assert (
        result["authored_sha256"]
        == identity.EXPORTER_SHA256
    )

    assert (
        result["generated_tail"]
        == "ABSENT"
    )


def test_authored_mutation_fails_closed():
    with pytest.raises(
        ValueError,
        match=(
            "CHART_CATCHUP_EXPORTER_SOURCE_CHANGED"
        ),
    ):
        identity.verify_chart_catchup_source(
            normalized_source()
            + b" "
        )


def test_legacy_bundle_identity_cannot_satisfy_current_source_verification():
    assert identity.EXPORTER_SHA256 == CURRENT_EXPORTER_SHA256
    assert LEGACY_EXPORTER_SHA256 != identity.EXPORTER_SHA256

    with pytest.raises(
        ValueError,
        match="CHART_CATCHUP_EXPORTER_SOURCE_CHANGED",
    ):
        identity.verify_chart_catchup_source(
            LEGACY_EXPORTER_SHA256.encode("ascii")
        )


def test_custom_failure_reason_is_preserved():
    with pytest.raises(
        ValueError,
        match=(
            "STARTUP_CATCHUP_INSTALLED_SOURCE"
        ),
    ):
        identity.verify_chart_catchup_source(
            normalized_source()
            + b" ",
            mismatch_reason=(
                "STARTUP_CATCHUP_INSTALLED_SOURCE"
            ),
        )


def test_generated_wrapper_requires_pinned_tokens(
    monkeypatch,
):
    body = (
        "namespace NinjaTrader "
        "{ class Generated { } }"
    )

    monkeypatch.setattr(
        identity,
        "WRAPPER_TOKENS_SHA256",
        token_hash(body + "\n#endregion"),
    )

    result = (
        identity
        .verify_chart_catchup_source(
            wrapped_source(body)
        )
    )

    assert (
        result["authored_sha256"]
        == identity.EXPORTER_SHA256
    )

    assert (
        result["generated_tail"]
        == "VERIFIED_TOKENS"
    )


def test_unreviewed_generated_wrapper_fails_closed():
    body = (
        "namespace NinjaTrader "
        "{ class Unreviewed { } }"
    )

    with pytest.raises(
        ValueError,
        match=(
            "CHART_CATCHUP_EXPORTER_SOURCE_CHANGED"
        ),
    ):
        identity.verify_chart_catchup_source(
            wrapped_source(body)
        )


def test_multiple_generated_boundaries_fail_closed():
    raw = (
        normalized_source()
        + b"\n"
        + identity.BOUNDARY.encode()
        + b"\n#endregion\n"
        + identity.BOUNDARY.encode()
        + b"\n#endregion\n"
    )

    with pytest.raises(
        ValueError,
        match=(
            "CHART_CATCHUP_EXPORTER_SOURCE_CHANGED"
        ),
    ):
        identity.verify_chart_catchup_source(
            raw
        )
