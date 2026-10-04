"""R111B MNQ research cannot be silently merged with NQ."""

from dataclasses import replace

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain
from backend.medar.futures_research_memory import FuturesInstrument, FuturesResearchSessionIndex
from backend.tests.test_phase8_nq_research_memory import _record


SCOPE = dict(tenant_id="tenant-a", owner_id="owner-a", session_id="session-a")


def test_mnq_uses_distinct_domain_and_explicit_instrument_bucket():
    index = FuturesResearchSessionIndex(**SCOPE)
    nq = _record()
    mnq = replace(nq, instrument=FuturesInstrument.MNQ)
    assert nq.domain is DurableMemoryDomain.NQ
    assert mnq.domain is DurableMemoryDomain.MNQ
    index.add(nq)
    index.add(mnq)
    assert index.list_for(FuturesInstrument.NQ, **SCOPE) == (nq,)
    assert index.list_for(FuturesInstrument.MNQ, **SCOPE) == (mnq,)
    with pytest.raises(TypeError):
        index.list_for("NQ", **SCOPE)


def test_mnq_index_rejects_cross_scope_duplicate_or_implicit_merge():
    index = FuturesResearchSessionIndex(**SCOPE, max_per_instrument=1)
    mnq = replace(_record(), instrument=FuturesInstrument.MNQ)
    with pytest.raises(PermissionError):
        index.add(replace(mnq, owner_id="other"))
    index.add(mnq)
    with pytest.raises(ValueError):
        index.add(mnq)
    with pytest.raises(PermissionError):
        index.list_for(FuturesInstrument.MNQ, tenant_id="tenant-b", owner_id="owner-a", session_id="session-a")
    assert index.list_for(FuturesInstrument.NQ, **SCOPE) == ()
