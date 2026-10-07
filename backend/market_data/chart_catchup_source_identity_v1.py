"""Pinned ArmsChartCatchupBridgeV1 authored source plus NinjaScript wrapper."""

from hashlib import sha256
import re

from backend.market_data.analysis_time_profile_v1 import (
    require,
)
from backend.market_data.chart_catchup_bridge_v1 import (
    EXPORTER_SHA256,
)


BOUNDARY = (
    "#region NinjaScript generated code. "
    "Neither change nor remove."
)

WRAPPER_TOKENS_SHA256 = (
    "f2a6d30fba8edc9b28537e602912424f"
    "aa9f841b5b1bef7b3bac60b5917a9772"
)


def _token_hash(body: str) -> str:
    tokens = re.findall(
        r"[A-Za-z_][A-Za-z_0-9]*"
        r"|[0-9]+"
        r"|==|!=|\+\+|\S",
        body,
    )

    return sha256(
        "\n".join(tokens).encode()
    ).hexdigest()


def verify_chart_catchup_source(
    source,
    *,
    mismatch_reason=(
        "CHART_CATCHUP_EXPORTER_SOURCE_CHANGED"
    ),
):
    require(
        isinstance(
            source,
            (bytes, bytearray),
        ),
        mismatch_reason,
    )

    try:
        text = bytes(source).decode(
            "utf-8"
        )
    except UnicodeDecodeError:
        raise ValueError(
            mismatch_reason
        ) from None

    text = text.replace(
        "\r\n",
        "\n",
    )

    require(
        "\r" not in text
        and "\x00" not in text,
        mismatch_reason,
    )

    count = text.count(
        BOUNDARY
    )

    require(
        count <= 1,
        mismatch_reason,
    )

    authored = text
    generated_tail = "ABSENT"

    if count:
        authored, tail = text.split(
            BOUNDARY,
            1,
        )

        require(
            authored.endswith("\n")
            and tail.startswith("\n"),
            mismatch_reason,
        )

        require(
            tail.count(
                "#endregion"
            )
            == 1
            and tail.rstrip(
                "\n"
            ).endswith(
                "#endregion"
            ),
            mismatch_reason,
        )

        require(
            _token_hash(tail)
            == WRAPPER_TOKENS_SHA256,
            mismatch_reason,
        )

        # NinjaTrader may insert separating blank
        # lines before its generated region. They
        # are not part of the authored source.
        authored_bytes = authored.rstrip(
            "\n"
        ).encode(
            "utf-8"
        )

        generated_tail = (
            "VERIFIED_TOKENS"
        )

    else:
        # Preserve the historical exact authored
        # source semantics when no wrapper exists.
        authored_bytes = authored.rstrip(
            "\n"
        ).encode(
            "utf-8"
        )

    digest = sha256(
        authored_bytes
    ).hexdigest()

    require(
        digest == EXPORTER_SHA256,
        mismatch_reason,
    )

    return {
        "authored_sha256": digest,
        "generated_tail":
            generated_tail,
    }
