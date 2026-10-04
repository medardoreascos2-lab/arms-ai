"""Scoped voice presentation preferences; no biometric voice cloning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VoiceVerbosity(str, Enum):
    CONCISE = "CONCISE"
    STANDARD = "STANDARD"
    DETAILED = "DETAILED"


@dataclass(frozen=True)
class VoicePreferences:
    tenant_id: str
    user_id: str
    voice_id: str
    language: str
    speaking_rate: float = 1.0
    verbosity: VoiceVerbosity = VoiceVerbosity.STANDARD
    auto_speak: bool = False
    quiet_hours_start: int = 2200
    quiet_hours_end: int = 700
    private_mode: bool = True
    biometric_cloning_allowed: bool = False

    def __post_init__(self) -> None:
        if not all((self.tenant_id, self.user_id, self.voice_id, self.language)):
            raise ValueError("scoped voice preference identifiers required")
        if not 0.5 <= self.speaking_rate <= 2.0:
            raise ValueError("speaking rate outside safe presentation range")
        if not 0 <= self.quiet_hours_start <= 2359 or not 0 <= self.quiet_hours_end <= 2359:
            raise ValueError("quiet hours must be HHMM values")
        if self.biometric_cloning_allowed:
            raise ValueError("biometric voice cloning is unavailable")


class VoicePreferenceStore:
    def __init__(self) -> None:
        self._values: dict[tuple[str,str], VoicePreferences] = {}
    def save(self, value: VoicePreferences) -> None:
        self._values[(value.tenant_id,value.user_id)] = value
    def get(self, tenant_id: str, user_id: str) -> VoicePreferences | None:
        return self._values.get((tenant_id,user_id))
