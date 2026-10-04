"""Deterministic, local-only MEDAR intent classifier."""

from dataclasses import dataclass
import re
from typing import Protocol

from backend.medar.request import CognitiveDomain, normalize_user_input


@dataclass(frozen=True)
class IntentClassification:
    primary_domain: CognitiveDomain
    domains: tuple[CognitiveDomain, ...]
    confidence: float
    matched_terms: tuple[str, ...]
    ambiguous: bool
    external_model_used: bool = False


class IntentClassifier(Protocol):
    def classify(self, text: str) -> IntentClassification: ...


_RULES: tuple[tuple[CognitiveDomain, tuple[str, ...]], ...] = (
    (CognitiveDomain.TRADING, (" nq ", " mnq ", "futures", "trading")),
    (CognitiveDomain.CRYPTO, ("crypto", "bitcoin", "ethereum", "arbitrage")),
    (CognitiveDomain.PORTFOLIO, ("portfolio", "allocation", "rebalance")),
    (CognitiveDomain.FINANCIAL, ("stock", " etf", "fundamental", "finance", "market risk")),
    (CognitiveDomain.WEB_RESEARCH, ("research", "latest", "web", "source", "news")),
    (CognitiveDomain.CODING, ("code", "repository", "bug", "test", "program")),
    (CognitiveDomain.MARKETING, ("marketing", "seo", "campaign", "funnel", "branding")),
    (CognitiveDomain.BUSINESS, ("business", "sales", "kpi", "operations", "company")),
    (CognitiveDomain.LIFE_ADVICE, ("career", "life decision", "habit", "personal goal")),
    (CognitiveDomain.ROSITA, ("rosita", "family remedy", "traditional practice")),
    (CognitiveDomain.COMPUTER_ACTION, ("computer", "terminal", "install", "delete file", "browser action")),
    (CognitiveDomain.DOCUMENT, ("document", "pdf", "spreadsheet", "presentation")),
    (CognitiveDomain.IMAGE, ("image", "illustration", "photo", "diagram")),
    (CognitiveDomain.VOICE, ("voice", "audio", "speech")),
)


class RuleAssistedIntentClassifier:
    """Classify requests without network access or an external model."""

    def classify(self, text: str) -> IntentClassification:
        normalized = f" {normalize_user_input(text).lower()} "
        matches: list[tuple[CognitiveDomain, str]] = []
        for domain, terms in _RULES:
            for term in terms:
                candidate = term.strip()
                if re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", normalized):
                    matches.append((domain, term.strip()))
                    break
        domains = tuple(dict.fromkeys(domain for domain, _ in matches))
        if not domains:
            general_terms = ("hello", "explain", "summarize", "question")
            if any(term in normalized for term in general_terms):
                return IntentClassification(CognitiveDomain.GENERAL, (CognitiveDomain.GENERAL,), 0.75, (), False)
            return IntentClassification(CognitiveDomain.UNKNOWN, (CognitiveDomain.UNKNOWN,), 0.0, (), True)
        confidence = min(0.98, 0.72 + (0.06 * len(matches)))
        return IntentClassification(
            primary_domain=domains[0],
            domains=domains,
            confidence=confidence,
            matched_terms=tuple(term for _, term in matches),
            ambiguous=len(domains) > 1,
        )
