"""Fail-closed static security scan for Phase 6 IaC and workload manifests."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class SecurityFinding:
    code: str
    path: str
    detail: str


@dataclass(frozen=True)
class ConfigurationSecurityReport:
    files_scanned: int
    findings: tuple[SecurityFinding, ...]
    external_actions_performed: bool = False

    @property
    def passed(self) -> bool:
        return not self.findings

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "BLOCKED"


def _finding(code: str, path: Path, root: Path, detail: str) -> SecurityFinding:
    try:
        rendered = path.relative_to(root).as_posix()
    except ValueError:
        rendered = path.as_posix()
    return SecurityFinding(code=code, path=rendered, detail=detail)


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _walk_json(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = path + (str(key),)
            yield child_path, child
            yield from _walk_json(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = path + (str(index),)
            yield child_path, child
            yield from _walk_json(child, child_path)


def _scan_json(path: Path, root: Path) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [_finding("INVALID_CONFIGURATION", path, root, str(exc))]

    if document.get("environment") != "staging":
        findings.append(_finding("NON_STAGING_ENVIRONMENT", path, root, "environment must equal staging"))

    for key_path, value in _walk_json(document):
        key = key_path[-1].upper()
        rendered = ".".join(key_path)
        if key == "ASSIGN_PUBLIC_IP" and value is not False:
            findings.append(_finding("PUBLIC_WORKLOAD_IP", path, root, rendered))
        if key == "EGRESS_TO" and isinstance(value, list):
            allowed = {"private_postgresql", "private_aws_endpoints"}
            if not set(value).issubset(allowed):
                findings.append(_finding("UNRESTRICTED_EGRESS", path, root, rendered))
        if key in {"BROKER", "PAPER", "LIVE", "PRODUCTION", "FINANCIAL_EXECUTION"} and value is not False:
            findings.append(_finding("EXECUTION_AUTHORITY_ENABLED", path, root, rendered))
        if any(marker in key for marker in ("EXECUTION_AUTHORIZED", "BROKER_ENABLED", "PAPER_ENABLED", "LIVE_ENABLED", "PRODUCTION_MUTATION_AUTHORIZED")) and _truthy(value):
            findings.append(_finding("EXECUTION_AUTHORITY_ENABLED", path, root, rendered))
        if "DEBUG" in key and _truthy(value):
            findings.append(_finding("DEBUG_ENABLED", path, root, rendered))

        secret_key = any(marker in key for marker in ("PASSWORD", "TOKEN", "API_KEY", "CREDENTIAL", "CLIENT_SECRET"))
        in_secret_reference = "secret_references" in key_path and key in {"NAME", "VALUE_FROM"}
        if secret_key and isinstance(value, str) and not in_secret_reference:
            findings.append(_finding("PLAINTEXT_SECRET_FIELD", path, root, rendered))
        if in_secret_reference and key == "VALUE_FROM":
            if not isinstance(value, str) or not re.fullmatch(r"\{\{[A-Z0-9_]+_ARN\}\}", value):
                findings.append(_finding("INVALID_SECRET_REFERENCE", path, root, rendered))
        if "BROKER" in key and any(marker in key for marker in ("PASSWORD", "TOKEN", "KEY", "CREDENTIAL", "SECRET")):
            findings.append(_finding("BROKER_CREDENTIAL_PRESENT", path, root, rendered))
    return findings


def _scan_terraform(path: Path, root: Path) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [_finding("INVALID_CONFIGURATION", path, root, str(exc))]

    checks = (
        ("OPEN_INGRESS", r'(?i)\bcidr_ipv[46]\s*=\s*"(?:0\.0\.0\.0/0|::/0)"'),
        ("PUBLIC_DATABASE", r'(?i)\bpublicly_accessible\s*=\s*true\b'),
        ("UNRESTRICTED_EGRESS", r'(?ims)resource\s+"aws_vpc_security_group_egress_rule"[^}]*cidr_ipv[46]\s*=\s*"(?:0\.0\.0\.0/0|::/0)"'),
        ("DEBUG_ENABLED", r'(?im)^\s*[^#\n]*debug[^=\n]*=\s*(?:true|"true")\b'),
        ("EXECUTION_AUTHORITY_ENABLED", r'(?im)^\s*[^#\n]*(?:live|production|broker|paper|execution)[^=\n]*(?:enabled|authorized|authority)?\s*=\s*(?:true|"true")\b'),
        ("BROKER_CREDENTIAL_PRESENT", r'(?im)^\s*(?:variable\s+)?"?[^"\n]*(?:broker)[^"\n]*(?:password|token|key|credential|secret)[^"\n]*"?\s*\{?'),
        ("PLAINTEXT_SECRET_FIELD", r'(?im)^\s*(?:password|token|api_key|client_secret|credential)\s*=\s*"(?!\$\{)[^"\n]+"'),
    )
    for code, pattern in checks:
        if re.search(pattern, text):
            findings.append(_finding(code, path, root, f"matched prohibited {code.lower()} pattern"))
    return findings


def scan_phase6_configuration(iac_root: Path, deployment_root: Path) -> ConfigurationSecurityReport:
    """Scan committed staging templates and return BLOCKED for any finding."""

    iac_root = Path(iac_root)
    deployment_root = Path(deployment_root)
    common_root = Path(os.path.commonpath([iac_root.resolve(), deployment_root.resolve()]))
    findings: list[SecurityFinding] = []
    files: list[Path] = []

    if not iac_root.is_dir():
        findings.append(SecurityFinding("MISSING_IAC_ROOT", iac_root.as_posix(), "IaC root is missing"))
    else:
        files.extend(sorted(iac_root.rglob("*.tf")))
        forbidden_values = sorted(iac_root.rglob("*.tfvars")) + sorted(iac_root.rglob("*.auto.tfvars.json"))
        for path in forbidden_values:
            findings.append(_finding("PLAINTEXT_VARIABLE_VALUES", path, common_root, "variable value files are forbidden"))
            files.append(path)

    if not deployment_root.is_dir():
        findings.append(SecurityFinding("MISSING_DEPLOYMENT_ROOT", deployment_root.as_posix(), "deployment root is missing"))
    else:
        files.extend(sorted(deployment_root.rglob("*.json")))

    for path in files:
        if path.suffix == ".tf":
            findings.extend(_scan_terraform(path, common_root))
        elif path.suffix == ".json" and not path.name.endswith(".tfvars.json"):
            findings.extend(_scan_json(path, common_root))

    if not files:
        findings.append(SecurityFinding("NO_CONFIGURATION", common_root.as_posix(), "no configuration files found"))
    return ConfigurationSecurityReport(
        files_scanned=len(files),
        findings=tuple(findings),
    )
