import json

import pytest

from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)

from backend.accounts.account_registry_v1 import (
    AccountRegistryV1,
)


def write_config(
    path,
    account_name,
):

    path.write_text(
        json.dumps(
            {
                "active_account":
                    account_name,
            }
        ),
        encoding="utf-8",
    )


def test_loads_active_account_from_config(
    tmp_path,
):

    config_path = (
        tmp_path
        / "accounts.json"
    )

    write_config(
        config_path,
        "TAKE_PROFIT_TRADER_150K",
    )

    manager = (
        AccountConfigManagerV2(
            config_path=config_path,
        )
    )

    assert (
        manager.active_account
        == "TAKE_PROFIT_TRADER_150K"
    )

    assert (
        manager
        .get_active_account()
        .account_size
        == 150000
    )


def test_switch_persists_active_account(
    tmp_path,
):

    config_path = (
        tmp_path
        / "accounts.json"
    )

    write_config(
        config_path,
        "TAKE_PROFIT_TRADER_50K",
    )

    manager = (
        AccountConfigManagerV2(
            config_path=config_path,
        )
    )

    manager.set_active_account(
        "TAKE_PROFIT_TRADER_150K"
    )

    persisted = json.loads(
        config_path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        persisted["active_account"]
        == "TAKE_PROFIT_TRADER_150K"
    )

    second_manager = (
        AccountConfigManagerV2(
            config_path=config_path,
        )
    )

    assert (
        second_manager.active_account
        == "TAKE_PROFIT_TRADER_150K"
    )


def test_invalid_switch_does_not_modify_config(
    tmp_path,
):

    config_path = (
        tmp_path
        / "accounts.json"
    )

    write_config(
        config_path,
        "TAKE_PROFIT_TRADER_50K",
    )

    manager = (
        AccountConfigManagerV2(
            config_path=config_path,
        )
    )

    before = (
        config_path.read_text(
            encoding="utf-8"
        )
    )

    with pytest.raises(
        ValueError
    ):

        manager.set_active_account(
            "DOES_NOT_EXIST"
        )

    after = (
        config_path.read_text(
            encoding="utf-8"
        )
    )

    assert after == before

    assert (
        manager.active_account
        == "TAKE_PROFIT_TRADER_50K"
    )


def test_registry_can_be_injected(
    tmp_path,
):

    config_path = (
        tmp_path
        / "accounts.json"
    )

    write_config(
        config_path,
        "TAKE_PROFIT_TRADER_50K",
    )

    registry = (
        AccountRegistryV1()
    )

    manager = (
        AccountConfigManagerV2(
            config_path=config_path,
            registry=registry,
        )
    )

    assert (
        manager.registry
        is registry
    )


def test_missing_config_raises(
    tmp_path,
):

    config_path = (
        tmp_path
        / "missing.json"
    )

    with pytest.raises(
        FileNotFoundError
    ):

        AccountConfigManagerV2(
            config_path=config_path,
        )


def test_invalid_active_account_format_raises(
    tmp_path,
):

    config_path = (
        tmp_path
        / "accounts.json"
    )

    config_path.write_text(
        json.dumps(
            {
                "active_account":
                    "",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError
    ):

        AccountConfigManagerV2(
            config_path=config_path,
        )
