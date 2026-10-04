"""R81A deterministic intent classification tests."""

from backend.medar.intent import RuleAssistedIntentClassifier
from backend.medar.request import CognitiveDomain


def test_classifier_covers_initial_domains_without_external_model():
    classifier = RuleAssistedIntentClassifier()
    examples = {
        "hello, explain this": CognitiveDomain.GENERAL,
        "research latest sources": CognitiveDomain.WEB_RESEARCH,
        "fix code bug": CognitiveDomain.CODING,
        "analyze a stock": CognitiveDomain.FINANCIAL,
        "analyze NQ futures": CognitiveDomain.TRADING,
        "scan crypto prices": CognitiveDomain.CRYPTO,
        "review my portfolio": CognitiveDomain.PORTFOLIO,
        "business operations": CognitiveDomain.BUSINESS,
        "marketing campaign": CognitiveDomain.MARKETING,
        "career life decision": CognitiveDomain.LIFE_ADVICE,
        "summarize Rosita notes": CognitiveDomain.ROSITA,
        "perform a computer action": CognitiveDomain.COMPUTER_ACTION,
        "read a document": CognitiveDomain.DOCUMENT,
        "create an image": CognitiveDomain.IMAGE,
        "transcribe voice audio": CognitiveDomain.VOICE,
    }

    for text, expected in examples.items():
        result = classifier.classify(text)
        assert expected in result.domains
        assert result.external_model_used is False


def test_multi_domain_request_is_preserved_as_ambiguous():
    result = RuleAssistedIntentClassifier().classify(
        "Research latest stock risk and create a marketing report"
    )

    assert result.domains == (
        CognitiveDomain.FINANCIAL,
        CognitiveDomain.WEB_RESEARCH,
        CognitiveDomain.MARKETING,
    )
    assert result.ambiguous is True


def test_unmatched_request_stays_unknown():
    result = RuleAssistedIntentClassifier().classify("florp zibble")

    assert result.primary_domain is CognitiveDomain.UNKNOWN
    assert result.confidence == 0.0
    assert result.ambiguous is True
