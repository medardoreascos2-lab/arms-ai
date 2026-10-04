"""Multimodal document seam over existing ingestion references."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class DocumentKind(str,Enum):
    PDF="PDF";SLIDES="SLIDES";DOCUMENT="DOCUMENT";IMAGE_DOCUMENT="IMAGE_DOCUMENT"


@dataclass(frozen=True)
class DocumentAnalysisRequest:
    request_id: str
    existing_ingestion_reference: str
    owner_session_id: str
    owner_user_id: str
    owner_tenant_id: str
    kind: DocumentKind
    page_numbers: tuple[int,...]=()
    def __post_init__(self):
        if not self.existing_ingestion_reference: raise ValueError("existing ingestion reference required")
        if any(page<1 for page in self.page_numbers): raise ValueError("page numbers must be positive")


@dataclass(frozen=True)
class DocumentAnalysisResult:
    request_id: str
    observations: tuple[str,...]
    provider: str
    synthetic: bool
    source_reference: str


class DocumentAnalysisProvider(Protocol):
    def analyze_existing(self,request: DocumentAnalysisRequest)->DocumentAnalysisResult: ...
