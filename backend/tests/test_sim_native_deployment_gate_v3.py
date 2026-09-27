from pathlib import Path
import hashlib
import json
import os
import shutil

import pytest

from tools.sim_native_deployment_gate_v3 import SOURCES, main as gate_main, verify
from tools import sim_native_deployment_gate_v3 as gate

ROOT = Path(__file__).resolve().parents[2]


def editor_reference():
    # Exact observed editor shape; Windows root is host-derived.
    path = Path(os.environ["WINDIR"])/"Microsoft.NET/Framework64/v4.0.30319/System.Security.dll"
    assert path.is_file()
    return '<Reference Include="System.Security"><HintPath>' + str(path) + '</HintPath></Reference>'


def test_exact_editor_hintpath_is_accepted(tmp_path):
    custom, project = installation(tmp_path)
    assert editor_reference() in project.read_text()
    before = project.read_bytes()
    result = verify(ROOT, custom, project)
    assert result["ready"], result["errors"]
    assert project.read_bytes() == before


@pytest.mark.parametrize("case", ["empty", "wrong_filename", "arbitrary", "repository", "custom", "traversal",
    "relative", "unc", "nonexistent", "reparse", "wrong_identity", "identity_failure"])
def test_framework_hintpath_authenticity(tmp_path, monkeypatch, case):
    approved = Path(os.environ["WINDIR"])/"Microsoft.NET/Framework64/v4.0.30319/System.Security.dll"
    path = str(approved)
    if case == "empty":
        path = ""
    elif case == "wrong_filename":
        path = str(approved.with_name("System.dll"))
    elif case in {"arbitrary", "repository", "custom"}:
        roots = {"arbitrary":tmp_path/"other", "repository":tmp_path/"repo", "custom":tmp_path/"NinjaTrader/bin/Custom"}
        alternate = roots[case]/"System.Security.dll"
        alternate.parent.mkdir(parents=True)
        # Even an exact copy of the real DLL is not an approved location.
        shutil.copyfile(approved, alternate)
        path = str(alternate)
    elif case == "traversal":
        path = str(approved.parent) + "\\..\\v4.0.30319\\System.Security.dll"
    elif case == "relative":
        path = "System.Security.dll"
    elif case == "unc":
        path = "\\\\localhost\\C$\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\System.Security.dll"
    elif case == "nonexistent":
        # Do not delete or alter the framework installation.
        original = Path.is_file
        monkeypatch.setattr(Path, "is_file", lambda p: False if p == approved else original(p))
    elif case == "reparse":
        original = Path.is_junction
        monkeypatch.setattr(Path, "is_junction", lambda p: p == approved.parent or original(p))
    else:
        from types import SimpleNamespace
        monkeypatch.setattr(gate.subprocess, "run", lambda *a, **kw: SimpleNamespace(
            returncode=1 if case == "identity_failure" else 0, stdout="Other.Assembly"))
    assert gate.framework_hintpath_error(path) is not None


