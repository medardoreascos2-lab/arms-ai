"""Explicit manifest, pre-deployment, and manual post-compile gates; read-only."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import os
import subprocess
import xml.etree.ElementTree as ET

SOURCES = {
    "ArmsSimNativeSubmitBridgeV2.cs": "Indicators",
    "ArmsSimNativeSubmitBridgeV2.ControlledV3.cs": "AddOns",
    "ArmsSimNativeSubmitBridgeV2.ReconciliationV3.cs": "AddOns",
    "ControlledSimOperationV3.cs": "AddOns",
}
OWNER = "ArmsSimNativeSubmitBridgeV2"
MODEL_TYPES = {"ControlledConfigurationV3", "ControlledSnapshotV3", "ControlledOrderV3", "IControlledAccountV3",
               "ControlledAdmissionV3", "ControlledOperationV3", "OperatorReconciliationV3"}


def code_only(text):
    # Remove comments and C# string/character literals before declaration checks.
    return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', ' ', text)


def manifest(repo: Path, custom: Path):
    rows = []
    for name, folder in SOURCES.items():
        source = repo / "integrations/ninjatrader" / name
        destination = custom / folder / name
        expected = hashlib.sha256(source.read_bytes()).hexdigest()
        actual = hashlib.sha256(destination.read_bytes()).hexdigest() if destination.is_file() else None
        rows.append(dict(source=str(source.resolve()), destination=str(destination.resolve()), expected_sha256=expected,
                         deployed_sha256=actual, action="COPY" if actual is None else "ALREADY_CURRENT" if actual == expected else "REPLACE"))
    return rows


def compile_offline(repo: Path, custom: Path, sdk: Path, output: Path):
    """Compile all production bodies; alias only the installed Indicator base.

    Installed Custom.dll is NOT a global reference: its old bridge cannot mask
    source duplicates. No generated output is written into the installation.
    """
    if output.resolve() == custom.resolve() or custom.resolve() in output.resolve().parents:
        raise ValueError("compile output must be outside NinjaTrader Custom")
    output.mkdir(parents=True, exist_ok=False)
    main = repo / "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
    isolated = output / main.name
    isolated.write_text("extern alias NTBase;\nusing Indicator = NTBase::NinjaTrader.NinjaScript.Indicators.Indicator;\n"+main.read_text(), encoding="utf-8")
    framework = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319"
    references = [sdk/"NinjaTrader.Core.dll", sdk/"NinjaTrader.Gui.dll",
        *(framework/"WPF"/name for name in ("WindowsBase.dll", "PresentationCore.dll", "PresentationFramework.dll")),
        "System.Core.dll", "System.Web.Extensions.dll", "System.ComponentModel.DataAnnotations.dll", "System.Xaml.dll", "System.Security.dll"]
    assembly = output / "ArmsRc2r.dll"
    command = [str(framework/"csc.exe"), "/nologo", "/langversion:5", "/target:library", "/out:"+str(assembly),
        *("/r:"+str(path) for path in references), "/r:NTBase="+str(custom/"NinjaTrader.Custom.dll"), str(isolated),
        *(str((repo/"integrations/ninjatrader"/name).resolve()) for name in SOURCES if name != main.name)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode or any(warning in result.stdout+result.stderr for warning in ("CS0436", "CS0612")):
        raise RuntimeError(result.stdout+result.stderr)
    return assembly, result.stdout+result.stderr


def verify(repo: Path, custom: Path, project: Path):
    """Certify exact pre-deployment destinations, never generated source variants.

    Project checks are conservative static checks, not an MSBuild evaluator.
    Conditional or indirect framework references require manual resolution.
    """
    rows = manifest(repo, custom)
    errors = []
    expected_paths = {Path(row["destination"]).resolve(): row for row in rows}
    counts = Counter()
    for path in custom.rglob("*.cs"):
        text = path.read_text(encoding="utf-8-sig")
        code = code_only(text)
        if "harness" in path.name.lower() or "Synthetic SDK only" in text:
            errors.append("TEST_HARNESS_SOURCE:"+str(path))
        for match in re.finditer(r'\b(?:(partial)\s+)?(?:class|interface)\s+(\w+)\b', code):
            partial, name = match.groups()
            if name not in MODEL_TYPES | {OWNER}:
                continue
            counts[name] += 1
            wanted = (path.resolve() in expected_paths and
                (path.name.startswith(OWNER) if name == OWNER else path.name == "ControlledSimOperationV3.cs"))
            if not wanted:
                errors.append("UNEXPECTED_PRODUCTION_TYPE:"+str(path)+":"+name)
            if name == OWNER and partial != "partial":
                errors.append("NONPARTIAL_OWNER:"+str(path))
    if counts[OWNER] != 3:
        errors.append("OWNER_PARTIAL_COUNT:"+str(counts[OWNER]))
    for name in MODEL_TYPES:
        if counts[name] != 1:
            errors.append("MODEL_TYPE_COUNT:"+name+":"+str(counts[name]))
    # The manifest hashes the entire byte stream, including BOM/newlines/suffixes.
    # Declaration inspection supplements this check; it never relaxes identity.
    for row in rows:
        path = Path(row["destination"])
        if row["deployed_sha256"] is None:
            errors.append("MISSING_SOURCE:"+str(path))
            continue
        if row["deployed_sha256"] != row["expected_sha256"]:
            errors.append("SOURCE_SHA256_MISMATCH:"+str(path))
    try:
        tree = ET.parse(project)
    except (ET.ParseError, OSError):
        errors.append("PROJECT_XML_INVALID_OR_UNREADABLE")
        return {"phase": "PRE_DEPLOYMENT_SOURCE_GATE", "ready": False, "errors": errors, "manifest": rows}
    includes = []
    parents = {child: parent for parent in tree.iter() for child in parent}
    active_security = False
    for element in tree.iter():
        if element.tag.split("}")[-1] != "Reference":
            continue
        # Removal/update/exclusion can invalidate an otherwise unconditional
        # reference. Do not guess at properties, wildcards or evaluation order.
        if any(name in element.attrib for name in ("Remove", "Update", "Exclude")):
            errors.append("REFERENCE_MODIFICATION_REQUIRES_REVIEW")
        if element.attrib.get("Include", "").split(",")[0] != "System.Security":
            continue
        group = parents.get(element)
        root = tree.getroot()
        if (group is None or group.tag.split("}")[-1] != "ItemGroup" or parents.get(group) is not root
                or root.tag.split("}")[-1] != "Project"
                or any("Condition" in node.attrib for node in (element, group, root))):
            errors.append("DPAPI_REFERENCE_NOT_PROVABLY_ACTIVE:System.Security")
        elif set(element.attrib) != {"Include"} or len(element):
            # Require the plain framework reference, not a HintPath/alias or
            # metadata that could redirect or exclude it from compilation.
            errors.append("DPAPI_REFERENCE_METADATA_REQUIRES_REVIEW:System.Security")
        else:
            active_security = True
    if not active_security:
        errors.append("DPAPI_FRAMEWORK_REFERENCE_MISSING_OR_INACTIVE:System.Security")
    for element in tree.iter():
        if element.tag.split("}")[-1] == "Compile" and "Include" in element.attrib:
            value = element.attrib["Include"]
            parent = element
            while parent is not None:
                if "Condition" in parent.attrib:
                    errors.append("CONDITIONAL_COMPILE_INCLUDE:"+value)
                parent = parents.get(parent)
            if any(c in value for c in "*?$;"):
                errors.append("UNRESOLVED_COMPILE_INCLUDE:"+value)
            else:
                includes.append((project.parent / value.replace("\\", "/")).resolve())
        if element.tag.split("}")[-1] == "Compile" and ("Remove" in element.attrib or "Exclude" in element.attrib):
            errors.append("COMPILE_EXCLUSION_REQUIRES_REVIEW")
        if element.tag.split("}")[-1] == "Reference" and element.attrib.get("Include", "").split(",")[0] == "NinjaTrader.Custom":
            errors.append("STALE_CUSTOM_ASSEMBLY_REFERENCE")
    for path in expected_paths:
        if includes.count(path) != 1:
            errors.append("PROJECT_INCLUDE_COUNT:"+str(path)+":"+str(includes.count(path)))
    main = (repo / "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs").read_text()
    for flag in ("NATIVE_SUBMIT_ENABLED", "AUTO_RETRY_ALLOWED"):
        if not re.search(r'\bconst\s+bool\s+'+flag+r'\s*=\s*false\s*;', code_only(main)):
            errors.append("SAFETY_CONSTANT:"+flag)
    return {"phase": "PRE_DEPLOYMENT_SOURCE_GATE", "ready": not errors, "errors": errors, "manifest": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("manifest", "pre-deployment", "post-compile"), required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--custom", type=Path, required=True)
    parser.add_argument("--project", type=Path)
    args = parser.parse_args(argv)
    if args.phase != "manifest" and args.project is None:
        parser.error("--project is required for destination and post-compile checks")
    if args.phase == "manifest":
        result = {"phase": "REPOSITORY_MANIFEST", "status": "INVENTORY_ONLY", "manifest": manifest(args.repo, args.custom)}
    else:
        result = verify(args.repo, args.custom, args.project)
        if args.phase == "post-compile":
            result["phase"] = "POST_NINJASCRIPT_COMPILE_GATE"
            result["ready"] = False
            result["errors"].append("MANUAL_COMMISSIONING_REQUIRED:GENERATED_SOURCE_AND_NATIVE_BUILD")
    print(json.dumps(result, indent=2))
    return 0 if result.get("ready", args.phase == "manifest") else 1


if __name__ == "__main__":
    raise SystemExit(main())
