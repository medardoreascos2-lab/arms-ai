import json
from datetime import date
from datetime import time

import pytest

from backend.services.certified_market_hours_snapshot_loader_v2 import (
    CertifiedMarketHoursSnapshotLoaderV2,
)


def build_document():
    return {
        "covered_dates": [
            "2026-08-18",
            "2026-11-27",
            "2026-12-25",
        ],
        "closed_dates": [
            "2026-12-25",
        ],
        "special_hours": [
            {
                "local_date": "2026-11-27",
                "open_time": "08:30",
                "close_time": "12:15",
            }
        ],
    }


def test_loads_certified_document():
    loader = CertifiedMarketHoursSnapshotLoaderV2()

    calendar, special = loader.load_from_mapping(
        raw=build_document(),
    )

    assert calendar.covered_dates == frozenset(
        {
            date(2026, 8, 18),
            date(2026, 11, 27),
            date(2026, 12, 25),
        }
    )

    assert calendar.closed_dates == frozenset(
        {
            date(2026, 12, 25),
        }
    )

    assert len(special.windows) == 1

    window = special.windows[0]

    assert window.local_date == date(2026, 11, 27)
    assert window.open_time == time(8, 30)
    assert window.close_time == time(12, 15)


def test_loads_from_file(tmp_path):
    path = tmp_path / "certified.json"

    path.write_text(
        json.dumps(build_document()),
        encoding="utf-8",
    )

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    calendar, special = loader.load_from_file(
        file_path=path,
    )

    assert date(2026, 8, 18) in calendar.covered_dates
    assert len(special.windows) == 1


def test_missing_file_fails():
    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(FileNotFoundError):
        loader.load_from_file(
            file_path="missing-certified-file.json",
        )


def test_invalid_json_fails(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text("{invalid", encoding="utf-8")

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(
        ValueError,
        match="JSON válido",
    ):
        loader.load_from_file(file_path=path)


def test_root_must_be_mapping():
    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(TypeError):
        loader.load_from_mapping(raw=[])


def test_rejects_unknown_root_field():
    document = build_document()
    document["invented"] = True

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(
        ValueError,
        match="desconocidos",
    ):
        loader.load_from_mapping(raw=document)


def test_rejects_missing_root_field():
    document = build_document()
    del document["closed_dates"]

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(
        ValueError,
        match="obligatorios",
    ):
        loader.load_from_mapping(raw=document)


def test_date_collections_must_be_lists():
    document = build_document()
    document["covered_dates"] = "2026-08-18"

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(TypeError):
        loader.load_from_mapping(raw=document)


def test_rejects_duplicate_covered_date():
    document = build_document()
    document["covered_dates"].append("2026-08-18")

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(
        ValueError,
        match="duplicadas",
    ):
        loader.load_from_mapping(raw=document)


def test_rejects_invalid_date():
    document = build_document()
    document["covered_dates"][0] = "not-a-date"

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(
        ValueError,
        match="fecha ISO inválida",
    ):
        loader.load_from_mapping(raw=document)


def test_closed_dates_must_be_covered():
    document = build_document()
    document["closed_dates"] = [
        "2027-01-01",
    ]

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(
        ValueError,
        match="subconjunto",
    ):
        loader.load_from_mapping(raw=document)


def test_special_hours_must_be_list():
    document = build_document()
    document["special_hours"] = {}

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(TypeError):
        loader.load_from_mapping(raw=document)


def test_special_hours_item_must_be_mapping():
    document = build_document()
    document["special_hours"] = ["invalid"]

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(TypeError):
        loader.load_from_mapping(raw=document)


def test_rejects_unknown_special_hours_field():
    document = build_document()
    document["special_hours"][0]["invented"] = True

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(
        ValueError,
        match="desconocidos",
    ):
        loader.load_from_mapping(raw=document)


def test_rejects_missing_special_hours_field():
    document = build_document()
    del document["special_hours"][0]["close_time"]

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(
        ValueError,
        match="obligatorios",
    ):
        loader.load_from_mapping(raw=document)


def test_rejects_invalid_time():
    document = build_document()
    document["special_hours"][0]["open_time"] = "99:99"

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(
        ValueError,
        match="hora ISO inválida",
    ):
        loader.load_from_mapping(raw=document)


def test_rejects_timezone_aware_time():
    document = build_document()
    document["special_hours"][0]["open_time"] = (
        "08:30:00+00:00"
    )

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(
        ValueError,
        match="sin timezone",
    ):
        loader.load_from_mapping(raw=document)


def test_rejects_duplicate_special_date():
    document = build_document()
    document["special_hours"].append(
        {
            "local_date": "2026-11-27",
            "open_time": "09:00",
            "close_time": "11:00",
        }
    )

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(
        ValueError,
        match="más de una ventana",
    ):
        loader.load_from_mapping(raw=document)


def test_rejects_reverse_special_window():
    document = build_document()
    document["special_hours"][0]["open_time"] = "13:00"
    document["special_hours"][0]["close_time"] = "12:00"

    loader = CertifiedMarketHoursSnapshotLoaderV2()

    with pytest.raises(
        ValueError,
        match="menor",
    ):
        loader.load_from_mapping(raw=document)
