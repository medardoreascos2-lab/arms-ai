"""Text and voice-script presentation derived only from Daily Intelligence data."""

from __future__ import annotations

from dataclasses import dataclass

from backend.product.financial_models import DailyFinancialSnapshot, ProductFinancialDegradedResponse


@dataclass(frozen=True)
class DailyVoicePresentation:
    status: str
    text: str | None
    voice_script: str | None
    source_id: str | None
    synthetic: bool


def present_daily_voice(value: DailyFinancialSnapshot | ProductFinancialDegradedResponse) -> DailyVoicePresentation:
    if isinstance(value, ProductFinancialDegradedResponse):
        return DailyVoicePresentation(status=value.status.value,text=None,voice_script=None,source_id=None,synthetic=False)
    parts=[value.headline] if value.headline else []
    if value.trading and value.trading.coach_summary: parts.append(value.trading.coach_summary)
    if value.coach and value.coach.summary: parts.append(value.coach.summary)
    parts.extend(alert.title for alert in value.alerts)
    text=" ".join(parts).strip() or None
    classification=value.provenance.classification
    return DailyVoicePresentation(status=value.status.value,text=text,voice_script=text,source_id=value.provenance.source_id,synthetic=classification in {"SYNTHETIC","LOCAL_TEST_ONLY","NOT_REAL_ACCOUNT_DATA"})
