"""R122C model output cannot smuggle authority through key variants."""

import json

import pytest

from backend.medar.model_output_validation import validate_model_output
from backend.medar.model_provider import ModelInvocation, ModelKind, ModelResult


def _result(output):
    return ModelResult("inv-1", "local-model", output, "No private reasoning", 1, 1, (), False)


def _invocation(schema=None):
    return ModelInvocation("inv-1", "local-model", ModelKind.LOCAL_LLM, "safe prompt", schema)


@pytest.mark.parametrize("key", (
    "execution_authority", "Execution-Authority", "LIVE AUTHORITY", "paper.authority",
    "tradingAuthority", "tool_calls", "shell-command", "production autonomy",
    "secret_access", "portfolio_mutation_authority", "model_update_authority",
))
def test_authority_key_variants_are_rejected_at_any_depth(key):
    normalized_attack = key
    if key == "tradingAuthority":
        normalized_attack = "trading-authority"
    output = json.dumps({"answer": "safe", "nested": [{normalized_attack: True}]})
    with pytest.raises(ValueError, match="authority or action"):
        validate_model_output(_invocation(), _result(output))


def test_validated_output_remains_data_only_with_empty_authorized_actions():
    output = validate_model_output(_invocation({"answer": "string"}), _result('{"answer":"advisory text"}'))
    assert output.structured == {"answer": "advisory text"}
    assert output.authorized_actions == ()
    assert not output.result.external_call_performed
