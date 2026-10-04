"""Future computer action permission levels; Phase 7 grants no OS control."""

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum


class ComputerPermissionLevel(IntEnum):
    LEVEL_0_READ_ONLY = 0
    LEVEL_1_SAFE_ACTIONS = 1
    LEVEL_2_FILE_EDITS = 2
    LEVEL_3_TERMINAL = 3
    LEVEL_4_SENSITIVE_CONFIRM = 4
    LEVEL_5_TEMP_ADMIN = 5


@dataclass(frozen=True)
class ComputerPermissionGrant:
    user_id: str
    max_level: ComputerPermissionLevel
    expires_at: datetime | None = None
    real_os_control: bool = False

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("user_id is required")
        if not isinstance(self.max_level, ComputerPermissionLevel):
            raise TypeError("max_level must be ComputerPermissionLevel")
        if self.real_os_control:
            raise ValueError("Phase 7 cannot grant real OS control")
        if self.max_level is ComputerPermissionLevel.LEVEL_5_TEMP_ADMIN and self.expires_at is None:
            raise ValueError("temporary admin permission requires expiry")
