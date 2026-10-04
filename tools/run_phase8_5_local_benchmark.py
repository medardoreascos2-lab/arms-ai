"""Run the controlled Phase 8.5B benchmark against the loopback Ollama server."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.medar.phase8_5_local_runtime_benchmark import run_benchmark, write_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run_benchmark(args.endpoint)
    path = write_report(report, args.output)
    print(json.dumps({"output": str(path), "quality_gate": report["quality_gate"], "summary": report["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())