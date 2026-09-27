"""Explicit commissioning publication; no startup hook or native interaction.

Run as the NinjaTrader Windows user with the approved backend APISettings
environment. No risk, freshness, or recovery values are supplied by this tool.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json

from backend.accounts.sim_native_account_v3 import SimNativeAccountV3, digest
from backend.services import sim_native_authority_v3 as authority
from backend.services.sim_admission_envelope_v3 import utc_us
from backend.services.sim_native_runtime_v3 import build_native_sim_runtime

COMMISSIONING_VALIDITY_US = 24 * 60 * 60 * 1_000_000


def canonical_paths():
    root = authority.safe_path(authority.authority_root() / "runtime", authority=True)
    names = ("commands", "activations", "state", "reconciliation")
    return {field: authority.safe_path(root / name, authority=True)
            for field, name in zip(authority.PATH_FIELDS, names)}


def _no_runtime_evidence():
    raise RuntimeError("commissioning publisher has no trading runtime evidence")


def publish(*, configuration_generation, protection_timeout_us, recovery_timeout_us):
    # Complete all input/runtime checks before creating directories or writing.
    key = authority.load_authority()  # Never provisions or rotates.
    binding = SimNativeAccountV3.load(execution_domain="SIM_NATIVE", provider="Simulator", native_account_name="Sim101")
    paths = canonical_paths()
    runtime = build_native_sim_runtime(binding=binding, namespace_root=paths["state_directory"],
        authority_key=key, runtime_evidence=_no_runtime_evidence,
        protection_timeout_us=protection_timeout_us, recovery_timeout_us=recovery_timeout_us)
    safety = runtime.store._durability.account_switch_safety
    risk_version = digest({"profile": binding.risk_profile_digest, "policy": digest(asdict(safety.settings))})
    if risk_version != runtime.lifecycle.native_admission_producer_v3.risk_version():
        raise ValueError("runtime admission risk version mismatch")
    root = authority.authority_root()
    prior = 0
    if any((root / name).exists() for name in ("controlled-v3-config.json", "controlled-v3-config.sig")):
        prior = int(authority.read_authenticated_config()["configuration_generation"])
    if type(configuration_generation) is not int or configuration_generation != prior + 1:
        raise ValueError("explicit next configuration generation required")
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
        authority._restrict_directory(path)
    issued_us = utc_us(datetime.now(timezone.utc))
    values = authority.publish_config(binding=binding, configuration_generation=configuration_generation,
        risk_version=risk_version, paths=paths, issued_us=issued_us,
        expires_us=issued_us+COMMISSIONING_VALIDITY_US, require_next_generation=True)
    verified = authority.verify_config(binding=binding, paths=paths, risk_version=risk_version,
        configuration_generation=configuration_generation, now_us=utc_us(datetime.now(timezone.utc)))
    if verified != values or verified["authority_id"] != authority.authority_id(key):
        raise ValueError("published configuration or authority changed during verification")
    return verified


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration-generation", required=True, type=int)
    parser.add_argument("--protection-timeout-us", required=True, type=int)
    parser.add_argument("--recovery-timeout-us", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        result = publish(configuration_generation=args.configuration_generation,
            protection_timeout_us=args.protection_timeout_us, recovery_timeout_us=args.recovery_timeout_us)
    except (ValueError, OSError):
        # Do not include arbitrary environment/exception content in operator logs.
        parser.exit(1, "CONFIG_PUBLICATION=FAILED_CLOSED; verify approved settings and existing authority/configuration\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
