"""R57B local static scan tests for Phase 5 staging artifacts."""

import os
from pathlib import Path
import subprocess
import sys

from backend.phase5.artifact_scan import STATIC_SCAN_CHECKS, scan_staging_package


GIT_SHA = "7" * 40


def _make_writable(root: Path):
    for path in root.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o666)


def _safe_source(root: Path):
    root.mkdir()
    (root / "requirements.txt").write_text("fastapi==0.139.2\n", encoding="utf-8")
    for relative in (
        "backend/phase3/runtime.py",
        "backend/phase4/runtime.py",
        "backend/phase5/runtime.py",
    ):
        path = root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "execution_authorized = False\n"
            "production_mutation_authorized = False\n"
            "debug = False\n",
            encoding="utf-8",
        )
    return root


def test_reproducible_package_passes_all_local_static_checks(tmp_path):
    source = _safe_source(tmp_path / "source")
    package = tmp_path / "package"
    repository_root = Path(__file__).parents[2]
    build = repository_root / "tools" / "build_phase5_staging_package.py"
    scan = repository_root / "tools" / "scan_phase5_staging_package.py"

    subprocess.run(
        [
            sys.executable,
            str(build),
            "--repository-root",
            str(source),
            "--destination-root",
            str(package),
            "--git-sha",
            GIT_SHA,
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=repository_root,
    )
    try:
        report = scan_staging_package(package.resolve())
        cli = subprocess.run(
            [sys.executable, str(scan), "--package-root", str(package)],
            check=True,
            capture_output=True,
            text=True,
            cwd=repository_root,
        )

        assert report.passed is True
        assert report.findings == ()
        assert report.checks == STATIC_SCAN_CHECKS
        assert report.files_scanned == 5
        assert cli.stdout.startswith("PHASE5_STATIC_SCAN_PASS")
        assert "external_scan_authorized=false" in cli.stdout
        assert report.execution_authorized is False
        assert report.production_mutation_authorized is False
        assert report.deployment_authorized is False
        assert report.external_scan_authorized is False
    finally:
        _make_writable(package)


def test_scanner_reports_every_required_unsafe_artifact_class(tmp_path):
    package = tmp_path / "unsafe-package"
    package.mkdir()
    fixtures = {
        ".env": 'API_KEY="synthetic-secret-value"\n',
        "unsafe_config.py": (
            "authentication_required = False\n"
            "execution_authorized = True\n"
            "debug = True\n"
        ),
        "network.py": "import requests\n",
        "broker.py": "from backend.connectors.live_broker import LiveBroker\n",
        "secrets.json": '{"password":"synthetic-password"}\n',
    }
    for relative, content in fixtures.items():
        path = package / relative
        path.write_text(content, encoding="utf-8")
        os.chmod(path, 0o666)

    report = scan_staging_package(package.resolve())
    checks = {finding.check for finding in report.findings}

    assert report.passed is False
    assert checks == set(STATIC_SCAN_CHECKS)
    assert all(finding.path for finding in report.findings)
    assert all("synthetic-secret-value" not in repr(item) for item in report.findings)
    assert all("synthetic-password" not in repr(item) for item in report.findings)
