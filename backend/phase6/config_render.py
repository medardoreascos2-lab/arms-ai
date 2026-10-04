"""Complete in-memory render of Phase 6 manifests against local emulation."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping

from backend.phase6.provider_emulator import LocalProviderEmulator


class ConfigurationRenderError(ValueError):
    """Raised when a manifest cannot be rendered into a safe staging config."""


PLACEHOLDER_PATTERN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
REQUIRED_SECRET_REFERENCES = frozenset(
    {
        "APPLICATION_DATABASE_SECRET_ARN",
        "RESEARCH_DATABASE_SECRET_ARN",
        "ALERT_DELIVERY_SECRET_ARN",
    }
)


@dataclass(frozen=True)
class RenderedStagingConfiguration:
    documents: Mapping[str, Mapping[str, Any]]
    resolved_placeholders: tuple[str, ...]
    secret_references: tuple[str, ...]
    unresolved_placeholders: tuple[str, ...]
    broker_authority: bool = False
    live_authority: bool = False
    production_authority: bool = False
    execution_authorized: bool = False


def _walk(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = path + (str(key),)
            yield child_path, child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = path + (str(index),)
            yield child_path, child
            yield from _walk(child, child_path)


def emulated_render_values(emulator: LocalProviderEmulator) -> Mapping[str, str]:
    """Return non-secret values and opaque secret references for local rendering."""

    database_endpoint = emulator.resolve_database_endpoint()
    identity = emulator.resolve_identity_metadata()
    image_digest = "sha256:" + "d" * 64
    values = {
        "REGISTRY_URL": emulator.registry_endpoint,
        "IMAGE_DIGEST": image_digest,
        "DATABASE_HOST": "database.phase6.invalid",
        "DATABASE_PORT": "5432",
        "OIDC_ISSUER": identity.issuer,
        "OIDC_AUDIENCE": identity.audience,
        "OIDC_JWKS_URI": identity.jwks_uri,
        "API_TASK_ROLE_ARN": "arn:aws:iam::000000000000:role/arms-ai-staging-api",
        "API_EXECUTION_ROLE_ARN": "arn:aws:iam::000000000000:role/arms-ai-staging-api-execution",
        "WORKER_TASK_ROLE_ARN": "arn:aws:iam::000000000000:role/arms-ai-staging-worker",
        "WORKER_EXECUTION_ROLE_ARN": "arn:aws:iam::000000000000:role/arms-ai-staging-worker-execution",
        "RESEARCH_TASK_ROLE_ARN": "arn:aws:iam::000000000000:role/arms-ai-staging-research",
        "RESEARCH_EXECUTION_ROLE_ARN": "arn:aws:iam::000000000000:role/arms-ai-staging-research-execution",
        "MAINTENANCE_TASK_ROLE_ARN": "arn:aws:iam::000000000000:role/arms-ai-staging-maintenance",
        "MAINTENANCE_EXECUTION_ROLE_ARN": "arn:aws:iam::000000000000:role/arms-ai-staging-maintenance-execution",
        "SCHEDULER_TASK_ROLE_ARN": "arn:aws:iam::000000000000:role/arms-ai-staging-scheduler",
        "SCHEDULER_EXECUTION_ROLE_ARN": "arn:aws:iam::000000000000:role/arms-ai-staging-scheduler-execution",
        "API_LOG_GROUP": "/arms-ai/staging/api",
        "WORKER_LOG_GROUP": "/arms-ai/staging/worker",
        "RESEARCH_LOG_GROUP": "/arms-ai/staging/research",
        "SCHEDULER_LOG_GROUP": "/arms-ai/staging/scheduler",
        "APPLICATION_DATABASE_SECRET_ARN": (
            "arn:aws:secretsmanager:phase6-local:000000000000:secret:"
            "arms-ai/staging/application-database"
        ),
        "RESEARCH_DATABASE_SECRET_ARN": (
            "arn:aws:secretsmanager:phase6-local:000000000000:secret:"
            "arms-ai/staging/research-database"
        ),
        "ALERT_DELIVERY_SECRET_ARN": (
            "arn:aws:secretsmanager:phase6-local:000000000000:secret:"
            "arms-ai/staging/alert-delivery"
        ),
    }
    if database_endpoint != emulator.database_endpoint:
        raise ConfigurationRenderError("database emulator endpoint changed during render")
    return MappingProxyType(values)


def _replace(value: Any, values: Mapping[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace(child, values) for key, child in value.items()}
    if isinstance(value, list):
        return [_replace(child, values) for child in value]
    if not isinstance(value, str):
        return value

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            return match.group(0)
        return values[name]

    return PLACEHOLDER_PATTERN.sub(substitute, value)


def render_external_staging_configuration(
    template_root: Path,
    emulator: LocalProviderEmulator,
    *,
    value_overrides: Mapping[str, str] | None = None,
) -> RenderedStagingConfiguration:
    """Render all workload JSON and fail closed on incomplete or unsafe output."""

    template_root = Path(template_root)
    if not template_root.is_dir():
        raise ConfigurationRenderError("template root is missing")
    values = dict(emulated_render_values(emulator))
    if value_overrides:
        values.update(value_overrides)
    if any(not isinstance(value, str) or not value for value in values.values()):
        raise ConfigurationRenderError("render values must be nonempty text")

    documents: dict[str, Mapping[str, Any]] = {}
    encountered: set[str] = set()
    unresolved: set[str] = set()
    secret_references: set[str] = set()
    template_paths = sorted(template_root.glob("*.json"))
    if not template_paths:
        raise ConfigurationRenderError("no workload templates found")

    for path in template_paths:
        raw = path.read_text(encoding="utf-8")
        encountered.update(PLACEHOLDER_PATTERN.findall(raw))
        try:
            source = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigurationRenderError(f"invalid JSON template {path.name}") from exc
        rendered = _replace(source, values)
        serialized = json.dumps(rendered, sort_keys=True, separators=(",", ":"))
        unresolved.update(PLACEHOLDER_PATTERN.findall(serialized))

        if rendered.get("environment") != "staging":
            raise ConfigurationRenderError(f"{path.name} is outside staging")
        for key_path, value in _walk(rendered):
            key = key_path[-1].upper()
            path_text = ".".join(key_path)
            if key in {"BROKER", "PAPER", "LIVE", "PRODUCTION", "FINANCIAL_EXECUTION"} and value is not False:
                raise ConfigurationRenderError(f"execution authority enabled at {path_text}")
            if any(marker in key for marker in ("EXECUTION_AUTHORIZED", "BROKER_ENABLED", "PAPER_ENABLED", "LIVE_ENABLED", "PRODUCTION_MUTATION_AUTHORIZED")):
                if value is not False and str(value).lower() != "false":
                    raise ConfigurationRenderError(f"execution authority enabled at {path_text}")
            if "secret_references" in key_path and key == "VALUE_FROM":
                if not isinstance(value, str) or not value.startswith(
                    "arn:aws:secretsmanager:phase6-local:000000000000:secret:arms-ai/staging/"
                ):
                    raise ConfigurationRenderError(f"invalid secret reference at {path_text}")
                secret_references.add(value.rsplit("/", 1)[-1])
            secret_field = any(marker in key for marker in ("PASSWORD", "TOKEN", "API_KEY", "CLIENT_SECRET"))
            if secret_field and isinstance(value, str):
                raise ConfigurationRenderError(f"secret value field present at {path_text}")
        documents[path.name] = rendered

    if unresolved:
        raise ConfigurationRenderError(f"unresolved placeholders: {sorted(unresolved)}")
    missing_values = encountered - set(values)
    if missing_values:
        raise ConfigurationRenderError(f"missing render values: {sorted(missing_values)}")
    expected_secret_names = {"application-database", "research-database", "alert-delivery"}
    if secret_references != expected_secret_names:
        raise ConfigurationRenderError("required secret reference set is incomplete")

    return RenderedStagingConfiguration(
        documents=MappingProxyType(documents),
        resolved_placeholders=tuple(sorted(encountered)),
        secret_references=tuple(sorted(secret_references)),
        unresolved_placeholders=(),
    )