def test_real_framework_identity_metadata_is_accepted():
    approved = Path(os.environ["WINDIR"])/"Microsoft.NET/Framework64/v4.0.30319/System.Security.dll"
    before = hashlib.sha256(approved.read_bytes()).hexdigest()
    assert gate.framework_hintpath_error(str(approved)) is None
    assert hashlib.sha256(approved.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("case", ["reference_false", "reference_unknown", "group_false", "group_unknown",
    "hint_false", "hint_unknown", "empty_hint", "aliases", "private", "specific_version", "interop",
    "custom_child", "reference_attribute", "hint_attribute", "nested", "duplicate_hint", "duplicate_valid",
    "duplicate_conflicting", "duplicate_conditional", "foreign_namespace", "text", "tail"])
def test_editor_reference_rejects_conditions_metadata_and_duplicates(tmp_path, case):
    custom, project = installation(tmp_path)
    reference = editor_reference()
    if case.startswith("reference_") and case != "reference_attribute":
        condition = "false" if case.endswith("false") else "'$(Unknown)' == 'yes'"
        reference = reference.replace('<Reference ', '<Reference Condition="' + condition + '" ')
    elif case.startswith("group_"):
        condition = "false" if case.endswith("false") else "'$(Unknown)' == 'yes'"
        reference = '</ItemGroup><ItemGroup Condition="' + condition + '">' + reference + '</ItemGroup><ItemGroup>'
    elif case.startswith("hint_") and case != "hint_attribute":
        condition = "false" if case.endswith("false") else "'$(Unknown)' == 'yes'"
        reference = reference.replace('<HintPath>', '<HintPath Condition="' + condition + '">')
    elif case == "empty_hint":
        reference = '<Reference Include="System.Security"><HintPath> </HintPath></Reference>'
    elif case in {"aliases", "private", "specific_version", "interop", "custom_child"}:
        name = {"aliases":"Aliases", "private":"Private", "specific_version":"SpecificVersion",
                "interop":"EmbedInteropTypes", "custom_child":"Unknown"}[case]
        reference = reference.replace('</Reference>', '<'+name+'>true</'+name+'></Reference>')
    elif case in {"reference_attribute", "hint_attribute"}:
        tag = 'Reference Include' if case == "reference_attribute" else 'HintPath'
        reference = reference.replace('<'+tag, '<'+tag.split()[0]+' Unknown="value"'+(' Include' if case == "reference_attribute" else ''))
    elif case == "nested":
        reference = reference.replace('</HintPath>', '<Nested /></HintPath>')
    elif case == "duplicate_hint":
        reference = reference.replace('</Reference>', '<HintPath>other.dll</HintPath></Reference>')
    elif case.startswith("duplicate_"):
        second = editor_reference()
        if case == "duplicate_conflicting":
            second = '<Reference Include="System.Security"><HintPath>other.dll</HintPath></Reference>'
        elif case == "duplicate_conditional":
            second = second.replace('<Reference ', '<Reference Condition="false" ')
        reference += second
    elif case == "foreign_namespace":
        reference = reference.replace('<HintPath>', '<HintPath xmlns="urn:unapproved">')
    elif case == "text":
        reference = reference.replace('<HintPath>', 'unknown<HintPath>')
    elif case == "tail":
        reference = reference.replace('</HintPath>', '</HintPath>unknown')
    project.write_text(project.read_text().replace(editor_reference(), reference))
    before = project.read_bytes()
    result = verify(ROOT, custom, project)
    assert not result["ready"]
    assert any(error.startswith("DPAPI_REFERENCE_") for error in result["errors"])
    assert not any("MISSING" in error for error in result["errors"])
    assert project.read_bytes() == before


def test_missing_hintpath_is_not_a_missing_reference(tmp_path):
    custom, project = installation(tmp_path)
    project.write_text(project.read_text().replace(editor_reference(), '<Reference Include="System.Security" />'))
    result = verify(ROOT, custom, project)
    assert not result["ready"]
    assert result["errors"] == ["DPAPI_REFERENCE_HINTPATH_MISSING:System.Security"]


@pytest.mark.parametrize("defect", ["D1", "D2", "D3"])
def test_review_defects_fail_closed(tmp_path, defect):
    custom, project = installation(tmp_path)
    main = custom/"Indicators/ArmsSimNativeSubmitBridgeV2.cs"
    if defect == "D1":
        main.write_bytes(main.read_bytes() + b"\n")
    elif defect == "D2":
        with main.open("a") as file:
            file.write("\n#region NinjaScript generated code\nnamespace Unapproved { public class ExtraExecutableCode { public static int Run() { return 1; } } }\n#endregion\n")
    else:
        project.write_text(project.read_text().replace(editor_reference(),
            '<Reference Include="System.Security" Condition="false" />'))
    result = verify(ROOT, custom, project)
    assert not result["ready"], f"{defect} was incorrectly accepted: {result['errors']}"


def installation(tmp_path):
    custom = tmp_path/"Custom"
    includes = []
    for name, folder in SOURCES.items():
        target = custom/folder/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/"integrations/ninjatrader"/name, target)
        includes.append(f'<Compile Include="{folder}/{name}" />')
    project = custom/"NinjaTrader.Custom.csproj"
    project.write_text('<Project><ItemGroup>'+editor_reference()+"".join(includes)+"</ItemGroup></Project>")
    return custom, project


