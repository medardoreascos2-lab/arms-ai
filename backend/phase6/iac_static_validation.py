"""Credential-free static checks for the Phase 6 Terraform/OpenTofu tree."""

from dataclasses import dataclass
from pathlib import Path
import re


REQUIRED_ROOT_FILES = frozenset(
    {"versions.tf", "providers.tf", "variables.tf", "locals.tf", "outputs.tf"}
)
REQUIRED_MODULES = frozenset(
    {"network", "database", "secrets", "identity", "observability", "backup", "registry"}
)
REQUIRED_MODULE_FILES = frozenset({"main.tf", "variables.tf", "outputs.tf"})


@dataclass(frozen=True)
class IacValidationReport:
    root: Path
    terraform_file_count: int
    module_names: tuple[str, ...]
    errors: tuple[str, ...]
    limitations: tuple[str, ...]
    terraform_available: bool
    opentofu_available: bool
    external_actions_performed: bool = False

    @property
    def passed(self) -> bool:
        return not self.errors

    @property
    def native_validation_available(self) -> bool:
        return self.terraform_available or self.opentofu_available


def _structure_only(text: str) -> str:
    """Replace comments and quoted text while preserving structural delimiters."""

    result: list[str] = []
    index = 0
    state = "code"
    while index < len(text):
        char = text[index]
        pair = text[index : index + 2]
        if state == "code":
            if char == '"':
                state = "string"
                result.append(" ")
            elif char == "#":
                state = "line_comment"
                result.append(" ")
            elif pair == "//":
                state = "line_comment"
                result.extend("  ")
                index += 1
            elif pair == "/*":
                state = "block_comment"
                result.extend("  ")
                index += 1
            else:
                result.append(char)
        elif state == "string":
            if char == "\\":
                result.append(" ")
                if index + 1 < len(text):
                    result.append(" ")
                    index += 1
            elif char == '"':
                state = "code"
                result.append(" ")
            else:
                result.append("\n" if char == "\n" else " ")
        elif state == "line_comment":
            if char == "\n":
                state = "code"
                result.append("\n")
            else:
                result.append(" ")
        elif state == "block_comment":
            if pair == "*/":
                state = "code"
                result.extend("  ")
                index += 1
            else:
                result.append("\n" if char == "\n" else " ")
        index += 1
    if state in {"string", "block_comment"}:
        raise ValueError(f"unterminated {state.replace('_', ' ')}")
    return "".join(result)


def _delimiter_error(text: str) -> str | None:
    opening = {"{": "}", "[": "]", "(": ")"}
    closing = {value: key for key, value in opening.items()}
    stack: list[tuple[str, int]] = []
    for position, char in enumerate(text):
        if char in opening:
            stack.append((char, position))
        elif char in closing:
            if not stack or stack[-1][0] != closing[char]:
                return f"unexpected delimiter {char!r} at offset {position}"
            stack.pop()
    if stack:
        char, position = stack[-1]
        return f"unclosed delimiter {char!r} at offset {position}"
    return None


_DECLARATION = re.compile(
    r'^\s*(resource|data|module|variable|output|provider)\s+"([^"]+)"'
    r'(?:\s+"([^"]+)")?\s*\{',
    flags=re.MULTILINE,
)


def _duplicate_declarations(paths: list[Path]) -> list[str]:
    declarations: dict[tuple[str, str, str], Path] = {}
    errors: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for kind, first, second in _DECLARATION.findall(text):
            identity = (kind, first, second or "")
            if identity in declarations:
                errors.append(
                    f"duplicate {kind} declaration {first}.{second or ''} in "
                    f"{declarations[identity].name} and {path.name}"
                )
            else:
                declarations[identity] = path
    return errors


def validate_iac_tree(
    root: Path,
    *,
    terraform_available: bool = False,
    opentofu_available: bool = False,
) -> IacValidationReport:
    """Validate local HCL structure and module wiring without provider access."""

    root = Path(root)
    errors: list[str] = []
    if not root.is_dir():
        errors.append("IaC root does not exist")
        paths: list[Path] = []
    else:
        paths = sorted(root.rglob("*.tf"))

    root_files = {path.name for path in root.glob("*.tf")} if root.is_dir() else set()
    missing_root = REQUIRED_ROOT_FILES - root_files
    if missing_root:
        errors.append(f"missing root Terraform files: {sorted(missing_root)}")

    module_root = root / "modules"
    module_names = tuple(sorted(path.name for path in module_root.iterdir() if path.is_dir())) \
        if module_root.is_dir() else ()
    missing_modules = REQUIRED_MODULES - set(module_names)
    if missing_modules:
        errors.append(f"missing required modules: {sorted(missing_modules)}")
    for module_name in module_names:
        module_files = {path.name for path in (module_root / module_name).glob("*.tf")}
        missing_files = REQUIRED_MODULE_FILES - module_files
        if missing_files:
            errors.append(f"module {module_name} missing files: {sorted(missing_files)}")

    for path in paths:
        try:
            structural = _structure_only(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
            continue
        delimiter_error = _delimiter_error(structural)
        if delimiter_error:
            errors.append(f"{path.relative_to(root)}: {delimiter_error}")

    by_directory: dict[Path, list[Path]] = {}
    for path in paths:
        by_directory.setdefault(path.parent, []).append(path)
    for directory_paths in by_directory.values():
        errors.extend(_duplicate_declarations(directory_paths))

    root_text = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.tf"))
    if not re.search(r'required_version\s*=\s*"[^"]+"', root_text):
        errors.append("required Terraform/OpenTofu version constraint is missing")
    if 'source  = "hashicorp/aws"' not in root_text:
        errors.append("AWS provider source constraint is missing")
    if re.search(r'^\s*backend\s+"', root_text, flags=re.MULTILINE):
        errors.append("remote state backend must remain operator-selected and unconfigured")
    if re.search(r'^\s*resource\s+"', root_text, flags=re.MULTILINE):
        errors.append("root module must compose reviewed child modules only")

    module_sources = set(re.findall(r'source\s*=\s*"\./modules/([^"]+)"', root_text))
    missing_sources = REQUIRED_MODULES - module_sources
    if missing_sources:
        errors.append(f"root module does not reference modules: {sorted(missing_sources)}")
    unknown_sources = module_sources - set(module_names)
    if unknown_sources:
        errors.append(f"root module references missing local modules: {sorted(unknown_sources)}")

    limitations = []
    if not (terraform_available or opentofu_available):
        limitations.append(
            "Terraform/OpenTofu was unavailable; provider schema validation, fmt and plan were not run."
        )
    limitations.append("No provider credentials were used and no external plan or apply was executed.")

    return IacValidationReport(
        root=root,
        terraform_file_count=len(paths),
        module_names=module_names,
        errors=tuple(errors),
        limitations=tuple(limitations),
        terraform_available=terraform_available,
        opentofu_available=opentofu_available,
    )
