"""Run the controlled Phase 8.5E long-context allocation stability study."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.medar.phase8_5_long_context_stability import run_study, write_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    def progress(event):
        print(json.dumps(event, separators=(",", ":")), flush=True)

    report = run_study(args.endpoint, progress=progress)
    path = write_report(report, args.output)
    print(json.dumps({
        "output": str(path),
        "status": report["qwen_9b_long_context_status"],
        "memory_leak_classification": report["memory_leak_classification"],
        "summary": report["summary"],
        "guard_recommendation": report["current_12_gib_guard_recommendation"],
        "recommended_initial_context": report["recommended_initial_context"],
        "recommended_max_context": report["recommended_max_context"],
    }, indent=2), flush=True)
    if report["qwen_9b_long_context_status"] == "PASS":
        return 0
    if report["qwen_9b_long_context_status"] == "STOP_RESOURCE_PRESSURE":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