def test_exact_four_sources_and_single_owner_composition(tmp_path):
    custom, project = installation(tmp_path)
    assert verify(ROOT, custom, project)["ready"]


@pytest.mark.parametrize("case", ["stale", "backup", "duplicate_model", "duplicate_partial", "harness", "missing_include", "double_include", "missing_source", "conditional", "excluded", "stale_reference", "missing_dpapi_reference"])
def test_deployment_rejects_ambiguous_sources(tmp_path, case):
    custom, project = installation(tmp_path)
    main = custom/"Indicators/ArmsSimNativeSubmitBridgeV2.cs"
    if case == "stale":
        main.write_text(main.read_text().replace("public partial class ArmsSimNativeSubmitBridgeV2", "public class ArmsSimNativeSubmitBridgeV2"))
    elif case in {"backup", "duplicate_partial"}:
        shutil.copyfile(main, main.with_name("old-owner.cs"))
    elif case == "duplicate_model":
        shutil.copyfile(custom/"AddOns/ControlledSimOperationV3.cs", custom/"AddOns/old-model.cs")
    elif case == "harness":
        (custom/"AddOns/native_bridge_v3_harness.cs").write_text("// Synthetic SDK only")
    elif case == "missing_source":
        main.unlink()
    elif case == "conditional":
        project.write_text(project.read_text().replace("<ItemGroup>", '<ItemGroup Condition="false">'))
    elif case == "excluded":
        project.write_text(project.read_text().replace("</ItemGroup>", '<Compile Remove="Indicators/ArmsSimNativeSubmitBridgeV2.cs" /></ItemGroup>'))
    elif case == "stale_reference":
        project.write_text(project.read_text().replace("</ItemGroup>", '<Reference Include="NinjaTrader.Custom" /></ItemGroup>'))
    elif case == "missing_dpapi_reference":
        project.write_text(project.read_text().replace(editor_reference(), ""))
    else:
        text = project.read_text()
        include = '<Compile Include="Indicators/ArmsSimNativeSubmitBridgeV2.cs" />'
        project.write_text(text.replace(include, "" if case == "missing_include" else include*2))
    assert not verify(ROOT, custom, project)["ready"]


def test_generated_wrapper_is_not_approved_pre_deployment_source(tmp_path):
    custom, project = installation(tmp_path)
    main = custom/"Indicators/ArmsSimNativeSubmitBridgeV2.cs"
    with main.open("a") as file:
        file.write("\n#region NinjaScript generated code\nnamespace NinjaTrader.NinjaScript.Indicators { public partial class Indicator { } }\n#endregion")
    assert not verify(ROOT, custom, project)["ready"]
    with main.open("a") as file:
        file.write("\npublic partial class ArmsSimNativeSubmitBridgeV2 {}")
    assert not verify(ROOT, custom, project)["ready"]


