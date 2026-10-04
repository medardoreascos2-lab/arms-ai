"""Canonical multimodal request derived from a trusted Product session."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from types import MappingProxyType
from typing import Mapping

from backend.product.customer_session import TrustedCustomerSession
from .domain import Modality

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _safe(value: str, name: str) -> None:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ValueError(f"{name} must be a safe opaque identifier")


@dataclass(frozen=True, init=False)
class MultimodalRequest:
    request_id: str
    session_id: str
    user_id: str
    tenant_id: str
    modality: Modality
    content_reference: str
    mime_type: str
    created_at: datetime
    consent_context: Mapping[str, str]
    permission_context: Mapping[str, str]
    source_device: str
    metadata: Mapping[str, str]
    identity_source: str

    def __init__(
        self, *, session: TrustedCustomerSession, request_id: str,
        modality: Modality, content_reference: str, mime_type: str,
        created_at: datetime, consent_context: Mapping[str, str],
        permission_context: Mapping[str, str], source_device: str,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(session, TrustedCustomerSession):
            raise PermissionError("trusted Product session required")
        for value, name in ((request_id, "request_id"), (content_reference, "content_reference"),
                            (source_device, "source_device")):
            _safe(value, name)
        if not isinstance(modality, Modality):
            raise ValueError("canonical modality required")
        if not isinstance(mime_type, str) or not mime_type or len(mime_type) > 127:
            raise ValueError("valid mime_type required")
        if created_at.tzinfo is None or created_at.utcoffset() != timedelta(0):
            raise ValueError("created_at must be UTC")
        contexts = {
            "consent_context": consent_context,
            "permission_context": permission_context,
            "metadata": metadata or {},
        }
        for name, value in contexts.items():
            if not isinstance(value, Mapping) or any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()
            ):
                raise ValueError(f"{name} must contain text pairs")
        values = {
            "request_id": request_id, "session_id": session.session_id,
            "user_id": session.user_id, "tenant_id": session.tenant_id,
            "modality": modality, "content_reference": content_reference,
            "mime_type": mime_type, "created_at": created_at,
            "source_device": source_device,
            "identity_source": "TRUSTED_PRODUCT_SESSION",
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)
        for name, value in contexts.items():
            object.__setattr__(self, name, MappingProxyType(dict(value)))
