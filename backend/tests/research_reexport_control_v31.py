"""Sprint 04 source reproducibility audit; no dataset or execution admission.

Research-grade representation provenance and eligibility to mark/fill positions
are distinct contracts. Matching exports certify neither exchange prints nor
the executable nature of every stored observation.
"""
from hashlib import sha256
from pathlib import Path
import re


def compare_control(source_path, control_path, expected_source_sha256):
    source_path, control_path = Path(source_path), Path(control_path)
    source, control = source_path.read_bytes(), control_path.read_bytes()
    source_sha, control_sha = sha256(source).hexdigest(), sha256(control).hexdigest()
    if source_sha != expected_source_sha256.lower():
        raise ValueError("original source hash changed")
    old, new = source.splitlines(), control.splitlines()
    if not new or len(new) > len(old):
        raise ValueError("control must be a nonempty covered suffix")
    start = len(old)-len(new)
    if old[start:] != new:
        raise ValueError("control differs from original suffix")
    if (source_path.read_bytes(), control_path.read_bytes()) != (source, control):
        raise ValueError("file mutated during comparison")
    return {"source_path": str(source_path), "control_path": str(control_path),
            "source_sha256": source_sha, "control_sha256": control_sha,
            "source_rows": len(old), "control_rows": len(new),
            "suffix_start_1based": start+1, "shared_rows_exact": len(new),
            "shared_row_differences": 0, "byte_equal": source == control,
            "first_raw_label": new[0].decode().split(";")[0],
            "last_raw_label": new[-1].decode().split(";")[0],
            "whole_file_hash_difference_is_disagreement": False}


def _control_coverage(record, control):
    """Validate compare_control metadata; missing or contradictory proof is closed."""
    # The existing controls mapping supplies the contract identity. If a caller
    # also supplies an explicit identity, it must agree with that mapping key.
    if not isinstance(control, dict) or control.get("contract", record["contract"]) != record["contract"]:
        return None
    digest = record.get("sha256")
    if (type(digest) is not str or re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None
            or control.get("source_sha256") != digest):
        return None
    fields = ("suffix_start_1based", "control_rows", "source_rows", "shared_rows_exact", "shared_row_differences")
    if any(type(control.get(key)) is not int for key in fields):
        return None
    start, count, total = (control[key] for key in fields[:3])
    end = start + count - 1
    if (start < 1 or count < 1 or end != total
            or control["shared_rows_exact"] != count or control["shared_row_differences"] != 0):
        return None
    if "rows" in record and (type(record["rows"]) is not int or record["rows"] != total):
        return None
    return start, end


def annotate_exceptions(records, controls):
    """Preserve original evidence; flag direct reproduction versus inference."""
    output = []
    for record in records:
        control = controls.get(record["contract"])
        coverage = _control_coverage(record, control)
        for old in record["prior_exceptions"]:
            line = old.get("line")
            reproduced = bool(coverage is not None and type(line) is int
                              and coverage[0] <= line <= coverage[1])
            output.append({**old, "contract": record["contract"], "source_sha256": record["sha256"],
                           "session_anomaly": True, "directly_reproduced": reproduced,
                           "reproduction_basis": "EXACT_CONTROL_ROW" if reproduced else "COHORT_INFERENCE_ONLY",
                           "observation_disposition": "PRESERVE_AND_FLAG",
                           "execution_admissibility": "UNRESOLVED",
                           "not_a_normal_session_assertion": True})
    return output
