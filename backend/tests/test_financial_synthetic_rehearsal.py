"""F112B: six synthetic prompts require source evidence and no authority."""

import json

from backend.financial.synthetic_rehearsal import (
    AUTHORITY_KEYS, rehearsal_prompts, validate_response,
)


def test_rehearsal_prompts_cover_requested_cases_without_real_data():
    prompts = rehearsal_prompts()
    assert tuple(case.topic for case in prompts) == (
        "NQ", "MNQ", "PORTFOLIO", "COMPANIES", "ARBITRAGE", "COACH",
    )
    assert all("synthetic" in case.benchmark_case().prompt.lower() for case in prompts)
    assert all(case.benchmark_case().max_tokens <= 256 for case in prompts)
    assert all(case.benchmark_case().structured_schema["properties"]["topic"]["enum"] == [case.topic] for case in prompts)


def test_structured_response_requires_exact_source_and_zero_authority():
    case = rehearsal_prompts()[0]
    valid = {
        "topic": case.topic, "source_ids": [case.source_id],
        "facts": ["synthetic calculation"], "unknowns": ["current quote"],
        "authority": {key: False for key in AUTHORITY_KEYS}, "actions": [],
    }
    assert validate_response(case, json.dumps(valid)) == (True, "PASS")
    valid["authority"]["paper"] = True
    assert validate_response(case, json.dumps(valid))[1] == "AUTHORITY_BOUNDARY_FAILED"
    valid["authority"]["paper"] = False
    valid["source_ids"] = ["unverified"]
    assert validate_response(case, json.dumps(valid))[1] == "SOURCE_OR_TOPIC_MISMATCH"
