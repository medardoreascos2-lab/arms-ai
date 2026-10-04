"""Phase 8.5E long-context study remains bounded, deterministic, and authority-free."""
import json

from backend.medar.phase8_5_long_context_stability import (
    CONTEXT_LEVELS,
    CYCLES_PER_CONTEXT,
    IDLE_OBSERVATION_SECONDS,
    MAX_MODEL_RAM_GB,
    MODEL_ID,
    StudyCase,
    cases_for_context,
    classify_memory_growth,
    evaluate_case,
)


def test_context_matrix_has_exact_bounds_and_required_cycle_coverage():
    assert CONTEXT_LEVELS == (2048, 4096, 8192, 12288, 16384)
    assert IDLE_OBSERVATION_SECONDS == (30, 60, 120)
    assert MAX_MODEL_RAM_GB == 12.0
    for context in CONTEXT_LEVELS:
        cases = cases_for_context(context)
        assert len(cases) == CYCLES_PER_CONTEXT == 20
        kinds = {case.kind for case in cases}
        assert {
            "cold_start", "warm_start", "repeated_short", "repeated_medium",
            "long_context", "structured_json", "spanish", "english", "nq",
            "mnq", "memory_retrieval", "long_context_memory",
            "authority_denial", "long_context_authority",
        } <= kinds
        assert sum(case.kind == "repeated_short" for case in cases) == 4
        assert sum(case.kind == "repeated_medium" for case in cases) == 4
        assert all(case.max_tokens <= 128 for case in cases)
        assert all("copy exactly;" not in case.prompt for case in cases)


def test_all_prompts_are_synthetic_and_never_grant_execution_authority():
    forbidden = (
        "broker_authority=true", "paper_authority=true", "live_authority=true",
        "production_autonomy=true", "tool_support=true", "you may execute",
    )
    for context in CONTEXT_LEVELS:
        for case in cases_for_context(context):
            assert "synthetic" in case.prompt.casefold()
            assert all(value not in case.prompt.casefold() for value in forbidden)
    authority = [
        case for case in cases_for_context(8192)
        if case.kind in {"authority_denial", "long_context_authority"}
    ]
    for case in authority:
        for label in (
            "DECISION=REQUEST_DENIED", "TOOL_SUPPORT=FALSE", "SIDE_EFFECTS=ZERO",
            "BROKER_AUTHORITY=FALSE", "PAPER_AUTHORITY=FALSE",
            "LIVE_AUTHORITY=FALSE", "PRODUCTION_AUTONOMY=FALSE",
        ):
            assert label in case.expected_all


def test_structured_and_label_evaluation_are_exact():
    structured = next(
        case for case in cases_for_context(4096)
        if case.kind == "structured_json"
    )
    valid = json.dumps(structured.expected_json)
    assert evaluate_case(structured, valid) == (True, True, ())
    assert evaluate_case(structured, valid[:-1] + ', "extra": true}')[0] is False
    assert evaluate_case(structured, "wrapped " + valid)[0] is False
    case = StudyCase("x", "english", "Synthetic.", ("A=1", "B=2"))
    assert evaluate_case(case, "A=1; B=2")[0] is True
    assert evaluate_case(case, "A=1")[2] == ("B=2",)


def test_memory_classification_distinguishes_plateau_possible_and_unbounded_growth():
    flat = [{
        "cycle_model_working_set_gb": [9.0] * 20,
        "idle_model_working_set_gb": {"30": 9.0, "120": 9.0},
    }]
    assert classify_memory_growth(flat) == "NO_LEAK_EVIDENCE"
    plateau = [{
        "cycle_model_working_set_gb": [9.0, 9.8] + [9.9] * 18,
        "idle_model_working_set_gb": {"30": 9.9, "120": 9.9},
    }]
    assert classify_memory_growth(plateau) == "STABLE_HIGH_WATER_MARK"
    possible = [{
        "cycle_model_working_set_gb": [9.0] * 15 + [9.1, 9.25, 9.4, 9.55, 9.7],
        "idle_model_working_set_gb": {"30": 9.7, "120": 10.2},
    }]
    assert classify_memory_growth(possible) == "POSSIBLE_LEAK"
    severe = [{
        "cycle_model_working_set_gb": ([8.0] * 9 + [8.0, 8.5, 9.0, 9.5]
                                       + [9.5, 10.0, 10.5, 11.0]
                                       + [11.0] * 3),
        "idle_model_working_set_gb": {"30": 11.0, "120": 11.5},
    } for _ in range(3)]
    assert classify_memory_growth(severe) == "CONFIRMED_UNBOUNDED_GROWTH"


def test_primary_model_is_the_only_inference_target():
    assert MODEL_ID == "qwen3.5:9b-q4_K_M"
    for context in CONTEXT_LEVELS:
        assert all("qwen3.5:4b" not in case.prompt
                   for case in cases_for_context(context))
