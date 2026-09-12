"""Print the read-only inventory to stdout; there is deliberately no apply mode."""
import argparse
import json

from backend.services.legacy_state_inventory_v2 import LegacyStateInventoryV2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="Absolute workspace root")
    parser.add_argument("--state-path", action="append", default=[], help="Additional snapshot path; relative to workspace")
    parser.add_argument("--catalog-path", default="backend/config/accounts.json")
    args = parser.parse_args(argv)
    try:
        report = LegacyStateInventoryV2(workspace_root=args.workspace, state_paths=args.state_path,
                                        catalog_path=args.catalog_path).dry_run()
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))
    # Successful inventory does not imply migration eligibility.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
