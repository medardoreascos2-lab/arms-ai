"""Run the versioned Phase 8.5C local model soak and safety audit."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.medar.phase8_5_local_model_soak import run_soak, write_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--model-digest", default=None)
    args = parser.parse_args()
    kwargs = {}
    if args.model_id is not None:
        kwargs["model_id"] = args.model_id
    if args.model_digest is not None:
        kwargs["model_digest"] = args.model_digest
    report = run_soak(args.endpoint, **kwargs)
    path = write_report(report, args.output)
    print(json.dumps({
        "output": str(path),
        "prompts_executed": report["prompts_executed"],
        "quality_gate": report["quality_gate"],
        "functional_quality_gate": report["functional_quality_gate"],
        "resource_gate": report["resource_gate"],
        "second_model_needed": report["second_model_needed"],
        "summary": report["summary"],
        "quality_by_category": report["quality_by_category"],
        "quality_by_profile": report["quality_by_profile"],
        "safety": report["safety"],
    }, indent=2))
    return 0 if report["quality_gate"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
