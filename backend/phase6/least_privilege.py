"""Static least-privilege validation for Phase 6 AWS staging boundaries."""

from dataclasses import dataclass
import json
from pathlib import Path
import re


REQUIRED_SURFACES = (
    "API",
    "workers",
    "scheduler",
    "DB",
    "secret manager",
    "backup",
    "artifact registry",
    "telemetry",
)


@dataclass(frozen=True)
class LeastPrivilegeFinding:
    surface: str
    code: str
    detail: str


@dataclass(frozen=True)
class LeastPrivilegeReport:
    surfaces: tuple[str, ...]
    findings: tuple[LeastPrivilegeFinding, ...]
    external_actions_performed: bool = False

    @property
    def passed(self) -> bool:
        return not self.findings

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "BLOCKED"


def _add_missing(
    findings: list[LeastPrivilegeFinding],
    surface: str,
    text: str,
    required: tuple[str, ...],
) -> None:
    for snippet in required:
        if snippet not in text:
            findings.append(LeastPrivilegeFinding(surface, "MISSING_SCOPE_CONTROL", snippet))


def validate_phase6_least_privilege(iac_root: Path, deployment_root: Path) -> LeastPrivilegeReport:
    """Validate the exact permission separation expressed by Phase 6 templates."""

    iac_root = Path(iac_root)
    deployment_root = Path(deployment_root)
    findings: list[LeastPrivilegeFinding] = []
    tf_paths = sorted(iac_root.rglob("*.tf")) if iac_root.is_dir() else []
    json_paths = sorted(deployment_root.rglob("*.json")) if deployment_root.is_dir() else []
    if not tf_paths or not json_paths:
        return LeastPrivilegeReport(
            REQUIRED_SURFACES,
            (LeastPrivilegeFinding("global", "MISSING_CONFIGURATION", "IaC or manifests missing"),),
        )

    all_tf = "\n".join(path.read_text(encoding="utf-8") for path in tf_paths)
    for marker in (
        "AdministratorAccess",
        "PowerUserAccess",
        "arn:aws:iam::aws:policy/",
        'Action = ["*"]',
        'actions = ["*"]',
    ):
        if marker in all_tf:
            findings.append(LeastPrivilegeFinding("global", "BROAD_ADMIN_PERMISSION", marker))
    broad_service_actions = set(re.findall(r'"([a-z0-9-]+:\*)"', all_tf, flags=re.IGNORECASE))
    if broad_service_actions - {"s3:*"}:
        findings.append(
            LeastPrivilegeFinding(
                "global",
                "BROAD_SERVICE_PERMISSION",
                repr(sorted(broad_service_actions - {"s3:*"})),
            )
        )

    identity_main = (iac_root / "modules" / "identity" / "main.tf").read_text(encoding="utf-8")
    identity_variables = (iac_root / "modules" / "identity" / "variables.tf").read_text(encoding="utf-8")
    root_modules = (iac_root / "locals.tf").read_text(encoding="utf-8")
    for service in (
        "api",
        "worker",
        "scheduler",
        "research",
        "migration",
        "maintenance",
        "backup",
        "restore",
        "telemetry",
        "artifact-publisher",
    ):
        if f'"{service}"' not in identity_main or f"{service}" not in root_modules:
            findings.append(LeastPrivilegeFinding(service, "MISSING_ISOLATED_IDENTITY", service))
    _add_missing(
        findings,
        "API/workers/scheduler",
        identity_main + identity_variables,
        (
            'identifiers = ["ecs-tasks.amazonaws.com"]',
            'actions = ["sts:AssumeRole"]',
            'resource "aws_iam_role_policy_attachment" "workload"',
            "aws_iam_role.service[each.value.service].name",
            "policy_arn = each.value.policy_arn",
        ),
    )

    role_values: list[str] = []
    for path in json_paths:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            findings.append(LeastPrivilegeFinding("global", "INVALID_MANIFEST", path.name))
            continue
        serialized = json.dumps(document)
        if '"shared_role_allowed": true' in serialized:
            findings.append(LeastPrivilegeFinding("API/workers/scheduler", "SHARED_ROLE_ENABLED", path.name))
        for match in re.finditer(r'"(?:task|execution)_role_arn"\s*:\s*"([^"]+)"', serialized):
            role_values.append(match.group(1))
    if len(role_values) != len(set(role_values)):
        findings.append(LeastPrivilegeFinding("API/workers/scheduler", "DUPLICATE_ROLE_REFERENCE", "roles must be unique"))

    database = (iac_root / "modules" / "database" / "main.tf").read_text(encoding="utf-8")
    network = (iac_root / "modules" / "network" / "main.tf").read_text(encoding="utf-8")
    _add_missing(
        findings,
        "DB",
        database + network,
        (
            "publicly_accessible    = false",
            "manage_master_user_password = true",
            "iam_database_authentication_enabled = true",
            'resource "aws_vpc_security_group_ingress_rule" "database"',
            "referenced_security_group_id = each.value",
            "from_port                    = 5432",
        ),
    )

    secrets = (iac_root / "modules" / "secrets" / "main.tf").read_text(encoding="utf-8")
    _add_missing(
        findings,
        "secret manager",
        secrets,
        (
            '"secretsmanager:DescribeSecret"',
            '"secretsmanager:GetSecretValue"',
            'Action   = ["kms:Decrypt"]',
            'Resource = [aws_kms_key.secrets.arn]',
            '"kms:ViaService"',
        ),
    )
    for forbidden in ('"secretsmanager:ListSecrets"', '"secretsmanager:PutSecretValue"', '"secretsmanager:DeleteSecret"'):
        if forbidden in secrets:
            findings.append(LeastPrivilegeFinding("secret manager", "EXCESS_SECRET_PERMISSION", forbidden))

    backup = (iac_root / "modules" / "backup" / "main.tf").read_text(encoding="utf-8")
    writer, reader = backup.split('resource "aws_iam_policy" "restore_reader"', 1)
    _add_missing(
        findings,
        "backup",
        writer,
        ('"s3:PutObject"', '"kms:Encrypt"', 'Resource = "${aws_s3_bucket.backup.arn}/backups/*"'),
    )
    _add_missing(
        findings,
        "backup",
        reader,
        ('"s3:GetObject"', '"kms:Decrypt"', 'Resource = "${aws_s3_bucket.backup.arn}/backups/*"'),
    )
    if '"s3:GetObject"' in writer or '"s3:PutObject"' in reader:
        findings.append(LeastPrivilegeFinding("backup", "BACKUP_RESTORE_ROLE_MIXING", "read/write duties mixed"))

    registry = (iac_root / "modules" / "registry" / "main.tf").read_text(encoding="utf-8")
    publisher, puller = registry.split('resource "aws_iam_policy" "puller"', 1)
    _add_missing(
        findings,
        "artifact registry",
        publisher,
        ('"ecr:PutImage"', "Resource = aws_ecr_repository.staging.arn"),
    )
    _add_missing(
        findings,
        "artifact registry",
        puller,
        ('"ecr:BatchGetImage"', '"ecr:GetDownloadUrlForLayer"', "Resource = aws_ecr_repository.staging.arn"),
    )
    if '"ecr:PutImage"' in puller or '"ecr:DeleteRepository"' in registry:
        findings.append(LeastPrivilegeFinding("artifact registry", "EXCESS_REGISTRY_PERMISSION", "pull/delete authority"))

    telemetry = (iac_root / "modules" / "observability" / "main.tf").read_text(encoding="utf-8")
    _add_missing(
        findings,
        "telemetry",
        telemetry,
        (
            '"logs:CreateLogStream"',
            '"logs:PutLogEvents"',
            'Action   = ["cloudwatch:PutMetricData"]',
            '"cloudwatch:namespace" = "ARMSAI/Staging/Safety"',
        ),
    )
    for forbidden in ('"logs:GetLogEvents"', '"logs:DeleteLogGroup"', '"cloudwatch:DeleteAlarms"'):
        if forbidden in telemetry:
            findings.append(LeastPrivilegeFinding("telemetry", "EXCESS_TELEMETRY_PERMISSION", forbidden))

    return LeastPrivilegeReport(REQUIRED_SURFACES, tuple(findings))
