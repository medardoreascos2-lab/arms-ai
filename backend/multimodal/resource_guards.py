"""Fail-closed admission control for bounded multimodal workloads."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock


class ResourceCode(str, Enum):
    ALLOWED = "ALLOWED"
    AUDIO_DURATION_LIMIT = "AUDIO_DURATION_LIMIT"
    IMAGE_SIZE_LIMIT = "IMAGE_SIZE_LIMIT"
    CAMERA_FRAME_RATE_LIMIT = "CAMERA_FRAME_RATE_LIMIT"
    MEMORY_LIMIT = "MEMORY_LIMIT"
    QUEUED = "QUEUED"
    QUEUE_LIMIT = "QUEUE_LIMIT"


@dataclass(frozen=True)
class ResourceLimits:
    max_audio_duration_seconds: float = 120.0
    max_image_size_bytes: int = 15_000_000
    max_camera_frames_per_second: float = 5.0
    max_concurrent_jobs: int = 2
    max_memory_bytes_per_job: int = 256_000_000
    max_queue_depth: int = 8

    def __post_init__(self) -> None:
        values = (
            self.max_audio_duration_seconds,
            self.max_image_size_bytes,
            self.max_camera_frames_per_second,
            self.max_concurrent_jobs,
            self.max_memory_bytes_per_job,
        )
        if any(value <= 0 for value in values) or self.max_queue_depth < 0:
            raise ValueError("resource limits must be positive; queue depth may be zero")


@dataclass(frozen=True)
class ResourceRequest:
    audio_duration_seconds: float = 0.0
    image_size_bytes: int = 0
    camera_frames_per_second: float = 0.0
    estimated_memory_bytes: int = 1


@dataclass(frozen=True)
class ResourceDecision:
    allowed: bool
    code: ResourceCode


class MultimodalResourceGuard:
    """Tracks bounded admission without executing, capturing, or storing media."""

    def __init__(self, limits: ResourceLimits = ResourceLimits()) -> None:
        self._limits = limits
        self._active_jobs = 0
        self._queued_jobs = 0
        self._lock = Lock()

    @property
    def active_jobs(self) -> int:
        with self._lock:
            return self._active_jobs

    @property
    def queued_jobs(self) -> int:
        with self._lock:
            return self._queued_jobs

    def validate(self, request: ResourceRequest) -> ResourceDecision:
        if request.audio_duration_seconds < 0 or request.audio_duration_seconds > self._limits.max_audio_duration_seconds:
            return ResourceDecision(False, ResourceCode.AUDIO_DURATION_LIMIT)
        if request.image_size_bytes < 0 or request.image_size_bytes > self._limits.max_image_size_bytes:
            return ResourceDecision(False, ResourceCode.IMAGE_SIZE_LIMIT)
        if request.camera_frames_per_second < 0 or request.camera_frames_per_second > self._limits.max_camera_frames_per_second:
            return ResourceDecision(False, ResourceCode.CAMERA_FRAME_RATE_LIMIT)
        if request.estimated_memory_bytes <= 0 or request.estimated_memory_bytes > self._limits.max_memory_bytes_per_job:
            return ResourceDecision(False, ResourceCode.MEMORY_LIMIT)
        return ResourceDecision(True, ResourceCode.ALLOWED)

    def try_acquire(self, request: ResourceRequest) -> ResourceDecision:
        validation = self.validate(request)
        if not validation.allowed:
            return validation
        with self._lock:
            if self._active_jobs < self._limits.max_concurrent_jobs:
                self._active_jobs += 1
                return ResourceDecision(True, ResourceCode.ALLOWED)
            if self._queued_jobs < self._limits.max_queue_depth:
                self._queued_jobs += 1
                return ResourceDecision(False, ResourceCode.QUEUED)
            return ResourceDecision(False, ResourceCode.QUEUE_LIMIT)

    def release(self) -> None:
        with self._lock:
            if self._active_jobs <= 0:
                raise RuntimeError("no active multimodal job to release")
            self._active_jobs -= 1

    def discard_queued(self) -> None:
        with self._lock:
            if self._queued_jobs <= 0:
                raise RuntimeError("no queued multimodal job to discard")
            self._queued_jobs -= 1