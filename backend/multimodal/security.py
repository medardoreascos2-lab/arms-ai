"""Fail-closed security checks applied before multimodal capture or provider use."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import PurePath
import re
from typing import Callable, Mapping, TypeVar


_SAFE_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_. -]{0,127}$")
_SAFE_METADATA = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_ALLOWED_METADATA = frozenset({"capture_id", "source_device", "provider_reference"})
T = TypeVar("T")


class SubmissionKind(str, Enum):
    AUDIO = "AUDIO"
    IMAGE = "IMAGE"
    DOCUMENT = "DOCUMENT"
    CAMERA_START = "CAMERA_START"
    NOTIFICATION = "NOTIFICATION"


@dataclass(frozen=True)
class SecureMediaSubmission:
    kind: SubmissionKind
    content_reference: str
    filename: str
    declared_mime_type: str
    detected_mime_type: str
    size_bytes: int
    session_id: str
    user_id: str
    tenant_id: str
    created_at: datetime
    consent_granted: bool
    explicit_user_action: bool = False
    trusted_origin: bool = False
    metadata: Mapping[str, str] = field(default_factory=dict)


class MultimodalInputBoundary:
    def __init__(self, *, allowed_mime_types: frozenset[str], max_size_bytes: int,
                 max_age: timedelta = timedelta(minutes=5)) -> None:
        if not allowed_mime_types or max_size_bytes <= 0 or max_age <= timedelta(0):
            raise ValueError("valid security boundary configuration required")
        self._allowed_mime_types = allowed_mime_types
        self._max_size_bytes = max_size_bytes
        self._max_age = max_age

    def validate(self, submission: SecureMediaSubmission, *, session_id: str,
                 user_id: str, tenant_id: str, at: datetime) -> None:
        if at.tzinfo is None or submission.created_at.tzinfo is None:
            raise ValueError("UTC timestamps required")
        if PurePath(submission.filename).name != submission.filename or not _SAFE_FILE.fullmatch(submission.filename):
            raise ValueError("unsafe media filename")
        if (submission.declared_mime_type != submission.detected_mime_type
                or submission.declared_mime_type not in self._allowed_mime_types):
            raise ValueError("media mime mismatch")
        if submission.size_bytes <= 0 or submission.size_bytes > self._max_size_bytes:
            raise ValueError("media size outside configured limit")
        if (submission.session_id, submission.user_id, submission.tenant_id) != (
            session_id, user_id, tenant_id,
        ):
            raise PermissionError("media scope mismatch")
        age = at - submission.created_at
        if age < timedelta(0) or age > self._max_age:
            raise PermissionError("stale or future media submission")
        if not submission.consent_granted:
            raise PermissionError("explicit modality consent required")
        if submission.kind is SubmissionKind.CAMERA_START and not submission.explicit_user_action:
            raise PermissionError("explicit camera start action required")
        if submission.kind is SubmissionKind.NOTIFICATION and not submission.trusted_origin:
            raise PermissionError("trusted notification origin required")
        if any(
            key not in _ALLOWED_METADATA
            or not isinstance(value, str)
            or not _SAFE_METADATA.fullmatch(value)
            for key, value in submission.metadata.items()
        ):
            raise ValueError("unsafe or unsupported media metadata")

    def execute(self, submission: SecureMediaSubmission, *, session_id: str,
                user_id: str, tenant_id: str, at: datetime,
                operation: Callable[[SecureMediaSubmission], T]) -> T:
        self.validate(submission, session_id=session_id, user_id=user_id, tenant_id=tenant_id, at=at)
        return operation(submission)