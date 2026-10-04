"""Evidence-bound MEDAR response synthesis."""

from hashlib import sha256
import json

from backend.medar.evidence import EvidenceBundle
from backend.medar.response import CognitiveResponse, EvidenceReference, ResponseStatus


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def synthesize_response(
    *,
    response_id: str,
    request_id: str,
    answer: str,
    evidence: EvidenceBundle,
) -> CognitiveResponse:
    if not evidence.is_sufficient:
        return CognitiveResponse(
            response_id=response_id,
            request_id=request_id,
            status=ResponseStatus.PARTIAL,
            answer="Insufficient evidence to provide a supported answer.",
            confidence=0.0,
            reasoning_summary="No usable evidence was available.",
            warnings=tuple(dict.fromkeys(evidence.warnings + ("INSUFFICIENT_EVIDENCE",))),
            follow_up_needed=True,
        )
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("a supported answer must be non-empty")

    tool_evidence = tuple(
        EvidenceReference(
            f"tool:{item.call_id}",
            f"{item.tool_id}:{item.status.value}",
            _digest(item.output),
        )
        for item in evidence.tool_results
    )
    memory_evidence = tuple(
        EvidenceReference(
            f"memory:{item.memory_id}",
            f"{item.domain.value} memory",
            _digest(item.content),
        )
        for item in evidence.memory_results
    )
    confidences = [item.confidence for item in evidence.agent_outputs]
    confidences.extend(item.confidence for item in evidence.memory_results)
    confidence = min(confidences) if confidences else 0.5
    return CognitiveResponse(
        response_id=response_id,
        request_id=request_id,
        status=ResponseStatus.SUCCESS,
        answer=answer.strip(),
        confidence=confidence,
        reasoning_summary=(
            f"Synthesized from {evidence.usable_evidence_count} usable evidence item(s)."
        ),
        sources=evidence.sources,
        tool_evidence=tool_evidence,
        memory_evidence=memory_evidence,
        warnings=evidence.warnings,
    )
