"""Explicit offline certification only. Does not capture, watch, attach or launch."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from backend.market_data.certified_bootstrap_v1 import certify_bootstrap
from backend.market_data.native_historical_bootstrap_v1 import SCHEMA, REVIEWED_EXPORTER_HASHES, report
from backend.market_data.fresh_native_adapter_v1 import local_path
from tools.certify_analysis_bootstrap_v1 import bounded_read


def build_bundle(history, seal, template, source):
    # Source bytes are the reviewed authored file, not an arbitrary installed wrapper.
    authored_hash = sha256(source.replace(b'\r\n', b'\n')).hexdigest()
    if authored_hash not in REVIEWED_EXPORTER_HASHES:
        raise ValueError('HISTORY_EXPORTER_SOURCE_CHANGED')
    raw = json.dumps(dict(schema=SCHEMA, authored_sha256=authored_hash,
        history_utf8=history.decode('utf-8'), seal_utf8=seal.decode('utf-8'),
        template_utf8=template.decode('utf-8')), separators=(',',':')).encode('utf-8')
    data = certify_bootstrap(raw, expected_sha256=sha256(raw).hexdigest())
    return raw, report(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('history','seal','template','exporter-source','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    raw, result = build_bundle(*(bounded_read(p.resolve()) for p in
        (args.history, args.seal, args.template, args.exporter_source)))
    with local_path(args.output.resolve()).open('xb') as handle:
        handle.write(raw)
    print(json.dumps(dict(status='OFFLINE_VALIDATED_REVIEW_PIN_BEFORE_USE', **result)))


if __name__ == '__main__':
    main()