@pytest.mark.parametrize("name,folder", SOURCES.items())
@pytest.mark.parametrize("mutation", ["exact", "append_newline", "remove_newline", "line_endings", "whitespace", "bom", "character"])
def test_d1_exact_bytes_for_each_source(tmp_path, name, folder, mutation):
    custom, project = installation(tmp_path)
    target = custom/folder/name
    source = ROOT/"integrations/ninjatrader"/name
    original = source.read_bytes()
    changed = original
    if mutation == "append_newline":
        changed += b"\n"
    elif mutation == "remove_newline":
        assert original.endswith(b"\n")
        changed = original[:-1]
    elif mutation == "line_endings":
        changed = original.replace(b"\r\n", b"\n") if b"\r\n" in original else original.replace(b"\n", b"\r\n")
    elif mutation == "whitespace":
        changed += b" "
    elif mutation == "bom":
        assert not original.startswith(b"\xef\xbb\xbf")
        changed = b"\xef\xbb\xbf" + original
    elif mutation == "character":
        changed = original.replace(b"using System;", b"using Xystem;", 1)
    if mutation != "exact":
        assert changed != original
    target.write_bytes(changed)
    before = {p:p.read_bytes() for p in custom.rglob("*") if p.is_file()}
    result = verify(ROOT, custom, project)
    assert result["ready"] is (mutation == "exact")
    row = next(row for row in result["manifest"] if Path(row["destination"]).name == name)
    assert row["expected_sha256"] == hashlib.sha256(original).hexdigest()
    assert row["deployed_sha256"] == hashlib.sha256(changed).hexdigest()
    if mutation != "exact":
        assert any(error.startswith("SOURCE_SHA256_MISMATCH:") for error in result["errors"])
    assert source.read_bytes() == original
    assert before == {p:p.read_bytes() for p in custom.rglob("*") if p.is_file()}


@pytest.mark.parametrize("suffix", [
    "namespace Unapproved { public class ExtraExecutableCode { public static int Run() { return 1; } } }",
    "public void UnexpectedMethod() { }",
    "public void Mutate() { selectedAccount.Submit(orders); selectedAccount.Cancel(orders); selectedAccount.Flatten(instruments); }",
    "public partial class ArmsSimNativeSubmitBridgeV2 {}",
    "public class ControlledSimOperationV3 {}",
    "public class ControlledOperationV3 {}",
    "public class NativeTestHarness {}",
])
def test_d2_no_generated_suffix_is_ignored(tmp_path, suffix):
    custom, project = installation(tmp_path)
    main = custom/"Indicators/ArmsSimNativeSubmitBridgeV2.cs"
    changed = main.read_bytes() + ("\n#region NinjaScript generated code\n" + suffix + "\n#endregion\n").encode()
    main.write_bytes(changed)
    result = verify(ROOT, custom, project)
    assert not result["ready"]
    assert any(error.startswith("SOURCE_SHA256_MISMATCH:") for error in result["errors"])
    assert main.read_bytes() == changed


@pytest.mark.parametrize("case", ["missing", "typo", "comment", "false", "resolved_false", "unknown",
    "true_unproven", "inactive_group", "unknown_group", "unrelated_target", "choose", "removed",
    "metadata", "malformed"])
def test_d3_system_security_must_be_provably_active(tmp_path, case):
    custom, project = installation(tmp_path)
    text = project.read_text()
    reference = editor_reference()
    changes = {
        "missing": "",
        "typo": '<Reference Include="System.Securty" />',
        "comment": '<!--' + reference + '-->',
        "false": '<Reference Include="System.Security" Condition="false" />',
        "resolved_false": '<Reference Include="System.Security" Condition="\'Debug\' == \'Release\'" />',
        "unknown": '<Reference Include="System.Security" Condition="\'$(Unknown)\' == \'yes\'" />',
        "true_unproven": '<Reference Include="System.Security" Condition="true" />',
        "inactive_group": '</ItemGroup><ItemGroup Condition="false">' + reference + '</ItemGroup><ItemGroup>',
        "unknown_group": '</ItemGroup><ItemGroup Condition="\'$(Configuration)\' == \'Release\'">' + reference + '</ItemGroup><ItemGroup>',
        "unrelated_target": '</ItemGroup><Target Name="Unused"><ItemGroup>' + reference + '</ItemGroup></Target><ItemGroup>',
        "choose": '</ItemGroup><Choose><When Condition="false"><ItemGroup>' + reference + '</ItemGroup></When></Choose><ItemGroup>',
        "removed": reference + '<Reference Remove="System.Security" />',
        "metadata": '<Reference Include="System.Security"><HintPath>unapproved.dll</HintPath></Reference>',
    }
    text = '<Project><ItemGroup>' if case == "malformed" else text.replace(reference, changes[case])
    project.write_text(text)
    before = project.read_bytes()
    result = verify(ROOT, custom, project)
    assert not result["ready"]
    assert any(error.startswith(("DPAPI_", "REFERENCE_MODIFICATION_", "PROJECT_XML_")) for error in result["errors"])
    assert project.read_bytes() == before


