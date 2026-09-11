"""Read contract for precomputed strategy intelligence stored by a completed job.

The executor's existing result store is the trust boundary, not request input.
A publishable result is a JSON dict with ``report`` (the dashboard fields) and
``provenance``: job_id, strategy_id, strategy_version, dataset_id, dataset_sha256,
generated_at, source_kind=HISTORICAL_BACKTEST and report_sha256. The report hash
uses UTF-8 JSON with sort_keys=True, separators=(",", ":"), allow_nan=False.

These references permit auditing the producing job, dataset and strategy; a hash
checks report integrity, not the truth of a producer's claims. Existing V1/V2
results without these references cannot be promoted to verified reports. No
producer is added here, and no report is calculated, repaired or saved on read.
"""
from datetime import datetime
from hashlib import sha256
import json
import math
import re

from backend.backtesting.backtesting_job_v2 import BacktestingJobStatusV2


def _unavailable(reason):
    # Unknown measurements must not masquerade as measured zeroes.
    return {
        "status": "UNAVAILABLE",
        "data_status": reason,
        "source": None,
        "strategy_status": "UNAVAILABLE",
        "certification": {"tests": None, "passed": None, "failed": None},
        "metrics": {
            "average_score": None, "average_probability": None,
            "buy_signals": None, "sell_signals": None, "no_trade": None,
        },
        "performance": {"trades": None, "win_rate": None, "average_rr": None},
    }


def _timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("Timestamp requires timezone")
    return parsed


def _has_provenance(provenance, job, report):
    if type(provenance) is not dict:
        return False
    required = (
        "job_id", "strategy_id", "strategy_version", "dataset_id",
        "dataset_sha256", "generated_at", "source_kind", "report_sha256",
    )
    if any(type(provenance.get(key)) is not str or not provenance[key].strip()
           for key in required):
        return False
    if (provenance["job_id"] != job.job_id
            or provenance["source_kind"] != "HISTORICAL_BACKTEST"
            or not re.fullmatch(r"[0-9a-f]{64}", provenance["dataset_sha256"])):
        return False
    try:
        generated_at = _timestamp(provenance["generated_at"])
        if not job.started_at <= generated_at <= job.finished_at:
            return False
        encoded = json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return False
    return sha256(encoded).hexdigest() == provenance["report_sha256"]


def _complete_report(report):
    if type(report) is not dict or report.get("strategy_status") not in (
        "CERTIFIED", "REJECTED",
    ):
        return False
    # Keep the original dashboard contract, without inventing absent metrics.
    fields = {
        "certification": ("tests", "passed", "failed"),
        "metrics": ("average_score", "average_probability", "buy_signals",
                    "sell_signals", "no_trade"),
        "performance": ("trades", "win_rate", "average_rr"),
    }
    for section, names in fields.items():
        values = report.get(section)
        if type(values) is not dict:
            return False
        for name in names:
            value = values.get(name)
            if type(value) not in (int, float):
                return False
            if type(value) is float and not math.isfinite(value):
                return False
    counts = [report["certification"][key] for key in ("tests", "passed", "failed")]
    counts.append(report["performance"]["trades"])
    counts += [report["metrics"][key] for key in ("buy_signals", "sell_signals", "no_trade")]
    if any(type(value) is not int or value < 0 for value in counts):
        return False
    certification = report["certification"]
    if (certification["tests"] <= 0
            or certification["passed"] + certification["failed"] != certification["tests"]
            or (report["strategy_status"] == "CERTIFIED") != (certification["failed"] == 0)):
        return False
    return 0 <= report["performance"]["win_rate"] <= 100


def project_strategy_intelligence(*, job_manager, job_executor):
    if job_manager is None or job_executor is None:
        return _unavailable("NO_DATA")
    jobs = job_manager.list_jobs()
    if not jobs:
        return _unavailable("NO_DATA")
    completed = [job for job in jobs if job.status == BacktestingJobStatusV2.COMPLETED]
    if not completed:
        return _unavailable("INCOMPLETE_REPORT")
    if any(not isinstance(job.finished_at, datetime)
           or job.finished_at.utcoffset() is None for job in completed):
        return _unavailable("UNVERIFIABLE_PROVENANCE")
    # Never silently substitute an older report for an invalid latest result.
    job = max(completed, key=lambda item: (item.finished_at, item.job_id))
    stored = job_executor.get_result(job.job_id)
    if stored is None:
        return _unavailable("INCOMPLETE_REPORT")
    # Do not invoke legacy summary/calculate/to_dict methods: they may generate
    # data or fill missing measurements with defaults.
    if type(stored) is not dict:
        return _unavailable("UNVERIFIABLE_PROVENANCE")
    try:
        snapshot = json.loads(json.dumps(stored, allow_nan=False))
    except (TypeError, ValueError, OverflowError):
        return _unavailable("INCOMPLETE_REPORT")
    report = snapshot.get("report")
    if not _complete_report(report):
        return _unavailable("INCOMPLETE_REPORT")
    provenance = snapshot.get("provenance")
    if not _has_provenance(provenance, job, report):
        return _unavailable("UNVERIFIABLE_PROVENANCE")
    return {
        **report,
        "status": "AVAILABLE",
        "data_status": "AVAILABLE",
        "source": provenance,
    }
