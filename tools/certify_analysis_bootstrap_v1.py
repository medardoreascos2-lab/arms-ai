"""Explicit offline bundle creation/inspection. Never watches or starts a runtime."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from backend.market_data.certified_bootstrap_v1 import SCHEMA, MAX_BYTES, certify_bootstrap
from backend.market_data.exporter_identity_v1 import AUTHORED_SHA256, verify_exporter_source
from backend.market_data.fresh_native_adapter_v1 import local_path


def bounded_read(path):
    with local_path(path).open('rb') as handle:
        raw = handle.read(MAX_BYTES+1)
    if len(raw) > MAX_BYTES:
        raise ValueError('BOOTSTRAP_SIZE')
    return raw


def load_bootstrap(path, expected_sha256):
    return certify_bootstrap(bounded_read(path), expected_sha256=expected_sha256)


def main():
    parser = argparse.ArgumentParser(description='Offline sealed native history; output requires independent pin review before use.')
    parser.add_argument('--segment', nargs=3, action='append', required=True, metavar=('CANONICAL','TIMING','SEAL'))
    parser.add_argument('--exporter-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    verify_exporter_source(bounded_read(args.exporter_source.resolve()))
    segments = [dict(zip(('canonical_utf8','timing_utf8','seal_utf8'),
                        (bounded_read(Path(p).resolve()).decode('utf-8') for p in paths))) for paths in args.segment]
    raw = json.dumps(dict(schema=SCHEMA, authored_sha256=AUTHORED_SHA256, segments=segments),
                     separators=(',',':'), ensure_ascii=False).encode('utf-8')
    digest = sha256(raw).hexdigest()
    result = certify_bootstrap(raw, expected_sha256=digest)
    with local_path(args.output.resolve()).open('xb') as output:
        output.write(raw)
    print(json.dumps(dict(status='OFFLINE_VALIDATED_REVIEW_PIN_BEFORE_USE', sha256=digest,
                         bars=len(result.bars), source=result.source, cutoff=result.bars[-1].label,
                         source_gaps=result.gap_count, live_records=0, runtime_started=False)))


if __name__ == '__main__':
    main()
