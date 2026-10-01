"""Explicit, reviewed Current PAPER news publication. No runtime discovery."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from backend.services import current_paper_economic_news_authority_v1 as news
from backend.services import sim_native_authority_v3 as key_store
from backend.services.sim_native_market_hours_authority_v1 import (
    canonical, parse, private_path, require, read_bounded,
)


def publish(candidate, expected_sha256, *, base, root=None, initialize_authority=False,
            initialize_history=False, clock=None):
    """Publish only a separately reviewed canonical candidate and identity."""
    source = read_bounded(candidate)
    require(type(expected_sha256) is str and sha256(source).hexdigest() == expected_sha256,
        "REVIEWED_DIGEST_MISMATCH")
    require(canonical(parse(source)) == source, "CANDIDATE_NOT_CANONICAL")
    folder_root = key_store.safe_path(root, authority=True) if root is not None else news.default_root()
    if initialize_authority:
        key_store.provision_authority(folder_root)
    key = key_store.load_authority(folder_root)
    # Validate the supplied execution binding independently of the candidate.
    expected_identity = news.identity(base, key)
    now = clock or (lambda: datetime.now(timezone.utc))
    signature = news.sign(source, key)
    value = news.verify(source, signature, base=base, key=key, now=now())
    require(all(value[name] == expected for name, expected in expected_identity.items()),
        "PAPER_BINDING_INVALID")
    folder = key_store.safe_path(folder_root / "authority-inputs", authority=True)
    folder.mkdir(exist_ok=True)
    key_store._restrict_directory(folder)
    private_path(folder)
    target, sig, history_path = [folder / name for name in news.FILES]
    lock = folder / news.LOCK
    with lock.open("xb"):
        if history_path.exists():
            require(not initialize_history, "HISTORY_ALREADY_EXISTS")
            history = news.verify_history(read_bounded(history_path), base=base, key=key)
        else:
            require(initialize_history and not target.exists() and not sig.exists(), "HISTORY_REQUIRED")
            history = dict(schema=news.HISTORY_SCHEMA, identity=expected_identity, entries=[])
        row = news.entry(value, source)
        require(all(existing["snapshot_version"] != row["snapshot_version"]
            for existing in history["entries"]), "VERSION_REUSE")
        if history["entries"]:
            require(row["issued_us"] > history["entries"][-1]["issued_us"], "VERSION_ROLLBACK")
        history["entries"].append(row)
        history_raw = news.history_wire(history, key)
        news.verify_history(history_raw, base=base, key=key)
        # The signed rollback floor advances first. A partial publication fails closed.
        key_store._atomic(history_path, history_raw)
        key_store._atomic(target, source)
        key_store._atomic(sig, signature)
        require(key_store.load_authority(folder_root) == key, "AUTHORITY_CHANGED")
        require(read_bounded(target) == source and read_bounded(history_path) == history_raw,
            "PUBLICATION_CHANGED")
        news.verify(read_bounded(target), read_bounded(sig), base=base, key=key, now=now())
    lock.unlink()
    return dict(schema=news.SCHEMA, snapshot_version=value["snapshot_version"],
        sha256=row["sha256"], news_policy_id=news.NEWS_POLICY_ID)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--identity-sha256", required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--initialize-authority", action="store_true")
    parser.add_argument("--initialize-history", action="store_true")
    args = parser.parse_args(argv)
    try:
        identity_raw = read_bounded(args.identity)
        require(sha256(identity_raw).hexdigest() == args.identity_sha256,
            "REVIEWED_IDENTITY_DIGEST_MISMATCH")
        require(canonical(parse(identity_raw)) == identity_raw, "IDENTITY_NOT_CANONICAL")
        base = parse(identity_raw)
        result = publish(args.candidate, args.candidate_sha256, base=base, root=args.root,
            initialize_authority=args.initialize_authority,
            initialize_history=args.initialize_history)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        parser.exit(1, "CURRENT_PAPER_NEWS_PUBLICATION=FAILED_CLOSED; retain artifacts for review\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
