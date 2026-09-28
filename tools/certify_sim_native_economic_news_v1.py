"""Explicit issuance of an independently reviewed news document; no acquisition.

The reviewed SHA256 pins the complete candidate, not just its asserted source
metadata. HMAC authenticates the ARMS issuer, not vendor accuracy/completeness.
Initial history creation needs --initialize-history and an empty news slot.
Thereafter the protected signed history is mandatory, including across restart.
Never delete/restore it to bypass rollback checks. Torn publication leaves a
lock and fails closed; operator recovery is separate. No automatic renewal.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json

from backend.accounts.sim_native_account_v3 import SimNativeAccountV3
from backend.services import sim_native_authority_v3 as auth
from backend.services import sim_native_economic_news_authority_v1 as news
from backend.services.sim_native_market_hours_authority_v1 import private_path
from backend.services.sim_native_commissioning_policy_v1 import load
from backend.services.sim_native_runtime_v3 import build_native_sim_runtime


def production_context():
    key, policy = auth.load_authority(), load()
    binding = SimNativeAccountV3.load(execution_domain='SIM_NATIVE',provider='Simulator',native_account_name='Sim101')
    root = auth.authority_root()
    paths = {f:root/'runtime'/n for f,n in zip(auth.PATH_FIELDS,('commands','activations','state','reconciliation'))}
    runtime = build_native_sim_runtime(binding=binding,namespace_root=root/'runtime/financial',authority_key=key,
        runtime_evidence=lambda: (_ for _ in ()).throw(RuntimeError('NO_ADMISSION_AUTHORITY')),
        api_settings=policy.api_settings,protection_timeout_us=policy.protection_timeout_us,recovery_timeout_us=policy.recovery_timeout_us)
    current = auth.read_authenticated_config()
    config = auth.verify_config(binding=binding,paths=paths,
        risk_version=runtime.lifecycle.native_admission_producer_v3.risk_version(),
        configuration_generation=int(current['configuration_generation']),now_us=news.utc_us(datetime.now(timezone.utc)))
    return config,policy.policy_id,key


def publish(candidate, expected_sha256, *, initialize_history=False):
    payload = news.read_bounded(candidate)
    news.require(hashlib.sha256(payload).hexdigest() == expected_sha256, 'REVIEWED_DIGEST_MISMATCH')
    config,policy_id,key = production_context()
    signature = news.sign(payload,key)
    value = news.verify(payload,signature,config=config,policy_id=policy_id,key=key,now=datetime.now(timezone.utc))
    folder = auth.safe_path(auth.authority_root()/'authority-inputs',authority=True)
    folder.mkdir(exist_ok=True)
    auth._restrict_directory(folder)
    private_path(folder)
    target,sig,history_path = [folder/n for n in news.FILES]
    lock = folder/news.LOCK
    # Exclusive lock serializes explicit issuers; GET refuses it. Failures retain it.
    with lock.open('xb'):
        if history_path.exists():
            news.require(not initialize_history, 'HISTORY_ALREADY_EXISTS')
            history = news.verify_history(news.read_bounded(history_path),config=config,policy_id=policy_id,key=key)
        else:
            news.require(initialize_history and not target.exists() and not sig.exists(), 'HISTORY_REQUIRED')
            history = dict(schema=news.HISTORY_SCHEMA,identity=news.identity(config,policy_id,key),entries=[])
        row = news.entry(value,payload)
        if history['entries']:
            news.require(all(e['snapshot_version'] != row['snapshot_version'] for e in history['entries']), 'VERSION_REUSE')
            news.require(row['issued_us'] > history['entries'][-1]['issued_us'], 'VERSION_ROLLBACK')
        history['entries'].append(row)
        history_raw = news.history_wire(history,key)
        news.verify_history(history_raw,config=config,policy_id=policy_id,key=key)
        # Advance the floor first: a crash cannot leave an older package usable.
        auth._atomic(history_path,history_raw)
        auth._atomic(target,payload)
        auth._atomic(sig,signature)
        current,policy,current_key = production_context()
        news.require(current == config and policy == policy_id and current_key == key, 'CONFIG_CHANGED')
        reread = news.read_bounded(target)
        news.require(reread == payload and news.read_bounded(history_path) == history_raw, 'PUBLICATION_CHANGED')
        news.verify(reread,news.read_bounded(sig),config=current,policy_id=policy,key=current_key,now=datetime.now(timezone.utc))
    lock.unlink()
    return dict(schema=news.SCHEMA,snapshot_version=value['snapshot_version'],sha256=row['sha256'],
                issued_us=value['issued_us'],expires_us=value['expires_us'],news_policy_id=news.NEWS_POLICY_ID)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--sha256',required=True,help='Independently reviewed full canonical candidate SHA256')
    parser.add_argument('--initialize-history',action='store_true')
    args = parser.parse_args(argv)
    try:
        result = publish(args.candidate,args.sha256,initialize_history=args.initialize_history)
    except (ValueError,OSError,TypeError,KeyError,RuntimeError):
        parser.exit(1,'NEWS_PUBLICATION=FAILED_CLOSED; retain artifacts for operator review\n')
    print(json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    main()
