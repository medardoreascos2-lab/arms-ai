"""Build a Phase 8.5D side-by-side report from two completed local soaks."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.medar.phase8_5_model_comparison import build_comparison


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--primary-monitor", required=True)
    parser.add_argument("--candidate-monitor", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = build_comparison(load(args.primary), load(args.candidate),
                              load(args.primary_monitor), load(args.candidate_monitor))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(path), "recommendation": result["recommendation"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())