from pathlib import Path
import shutil

import pytest

from tools.sim_native_deployment_gate_v3 import SOURCES, verify

ROOT = Path(__file__).resolve().parents[2]


def installation(tmp_path):
    custom = tmp_path/"Custom"
    includes = []
    for name, folder in SOURCES.items():
        target = custom/folder/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/"integrations/ninjatrader"/name, target)
        includes.append(f'<Compile Include="{folder}/{name}" />')
    project = custom/"NinjaTrader.Custom.csproj"
    project.write_text('<Project><ItemGroup><Reference Include="System.Security" />'+"".join(includes)+"</ItemGroup></Project>")
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
        project.write_text(project.read_text().replace('<Reference Include="System.Security" />', ""))
    else:
        text = project.read_text()
        include = '<Compile Include="Indicators/ArmsSimNativeSubmitBridgeV2.cs" />'
        project.write_text(text.replace(include, "" if case == "missing_include" else include*2))
    assert not verify(ROOT, custom, project)["ready"]


def test_generated_wrapper_does_not_duplicate_owner(tmp_path):
    custom, project = installation(tmp_path)
    main = custom/"Indicators/ArmsSimNativeSubmitBridgeV2.cs"
    with main.open("a") as file:
        file.write("\n#region NinjaScript generated code\nnamespace NinjaTrader.NinjaScript.Indicators { public partial class Indicator { } }\n#endregion")
    assert verify(ROOT, custom, project)["ready"]
    with main.open("a") as file:
        file.write("\npublic partial class ArmsSimNativeSubmitBridgeV2 {}")
    assert not verify(ROOT, custom, project)["ready"]
