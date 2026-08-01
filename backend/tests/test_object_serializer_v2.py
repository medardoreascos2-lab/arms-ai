from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import pytest

from backend.serialization.object_serializer_v2 import (
    ObjectSerializerV2,
)


class SampleAction(Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class SampleDecision:
    action: SampleAction
    confidence: float
    created_at: datetime


class ObjectWithToDict:

    def to_dict(self):
        return {
            "status": "READY",
            "path": Path("reports/result.json"),
        }


def test_serializes_primitive_values():

    serializer = ObjectSerializerV2()

    assert serializer.serialize(None) is None
    assert serializer.serialize(True) is True
    assert serializer.serialize(10) == 10
    assert serializer.serialize(10.5) == 10.5
    assert serializer.serialize("NQ") == "NQ"


def test_serializes_enum_to_value():

    serializer = ObjectSerializerV2()

    assert (
        serializer.serialize(SampleAction.BUY)
        == "BUY"
    )


def test_serializes_datetime_to_isoformat():

    serializer = ObjectSerializerV2()

    value = datetime(
        2026,
        8,
        1,
        13,
        30,
        tzinfo=timezone.utc,
    )

    assert serializer.serialize(value) == (
        "2026-08-01T13:30:00+00:00"
    )


def test_serializes_path_to_string():

    serializer = ObjectSerializerV2()

    assert serializer.serialize(
        Path("reports/backtest.json")
    ) == str(
        Path("reports/backtest.json")
    )


def test_serializes_dataclass_recursively():

    serializer = ObjectSerializerV2()

    decision = SampleDecision(
        action=SampleAction.BUY,
        confidence=0.95,
        created_at=datetime(
            2026,
            8,
            1,
            9,
            30,
        ),
    )

    assert serializer.serialize(decision) == {
        "action": "BUY",
        "confidence": 0.95,
        "created_at": "2026-08-01T09:30:00",
    }


def test_serializes_nested_collections():

    serializer = ObjectSerializerV2()

    payload = {
        "decisions": [
            SampleDecision(
                action=SampleAction.SELL,
                confidence=0.90,
                created_at=datetime(
                    2026,
                    8,
                    1,
                    10,
                    0,
                ),
            ),
        ],
        "tags": {
            "A+",
            "NQ",
        },
        "values": (
            1,
            2,
        ),
    }

    result = serializer.serialize(payload)

    assert result["decisions"] == [
        {
            "action": "SELL",
            "confidence": 0.90,
            "created_at": "2026-08-01T10:00:00",
        },
    ]

    assert sorted(result["tags"]) == [
        "A+",
        "NQ",
    ]

    assert result["values"] == [
        1,
        2,
    ]


def test_uses_to_dict_recursively():

    serializer = ObjectSerializerV2()

    assert serializer.serialize(
        ObjectWithToDict()
    ) == {
        "status": "READY",
        "path": str(
            Path("reports/result.json")
        ),
    }


def test_does_not_modify_original_object():

    serializer = ObjectSerializerV2()

    payload = {
        "items": [
            {
                "value": 1,
            },
        ],
    }

    result = serializer.serialize(payload)

    result["items"][0]["value"] = 99

    assert payload == {
        "items": [
            {
                "value": 1,
            },
        ],
    }


def test_rejects_unsupported_object():

    serializer = ObjectSerializerV2()

    with pytest.raises(
        TypeError,
        match="serializable",
    ):
        serializer.serialize(
            object()
        )
