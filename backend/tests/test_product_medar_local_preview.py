"""Synthetic Product MEDAR preview invokes the canonical core on loopback."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.api.product_medar_local_test import ProductMedarLocalTestConfig
from tools.run_product_medar_local_test import build_local_test_app


def test_local_preview_uses_only_synthetic_session_and_canonical_core():
    app = build_local_test_app(
        ProductMedarLocalTestConfig(enabled=True, environment="TEST"),
        at=datetime(2026, 10, 4, 12, tzinfo=timezone.utc),
    )
    client = TestClient(app, client=("127.0.0.1", 50000))
    response = client.post(
        "/product/medar/conversations",
        json={
            "request_id": "request-1",
            "conversation_id": "conversation-1",
            "message": "Summarize this request.",
        },
        headers={"X-ARMS-Local-Test-Session": "synthetic-session-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PARTIAL"
    assert body["answer"]
    assert body["memory_evidence"] == []
    assert body["tool_evidence"] == []
    assert body["action_proposals"] == []
