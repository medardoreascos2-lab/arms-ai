"""R75B full external staging configuration render tests."""

from pathlib import Path

import pytest

from backend.phase6.config_render import (
    ConfigurationRenderError,
    render_external_staging_configuration,
)
from backend.phase6.provider_emulator import LocalProviderEmulator


ROOT = Path(__file__).parents[2]
TEMPLATES = ROOT / "deploy" / "phase6" / "aws"


def test_complete_render_resolves_every_placeholder_and_secret_reference():
    emulator = LocalProviderEmulator()
    rendered = render_external_staging_configuration(TEMPLATES, emulator)

    assert set(rendered.documents) == {
        "api.workload.json",
        "research-isolation.policy.json",
        "scheduler.workload.json",
        "workers.workload.json",
    }
    assert len(rendered.resolved_placeholders) == 24
    assert rendered.unresolved_placeholders == ()
    assert set(rendered.secret_references) == {
        "application-database",
        "research-database",
        "alert-delivery",
    }


def test_render_preserves_all_execution_authority_as_false():
    rendered = render_external_staging_configuration(TEMPLATES, LocalProviderEmulator())

    assert rendered.broker_authority is False
    assert rendered.live_authority is False
    assert rendered.production_authority is False
    assert rendered.execution_authorized is False
    for document in rendered.documents.values():
        assert document["environment"] == "staging"


def test_render_uses_local_endpoints_opaque_references_and_pinned_images():
    rendered = render_external_staging_configuration(TEMPLATES, LocalProviderEmulator())
    api = rendered.documents["api.workload.json"]["workload"]

    assert api["image"]["uri"].startswith("emulator+oci://registry.phase6.invalid/")
    assert "@sha256:" in api["image"]["uri"]
    assert api["configuration"]["ARMS_DATABASE_HOST"] == "database.phase6.invalid"
    assert api["configuration"]["ARMS_OIDC_ISSUER"].endswith(".invalid/")
    assert set(api["secret_references"][0]) == {"name", "value_from"}
    assert "password" not in str(api).lower()


def test_render_fails_closed_for_missing_placeholder_value(tmp_path):
    template = tmp_path / "broken.json"
    template.write_text(
        '{"environment":"staging","unknown":"{{UNEXPECTED_VALUE}}",'
        '"authority":{"broker":false,"paper":false,"live":false,"production":false}}',
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationRenderError, match="unresolved placeholders"):
        render_external_staging_configuration(tmp_path, LocalProviderEmulator())


def test_render_rejects_enabled_authority(tmp_path):
    (tmp_path / "unsafe.json").write_text(
        '{"environment":"staging","authority":'
        '{"broker":true,"paper":false,"live":false,"production":false}}',
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationRenderError, match="execution authority"):
        render_external_staging_configuration(tmp_path, LocalProviderEmulator())
