"""R86B MEDAR scoped memory retrieval contract tests."""

from datetime import datetime, timezone

import pytest

from backend.medar.memory_read import MemoryQuery, MemoryReadResult
from backend.medar.memory_types import MemoryDomain, MemorySensitivity


def _query():
    return MemoryQuery(
        "tenant-1", "user-1", "preferences", (MemoryDomain.PERSONAL,),
        (MemorySensitivity.INTERNAL,), 5,
    )


def _result(**overrides):
    values = dict(
        memory_id="memory-1", tenant_id="tenant-1", user_id="user-1",
        domain=MemoryDomain.PERSONAL, sensitivity=MemorySensitivity.INTERNAL,
        content="Prefers concise reports", source_provenance="conversation:req-1",
        confidence=0.9, recorded_at=datetime.now(timezone.utc),
    )
    values.update(overrides)
    return MemoryReadResult(**values)


def test_result_visibility_requires_exact_tenant_user_domain_and_sensitivity_scope():
    assert _result().is_visible_to(_query()) is True
    assert _result(user_id="user-2").is_visible_to(_query()) is False
    assert _result(tenant_id="tenant-2").is_visible_to(_query()) is False


def test_query_requires_explicit_scope():
    with pytest.raises(ValueError, match="domain"):
        MemoryQuery("tenant", "user", "query", (), (MemorySensitivity.INTERNAL,))


def test_result_requires_confidence_and_timezone_aware_timestamp():
    with pytest.raises(ValueError, match="confidence"):
        _result(confidence=1.1)
    with pytest.raises(ValueError, match="timezone-aware"):
        _result(recorded_at=datetime.now())


def test_sensitivity_scope_is_enforced_by_visibility_check():
    assert _result(sensitivity=MemorySensitivity.RESTRICTED).is_visible_to(_query()) is False
