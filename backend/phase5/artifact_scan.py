"""Dependency-free static scanner for local Phase 5 staging packages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import stat

from backend.phase4.package_validation import (
    PackageValidationError,
    validate_phase4_package,
)


STATIC_SCAN_CHECKS = (
    "PACKAGE_INTEGRITY",
    "SECRET_MATERIAL",
    "UNSAFE_CONFIG",
    "DEBUG_FLAGS",
    "NETWORK_AUTHORITY",
    "LIVE_BROKER_IMPORT",
    "WORLD_WRITABLE_FILE",
)
_TEXT_SUFFIXES = frozenset({
    ".cfg",
    ".env",
    ".ini",
    ".json",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
})
_SENSITIVE_NAMES = frozenset({
    ".env",
    "credentials.json",
    "secrets.json",
})
_SENSITIVE_SUFFIXES = frozenset({".key", ".p12", ".pem"})
_MAX_TEXT_BYTES = 2 * 1024 * 1024
_SECRET_ASSIGNMENT = re.compile(
    r"(?im)^\s*[\"']?(?:api[_-]?key|password|passwd|secret|access[_-]?token|"
    r"private[_-]?key)[\"']?\s*[:=]\s*[\"'][^\"'\r\n]{8,}[\"']\s*,?\s*$"
)
_UNSAFE_CONFIG = re.compile(
    r"(?im)^\s*(?:authentication_required\s*[:=]\s*false|"
    r"execution_authorized\s*[:=]\s*true|"
    r"production_mutation_authorized\s*[:=]\s*true|"
    r"deployment_authorized\s*[:=]\s*true|"
    r"live_trading_enabled\s*[:=]\s*true)\s*,?\s*$"
)
_DEBUG_FLAG = re.compile(
    r"(?im)^\s*(?:debug|trace_orders|enable_debug_logging)\s*[:=]\s*"
    r"(?:true|1)\s*,?\s*$"
)
_NETWORK_IMPORT = re.compile(
    r"(?im)^\s*(?:from\s+(?:aiohttp|httpx|requests|socket|urllib\.request)\b|"
    r"import\s+(?:aiohttp|httpx|requests|socket|urllib\.request)\b)"
)
_LIVE_BROKER_IMPORT = re.compile(
    r"(?im)^\s*(?:from|import)\s+[^\r\n]*(?:broker_connector|live_broker|"
    r"ninjatrader|execution\.live)\b"
)


@dataclass(frozen=True, order=True)
class StaticScanFinding:
    check: str
    path: str
    line: int | None

    def __post_init__(self) -> None:
        if self.check not in STATIC_SCAN_CHECKS:
            raise ValueError("static scan finding check is invalid")
        if not isinstance(self.path, str) or not self.path:
            raise ValueError("static scan finding path is invalid")
        if self.line is not None and (type(self.line) is not int or self.line < 1):
            raise ValueError("static scan finding line is invalid")


@dataclass(frozen=True)
class StaticScanReport:
    files_scanned: int
    checks: tuple[str, ...]
    findings: tuple[StaticScanFinding, ...]
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)
    external_scan_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if type(self.files_scanned) is not int or self.files_scanned < 0:
            raise ValueError("files_scanned must be nonnegative")
        if self.checks != STATIC_SCAN_CHECKS:
            raise ValueError("static scan report must contain every check")
        if not isinstance(self.findings, tuple) or tuple(sorted(self.findings)) != self.findings:
            raise ValueError("static scan findings must be sorted")

    @property
    def passed(self) -> bool:
        return not self.findings


def _line(text: str, match: re.Match[str]) -> int:
    return text.count("\n", 0, match.start()) + 1


def scan_staging_package(package_root: Path) -> StaticScanReport:
    if not isinstance(package_root, Path) or not package_root.is_absolute():
        raise ValueError("package_root must be an absolute Path")
    root = package_root.resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("package_root must be a non-symlink directory")
    findings = []
    try:
        validate_phase4_package(root)
    except PackageValidationError:
        findings.append(StaticScanFinding("PACKAGE_INTEGRITY", "<package>", None))

    files = tuple(sorted(path for path in root.rglob("*") if path.is_file()))
    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            findings.append(StaticScanFinding("PACKAGE_INTEGRITY", relative, None))
            continue
        mode = path.stat().st_mode
        if mode & stat.S_IWOTH:
            findings.append(StaticScanFinding("WORLD_WRITABLE_FILE", relative, None))
        lowered_name = path.name.lower()
        if lowered_name in _SENSITIVE_NAMES or path.suffix.lower() in _SENSITIVE_SUFFIXES:
            findings.append(StaticScanFinding("SECRET_MATERIAL", relative, None))
        if path.suffix.lower() not in _TEXT_SUFFIXES or path.stat().st_size > _MAX_TEXT_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            findings.append(StaticScanFinding("PACKAGE_INTEGRITY", relative, None))
            continue
        for check, pattern in (
            ("SECRET_MATERIAL", _SECRET_ASSIGNMENT),
            ("UNSAFE_CONFIG", _UNSAFE_CONFIG),
            ("DEBUG_FLAGS", _DEBUG_FLAG),
            ("NETWORK_AUTHORITY", _NETWORK_IMPORT),
            ("LIVE_BROKER_IMPORT", _LIVE_BROKER_IMPORT),
        ):
            findings.extend(
                StaticScanFinding(check, relative, _line(text, match))
                for match in pattern.finditer(text)
            )
    return StaticScanReport(len(files), STATIC_SCAN_CHECKS, tuple(sorted(set(findings))))
