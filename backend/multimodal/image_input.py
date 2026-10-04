"""Validated image metadata contract; raw image bytes stay provider-owned."""

from dataclasses import dataclass

from .consent import ConsentState
from .domain import Modality
from .request import MultimodalRequest

_ALLOWED=frozenset({"image/jpeg","image/png","image/webp"})


@dataclass(frozen=True)
class ImageInput:
    content_reference: str
    owner_session_id: str
    owner_user_id: str
    owner_tenant_id: str
    mime_type: str
    size_bytes: int
    width: int
    height: int
    consent_reference: str
    consent_state: ConsentState


@dataclass(frozen=True)
class ImageLimits:
    max_size_bytes: int=15_000_000
    max_dimension: int=8192


def validate_image_input(image: ImageInput,request: MultimodalRequest,limits: ImageLimits=ImageLimits()) -> None:
    if request.modality != Modality.IMAGE: raise ValueError("image request required")
    if image.content_reference != request.content_reference: raise PermissionError("image reference mismatch")
    if (image.owner_session_id,image.owner_user_id,image.owner_tenant_id)!=(request.session_id,request.user_id,request.tenant_id): raise PermissionError("image ownership mismatch")
    if image.consent_state != ConsentState.GRANTED_SESSION or not image.consent_reference: raise PermissionError("explicit image consent required")
    if image.mime_type not in _ALLOWED or image.mime_type != request.mime_type: raise ValueError("unsupported or spoofed image mime")
    if image.size_bytes <= 0 or image.size_bytes > limits.max_size_bytes: raise ValueError("image size outside configured limit")
    if image.width <= 0 or image.height <= 0 or max(image.width,image.height)>limits.max_dimension: raise ValueError("image dimensions outside configured limit")
