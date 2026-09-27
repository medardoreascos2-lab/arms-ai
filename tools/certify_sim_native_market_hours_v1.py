"""Explicit operator publication from a NEW observed native witness; no execution.

Run as the provisioned NinjaTrader user, after reviewing the fresh artifact and
its SHA256. No import/startup/GET creates a package. Existing packages are never
overwritten or renewed; their retirement requires a separate operator decision.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json

from backend.accounts.sim_native_account_v3 import SimNativeAccountV3
from backend.services import sim_native_authority_v3 as auth
from backend.services import sim_native_market_hours_authority_v1 as hours
from backend.services.sim_admission_envelope_v3 import utc_us
from backend.services.sim_native_commissioning_policy_v1 import load
from backend.services.sim_native_runtime_v3 import build_native_sim_runtime


def publish(witness, expected_sha256, days=3):
    now = datetime.now(timezone.utc)
    raw = hours.read_bounded(witness)
    hours.require(hashlib.sha256(raw).hexdigest() == expected_sha256, 'OPERATOR_WITNESS_DIGEST')
    template = hours.production_template()
    hours.review_witness(raw, template, issued=now)
    key = auth.load_authority()  # Existing CurrentUser key only; never provisions.
    policy = load()
    binding = SimNativeAccountV3.load(execution_domain='SIM_NATIVE', provider='Simulator', native_account_name='Sim101')
    root = auth.authority_root()
    paths = {f: root/'runtime'/n for f, n in zip(auth.PATH_FIELDS, ('commands','activations','state','reconciliation'))}
    runtime = build_native_sim_runtime(binding=binding, namespace_root=root/'runtime/financial', authority_key=key,
        runtime_evidence=lambda: (_ for _ in ()).throw(RuntimeError('NO_ADMISSION_AUTHORITY')),
        api_settings=policy.api_settings, protection_timeout_us=policy.protection_timeout_us,
        recovery_timeout_us=policy.recovery_timeout_us)
    current = auth.read_authenticated_config()
    config = auth.verify_config(binding=binding, paths=paths,
        risk_version=runtime.lifecycle.native_admission_producer_v3.risk_version(),
        configuration_generation=int(current['configuration_generation']), now_us=utc_us(now))
    now = datetime.now(timezone.utc)  # Freshness is rechecked after authority/config I/O.
    payload, signature = hours.build(raw, template, config=config, policy_id=policy.policy_id, key=key, now=now, days=days)
    hours.verify(payload, signature, template, config=config, policy_id=policy.policy_id, key=key, now=now)
    folder = auth.safe_path(root/'authority-inputs', authority=True)
    folder.mkdir(exist_ok=True)
    auth._restrict_directory(folder)
    hours.private_path(folder)
    # Exclusive writer plus create-only pair. A crash/torn pair fails closed.
    lock = folder/'market-hours-publish.lock'
    with lock.open('xb'):
        target, sig = folder/'market-hours-v1.json', folder/'market-hours-v1.sig'
        hours.require(not target.exists() and not sig.exists(), 'PACKAGE_ALREADY_EXISTS')
        auth._atomic(target, payload, create_only=True)
        auth._atomic(sig, signature, create_only=True)
        # Recheck config and wall time after I/O; no signature-only success.
        current = auth.verify_config(binding=binding, paths=paths,
            risk_version=runtime.lifecycle.native_admission_producer_v3.risk_version(),
            configuration_generation=int(config['configuration_generation']), now_us=utc_us(datetime.now(timezone.utc)))
        hours.require(current == config, 'CONFIG_CHANGED')
        value, _ = hours.verify(hours.read_bounded(target), hours.read_bounded(sig), hours.production_template(),
            config=current, policy_id=load().policy_id, key=auth.load_authority(), now=datetime.now(timezone.utc))
    # Failure deliberately retains the lock and any torn pair for operator review.
    lock.unlink()
    return {k: value[k] for k in ('schema','covered_dates','closed_dates','special_hours','issued_us','expires_us','calendar_witness_sha256')}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--witness', required=True)
    p.add_argument('--witness-sha256', required=True, help='SHA256 reviewed by the operator after fresh capture')
    p.add_argument('--days', type=int, choices=(1,2,3), default=3)
    args = p.parse_args(argv)
    try:
        result = publish(args.witness, args.witness_sha256, args.days)
    except (ValueError, OSError, TypeError, KeyError, RuntimeError):
        p.exit(1, 'MARKET_HOURS_PUBLICATION=FAILED_CLOSED; inspect fresh witness, approved identity and private paths\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
