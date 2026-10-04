"""Multi-source research synthesis with lossless disagreement reporting."""

from dataclasses import dataclass

from backend.medar.web_research import WebSource


@dataclass(frozen=True)
class ResearchFinding:
    source_id: str
    claim: str

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.claim.strip():
            raise ValueError("research finding source and claim are required")


@dataclass(frozen=True)
class ResearchSynthesis:
    findings: tuple[ResearchFinding, ...]
    sources: tuple[WebSource, ...]
    consensus_claims: tuple[str, ...]
    disagreements: tuple[str, ...]
    sufficient: bool


def synthesize_research(
    findings: tuple[ResearchFinding, ...],
    sources: tuple[WebSource, ...],
) -> ResearchSynthesis:
    source_ids = {source.source_id for source in sources}
    if any(finding.source_id not in source_ids for finding in findings):
        raise ValueError("every finding must reference a provided source")
    claims: dict[str, list[str]] = {}
    for finding in findings:
        claims.setdefault(finding.claim.strip(), []).append(finding.source_id)
    consensus = tuple(claim for claim, ids in claims.items() if len(set(ids)) > 1)
    disagreements = tuple(claims) if len(claims) > 1 else ()
    return ResearchSynthesis(findings, sources, consensus, disagreements, bool(findings and sources))
