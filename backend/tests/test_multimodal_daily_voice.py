from datetime import datetime,timezone

from backend.multimodal.daily_voice import present_daily_voice
from backend.product.financial_models import DailyFinancialSnapshot,FinancialProjectionStatus,FinancialReadStatus,FinancialSourceStatus,ProductFinancialDegradedResponse,ProductFinancialProvenance

NOW=datetime(2026,10,4,12,tzinfo=timezone.utc)


def test_voice_script_uses_only_available_daily_projection_text():
    source=ProductFinancialProvenance(source_id="synthetic-daily",source_label="Synthetic",classification="SYNTHETIC",observed_at=NOW,freshness_seconds=0,source_status=FinancialSourceStatus.SYNTHETIC)
    value=DailyFinancialSnapshot(status=FinancialProjectionStatus.READY,provenance=source,headline="Synthetic morning view.",source_status=FinancialSourceStatus.SYNTHETIC)
    result=present_daily_voice(value)
    assert result.text == result.voice_script == "Synthetic morning view."
    assert result.synthetic and result.source_id == "synthetic-daily"


def test_unknown_daily_projection_stays_unknown_without_voice_script():
    result=present_daily_voice(ProductFinancialDegradedResponse(status=FinancialReadStatus.FINANCIAL_DATA_UNAVAILABLE))
    assert result.status=="FINANCIAL_DATA_UNAVAILABLE" and result.text is None and result.voice_script is None
