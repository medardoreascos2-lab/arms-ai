import inspect
from backend.multimodal.document_seam import DocumentAnalysisProvider,DocumentAnalysisRequest,DocumentKind

def test_document_seam_requires_existing_ingestion_reference_and_page_scope():
 request=DocumentAnalysisRequest("r","ingestion:1","s","u","t",DocumentKind.PDF,(1,2));assert request.existing_ingestion_reference=="ingestion:1"

def test_document_seam_does_not_duplicate_byte_upload_or_ingestion():
 source=inspect.getsource(DocumentAnalysisProvider)
 assert "analyze_existing" in source
 assert all(term not in source for term in ("upload","bytes","save_file","ingest"))
