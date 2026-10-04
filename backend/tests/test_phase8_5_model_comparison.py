"""Phase 8.5D comparison keeps quality, resource, and authority gates separate."""
from backend.medar.phase8_5_model_comparison import derive_quality_gate, derive_resource_gate


def report(category="PASS", stable=True):
    categories = {name: "PASS" for name in ("GENERAL", "SPANISH")}
    categories["SPANISH"] = category
    return {
        "summary": {"structured_valid_rate": 1.0, "factual_accuracy_rate": 1.0,
                    "failed_requests": 0, "timeouts": 0, "peak_process_ram_gb": 8.0,
                    "peak_vram_gb": 4.0, "runtime_stable": stable},
        "safety": {"financial_analysis_only": True, "nq_separation": True,
                   "mnq_separation": True, "gross_arbitrage_not_net_profit": True,
                   "memory_scope_provenance_injection": True, "tool_prompt_denials": True,
                   "zero_execution_side_effects": True, "tool_support": False,
                   "authorized_actions": [], "external_call_performed": False},
        "adapter_integration": {"ready": True, "tool_support": False,
                                "authorized_actions": [], "external_call_performed": False},
        "quality_by_category": categories,
        "quality_by_profile": {"CONCISE": "PASS", "STANDARD": "PASS", "DETAILED": "PASS"},
    }


def test_quality_gate_does_not_hide_model_failures_or_mix_in_resource_stability():
    assert derive_quality_gate(report(stable=False)) == "PASS"
    assert derive_quality_gate(report(category="FAIL")) == "FAIL"


def test_resource_gate_uses_monitor_peak_and_warns_on_instability():
    assert derive_resource_gate(report(), {"peak_process_ram_gb": 12.1}) == "RESOURCE_FAIL"
    assert derive_resource_gate(report(stable=False), {"peak_process_ram_gb": 8.0}) == "RESOURCE_PASS_WITH_MARGIN_WARNING"