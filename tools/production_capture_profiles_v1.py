"""Closed diagnostic resource profiles; never clock bounds or admission policy."""
from dataclasses import asdict, dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class Profile:
    profile_id: str
    purpose: str
    minimum_duration_seconds: int
    minimum_closed: int
    hard_maximum_duration_seconds: int
    maximum_native_records: int
    maximum_native_bytes: int
    maximum_receipt_records: int
    maximum_receipt_bytes: int
    maximum_clock_attempts: int
    maximum_clock_bytes: int
    profile_version: int = 1
    activation_timeout_seconds: int = 600
    acknowledgement_seconds: int = 120
    closure_seconds: int = 60
    final_clock_seconds: int = 120
    probe_cadence_seconds: int = 30
    maximum_native_files: int = 5
    maximum_run_files: int = 32
    maximum_frame_bytes: int = 65536
    read_chunk_bytes: int = 65536
    maximum_queue_records: int = 32

    def manifest(self):
        return asdict(self)


PROFILES = MappingProxyType({
    'LONG_A': Profile('LONG_A', 'LIQUID_PERIOD', 3600, 50, 7200,
                      16384, 16_000_000, 16384, 16_000_000, 1024, 8_000_000),
    'LONG_B': Profile('LONG_B', 'QUIET_SPARSE_PERIOD', 3600, 50, 7200,
                      16384, 16_000_000, 16384, 16_000_000, 1024, 8_000_000),
    'LONG_C': Profile('LONG_C', 'EXTENDED_MULTI_CONDITION', 21600, 300, 28800,
                      65536, 64_000_000, 65536, 64_000_000, 4096, 32_000_000),
})


def profile(value):
    """Only a named, immutable reviewed profile; no numeric CLI overrides."""
    if type(value) is not str or value not in PROFILES:
        raise ValueError('PROFILE_NOT_ALLOWLISTED')
    return PROFILES[value]
