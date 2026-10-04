"""R92A MEDAR computer permission level tests."""

from datetime import datetime, timezone

import pytest

from backend.medar.computer_permissions import ComputerPermissionGrant, ComputerPermissionLevel


def test_permission_levels_are_ordered_and_exact():
    assert tuple(item.name for item in ComputerPermissionLevel) == (
        "LEVEL_0_READ_ONLY", "LEVEL_1_SAFE_ACTIONS", "LEVEL_2_FILE_EDITS",
        "LEVEL_3_TERMINAL", "LEVEL_4_SENSITIVE_CONFIRM", "LEVEL_5_TEMP_ADMIN",
    )
    assert ComputerPermissionLevel.LEVEL_0_READ_ONLY < ComputerPermissionLevel.LEVEL_5_TEMP_ADMIN


def test_phase7_grant_cannot_enable_real_os_control():
    with pytest.raises(ValueError, match="real OS control"):
        ComputerPermissionGrant("user", ComputerPermissionLevel.LEVEL_0_READ_ONLY, real_os_control=True)


def test_temp_admin_schema_requires_expiry_but_still_has_no_os_authority():
    with pytest.raises(ValueError, match="expiry"):
        ComputerPermissionGrant("user", ComputerPermissionLevel.LEVEL_5_TEMP_ADMIN)
    grant = ComputerPermissionGrant(
        "user", ComputerPermissionLevel.LEVEL_5_TEMP_ADMIN, datetime.now(timezone.utc),
    )
    assert grant.real_os_control is False
