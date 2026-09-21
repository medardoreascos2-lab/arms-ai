"""Explicit health-first launcher. Help/import never starts native observation."""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Local ANALYSIS ONLY health-first startup; no execution authority.')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--start-analysis-only', action='store_true')
    mode.add_argument('--validate-offline', action='store_true', help='Exercise real local health gates, never arm, then shut down.')
    parser.add_argument('--installed-exporter', type=Path, required=True)
    parser.add_argument('--runtime-parent', type=Path, default=Path('.arms-dev/analysis-native').resolve())
    parser.add_argument('--port', type=int, default=18001)
    parser.add_argument('--frontend-port', type=int, default=13001)
    parser.add_argument('--bootstrap-evidence', type=Path, help='Reviewed sealed native history bundle; never a live input.')
    parser.add_argument('--bootstrap-sha256', help='Out-of-band reviewed SHA256 of the complete history bundle.')
    args = parser.parse_args()
    if bool(args.bootstrap_evidence) != bool(args.bootstrap_sha256):
        parser.error('bootstrap evidence and its reviewed SHA256 must be supplied together')
    if not all(1024 <= p <= 65535 for p in (args.port, args.frontend_port)) or args.port == args.frontend_port:
        parser.error('distinct local ports between 1024 and 65535 required')
    from tools.analysis_native_startup_v1 import run
    run(args)


if __name__ == '__main__':
    main()
