"""Offline-only private resolution of portable certification identities.

No production module imports this helper. Original input digests remain mandatory.
The private mapping and resolved runtime manifests must never enter Git history.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess

IDENTITY = re.compile(
    r"<(?:ARMS_AI_SOURCE_EXPORT|ARMS_AI_PROVENANCE_CONTROL|"
    r"ARMS_AI_BASELINE_SOURCE|NINJATRADER_TEMPLATE)>/[^/\\\\:]+"
)
DIGEST_FIELDS = {
    "source_file": "source_sha256", "source_path": "source_sha256",
    "control_path": "control_sha256", "path": "sha256",
}


def digest(path):
    checksum = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def resolve_evidence(value, mapping):
    """Return a resolved copy; reject missing identities and changed input bytes."""
    verified = set()

    def walk(item):
        if isinstance(item, list):
            return [walk(child) for child in item]
        if not isinstance(item, dict):
            if isinstance(item, str) and item.startswith("<"):
                raise ValueError("unrecognized or misplaced evidence identity")
            return item
        result = {}
        for key, child in item.items():
            if isinstance(child, str) and child.startswith("<"):
                if not IDENTITY.fullmatch(child) or child.rsplit("/", 1)[1] in {".", ".."}:
                    raise ValueError("invalid evidence identity")
                hash_field = DIGEST_FIELDS.get(key)
                expected = item.get(hash_field)
                if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                    raise ValueError("source digest required for evidence identity")
                actual = mapping.get(child)
                if not isinstance(actual, str) or not Path(actual).is_absolute():
                    raise ValueError("explicit absolute private mapping required")
                cache_key = (actual, expected)
                if cache_key not in verified:
                    try:
                        matches = digest(actual) == expected
                    except OSError:
                        raise ValueError("private evidence input unavailable") from None
                    if not matches:
                        raise ValueError("private evidence input hash mismatch")
                    verified.add(cache_key)
                result[key] = actual
            else:
                result[key] = walk(child)
        return result

    return walk(value)


def resolve_from_environment(value):
    """Resolve only portable identities; legacy local inputs retain their behavior."""
    def has_identity(item):
        if isinstance(item, dict):
            return any(has_identity(v) for v in item.values())
        if isinstance(item, list):
            return any(has_identity(v) for v in item)
        return isinstance(item, str) and item.startswith("<")

    if not has_identity(value):
        return value
    location = os.environ.get("ARMS_AI_PRIVATE_PATH_MAP")
    if not location:
        raise ValueError("ARMS_AI_PRIVATE_PATH_MAP is required for portable evidence")
    with Path(location).open(encoding="utf-8") as stream:
        mapping = json.load(stream)
    if not isinstance(mapping, dict) or not isinstance(mapping.get("paths"), dict):
        raise ValueError("private mapping must contain a paths object")
    return resolve_evidence(value, mapping["paths"])


def private_runtime_manifest(canonical_manifest):
    """Materialize an ignored local manifest for the existing production --manifest."""
    canonical = Path(canonical_manifest)
    original = json.loads(canonical.read_text(encoding="utf-8"))
    resolved = resolve_from_environment(original)
    if resolved == original:
        return canonical
    root = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()).resolve()
    private = root / ".arms-dev" / "private-manifests"
    payload = (json.dumps(resolved, indent=2, allow_nan=False) + "\n").encode("utf-8")
    output = private / (sha256(payload).hexdigest() + ".json")
    if not output.resolve().is_relative_to(root / ".arms-dev"):
        raise ValueError("private manifest directory must stay inside ignored local storage")
    relative = output.relative_to(root).as_posix()
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", relative], cwd=root
    )
    if ignored.returncode != 0:
        raise ValueError("resolved manifest output must be ignored and untracked")
    private.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as stream:
            stream.write(payload)
    except FileExistsError:
        if output.read_bytes() != payload:
            raise ValueError("private manifest collision") from None
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--mapping", required=True)
    args = parser.parse_args()
    os.environ["ARMS_AI_PRIVATE_PATH_MAP"] = args.mapping
    print(private_runtime_manifest(args.manifest))