@pytest.mark.parametrize("name,folder", SOURCES.items())
@pytest.mark.parametrize("case", ["missing", "wrong_destination"])
def test_missing_or_wrong_destination_for_every_source(tmp_path, name, folder, case):
    custom, project = installation(tmp_path)
    target = custom/folder/name
    if case == "missing":
        target.unlink()
    else:
        target.rename(custom/("Indicators" if folder == "AddOns" else "AddOns")/name)
    assert not verify(ROOT, custom, project)["ready"]


@pytest.mark.parametrize("flag", ["NATIVE_SUBMIT_ENABLED", "AUTO_RETRY_ALLOWED"])
def test_changed_safety_constant_rejected_in_source_and_destination(tmp_path, flag):
    custom, project = installation(tmp_path)
    main = custom/"Indicators/ArmsSimNativeSubmitBridgeV2.cs"
    main.write_text(main.read_text().replace("const bool " + flag + " = false;", "const bool " + flag + " = true;"))
    assert not verify(ROOT, custom, project)["ready"]
    # Even matching manifest/destination bytes cannot approve enabled constants.
    repo = tmp_path/"repo"
    source = repo/"integrations/ninjatrader"
    source.mkdir(parents=True)
    for name, folder in SOURCES.items():
        shutil.copyfile(custom/folder/name, source/name)
    result = verify(repo, custom, project)
    assert not result["ready"]
    assert "SAFETY_CONSTANT:" + flag in result["errors"]


def test_backup_must_be_outside_active_custom_tree(tmp_path):
    custom, project = installation(tmp_path)
    backup = tmp_path/"backup"
    shutil.copytree(custom, backup)
    assert verify(ROOT, custom, project)["ready"]
    shutil.copytree(backup, custom/"backup")
    assert not verify(ROOT, custom, project)["ready"]


@pytest.mark.parametrize("phase,exit_code", [("manifest", 0), ("pre-deployment", 0), ("post-compile", 1)])
def test_cli_phase_contracts(tmp_path, capsys, phase, exit_code):
    custom, project = installation(tmp_path)
    args = ["--phase", phase, "--repo", str(ROOT), "--custom", str(custom)]
    if phase != "manifest":
        args += ["--project", str(project)]
    assert gate_main(args) == exit_code
    result = json.loads(capsys.readouterr().out)
    if phase == "manifest":
        assert result["phase"] == "REPOSITORY_MANIFEST"
        assert result["status"] == "INVENTORY_ONLY"
        assert "ready" not in result
    elif phase == "pre-deployment":
        assert result["phase"] == "PRE_DEPLOYMENT_SOURCE_GATE"
        assert result["ready"]
    else:
        assert result["phase"] == "POST_NINJASCRIPT_COMPILE_GATE"
        assert not result["ready"]
        assert result["errors"] == ["MANUAL_COMMISSIONING_REQUIRED:GENERATED_SOURCE_AND_NATIVE_BUILD"]


@pytest.mark.parametrize("args", [[], ["--phase", "pre-deployment"], ["--phase", "post-compile"]])
def test_cli_requires_explicit_phase_and_project(tmp_path, args):
    with pytest.raises(SystemExit) as error:
        gate_main(["--repo", str(ROOT), "--custom", str(tmp_path), *args])
    assert error.value.code == 2
