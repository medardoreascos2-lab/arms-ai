"""Offline clock-proof model. No clock reads, network, ingestion or execution.

Bounds are reviewer-supplied assumptions, NOT inferred from measured offsets.
Results apply only to the named operation window and monotonic clock epoch.
Nothing in the production runtime imports this module.
"""
from dataclasses import dataclass


OPERATIONS = ("MARKET_ANALYSIS", "PAPER", "NEWS", "SIM", "LIVE")


def integer(value, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError("INVALID_INTEGER_BOUND")
    return value


def text_identity(value):
    if type(value) is not str or not value.strip():
        raise ValueError("INVALID_EVIDENCE_IDENTITY")
    return value


@dataclass(frozen=True)
class Interval:
    low: int
    high: int

    def __post_init__(self):
        integer(self.low)
        integer(self.high)
        if self.low > self.high:
            raise ValueError("REVERSED_INTERVAL")


@dataclass(frozen=True)
class ReferenceBound:
    reference: str
    independence_group: str
    error_us: int
    provenance: str


@dataclass(frozen=True)
class ReviewedBounds:
    epoch: str
    valid_from_mono_us: int
    valid_until_mono_us: int
    rate_error_ppb: int  # Reviewed bound on BOTH monotonic rate and wall/mono drift.
    capture_error_us: int  # Includes timestamp quantization and paired-read error.
    references: tuple[ReferenceBound, ...]
    provenance: str


@dataclass(frozen=True)
class Sample:
    reference: str
    epoch: str
    host_send_us: int
    host_receive_us: int
    mono_send_us: int
    mono_receive_us: int
    reference_receive_us: int
    reference_send_us: int
    origin_verified: bool
    synchronized: bool


@dataclass(frozen=True)
class WindowsState:
    epoch: str
    observed_mono_us: int
    last_sync_mono_us: int  # Independently mapped, not a naive wall-time subtraction.
    running: bool
    automatic: bool
    source: str
    state: str
    last_error: int


@dataclass(frozen=True)
class OperationWindow:
    operation: str
    valid_utc: Interval
    end_inclusive: bool
    provenance: str  # Reviewed derivation: calendar/news/freshness intersection.


def drift(elapsed_us, bounds):
    """Outward rounding: never shrink a safety envelope by truncation."""
    return (abs(elapsed_us) * bounds.rate_error_ppb + 999_999_999) // 1_000_000_000


def inside(interval, window, end_inclusive=True):
    return (interval.low >= window.low and
            (interval.high <= window.high if end_inclusive else interval.high < window.high))


def boundary_proof(*, kind, close_label_us, event_utc, receipt_utc, now_utc, maximum_age_us):
    """Offline sufficient conditions only; never admits/queues/deduplicates a row.

    Source labels and each interval's provenance must be proved separately.
    Independent interval extremes deliberately sacrifice availability for safety.
    """
    integer(close_label_us)
    integer(maximum_age_us, 1)
    if close_label_us % 60_000_000 or kind not in ("FORMING", "CLOSED"):
        return "UNKNOWN"
    if any(type(x) is not Interval for x in (event_utc, receipt_utc, now_utc)):
        return "UNKNOWN"
    boundary = close_label_us - (60_000_000 if kind == "FORMING" else 0)
    lifetime = maximum_age_us + (60_000_000 if kind == "FORMING" else 0)
    if (event_utc.low < boundary or event_utc.high > boundary + lifetime
            or receipt_utc.low < event_utc.high or now_utc.low < receipt_utc.high
            or receipt_utc.high - event_utc.low > maximum_age_us
            or now_utc.high - receipt_utc.low > maximum_age_us
            or now_utc.high - boundary > lifetime):
        return "UNKNOWN"
    return "PROVEN_TIME_CONDITIONS_ONLY"


def assess(*, samples, bounds, windows, windows_state, epoch, host_now_us,
           mono_now_us, horizon_us=0):
    """Fail-closed, operation-specific clock readiness; never runtime authority.

    The caller supplies an explicitly reviewed trust/bounds object. A string
    provenance is an audit reference, not cryptographic verification. No default
    or production reviewer exists in this sprint, so actual host proof is UNKNOWN.
    """
    result = dict(schema="arms.clock-preflight.offline.v1", status="UNKNOWN", reasons=[],
                  clock_ready={op: False for op in OPERATIONS}, runtime_readiness_granted=False,
                  broker_order_calls=0, account_access=False, execution_authority=False)
    try:
        if type(bounds) is not ReviewedBounds:
            raise ValueError("REVIEWED_ERROR_AND_DRIFT_BOUNDS_MISSING")
        for value in (bounds.provenance, bounds.epoch, epoch):
            text_identity(value)
        if not bounds.provenance or not bounds.epoch or bounds.epoch != epoch:
            raise ValueError("UNREVIEWED_OR_CHANGED_CLOCK_EPOCH")
        for v in (bounds.valid_from_mono_us, bounds.valid_until_mono_us,
                  bounds.rate_error_ppb, bounds.capture_error_us, mono_now_us, horizon_us):
            integer(v, 0)
        integer(host_now_us)
        if bounds.rate_error_ppb >= 1_000_000_000:
            raise ValueError("INVALID_RATE_BOUND")
        if not bounds.valid_from_mono_us <= mono_now_us <= mono_now_us+horizon_us <= bounds.valid_until_mono_us:
            raise ValueError("BOUND_VALIDITY_EXPIRED_OR_HORIZON_UNPROVEN")
        refs = {}
        for ref in bounds.references:
            if (type(ref) is not ReferenceBound or not ref.reference or not ref.independence_group
                    or not ref.provenance or ref.reference in refs):
                raise ValueError("INVALID_REFERENCE_REVIEW")
            for value in (ref.reference, ref.independence_group, ref.provenance):
                text_identity(value)
            integer(ref.error_us, 0)
            refs[ref.reference] = ref
        if len({r.independence_group for r in refs.values()}) < 2:
            raise ValueError("INDEPENDENT_REFERENCES_MISSING")
        ws = windows_state
        if (type(ws) is not WindowsState or ws.epoch != epoch or ws.running is not True
                or ws.automatic is not True or ws.source not in refs or ws.state not in ("Hold", "Sync")
                or type(ws.last_error) is not int or ws.last_error != 0):
            raise ValueError("WINDOWS_STATE_UNKNOWN_OR_UNHEALTHY")
        integer(ws.last_sync_mono_us, 0)
        integer(ws.observed_mono_us, 0)
        if not bounds.valid_from_mono_us <= ws.last_sync_mono_us <= ws.observed_mono_us <= mono_now_us:
            raise ValueError("SYNC_FRESHNESS_UNPROVEN")
        by_ref = {key: [] for key in refs}
        intervals = []
        ages = []
        for s in samples:
            if (type(s) is not Sample or s.reference not in refs or s.epoch != epoch
                    or s.origin_verified is not True or s.synchronized is not True):
                raise ValueError("INVALID_OR_UNTRUSTED_SAMPLE")
            for v in (s.host_send_us, s.host_receive_us, s.reference_receive_us, s.reference_send_us):
                integer(v)
            integer(s.mono_send_us, 0)
            integer(s.mono_receive_us, 0)
            if not bounds.valid_from_mono_us <= s.mono_send_us <= s.mono_receive_us <= mono_now_us:
                raise ValueError("SAMPLE_AGE_OR_EPOCH_INVALID")
            elapsed = s.mono_receive_us-s.mono_send_us
            age = mono_now_us-s.mono_receive_us
            precision = bounds.capture_error_us
            if (s.reference_send_us < s.reference_receive_us
                    or abs((s.host_receive_us-s.host_send_us)-elapsed) > drift(elapsed,bounds)+2*precision
                    or abs((host_now_us-s.host_receive_us)-age) > drift(age,bounds)+2*precision):
                raise ValueError("HOST_STEP_OR_SAMPLE_TIMING_INVALID")
            ref_error = refs[s.reference].error_us
            # All RTT may be on either path. Never assume symmetric routing.
            low = s.reference_send_us-ref_error-precision
            high = s.reference_receive_us+elapsed+drift(elapsed,bounds)+ref_error+precision
            uncertainty = drift(age,bounds)+2*precision
            intervals.append(Interval(low+age-uncertainty, high+age+uncertainty))
            by_ref[s.reference].append(s.mono_receive_us)
            ages.append(age)
        if any(len(set(v)) < 2 for v in by_ref.values()):
            raise ValueError("TWO_DISTINCT_SAMPLES_PER_REFERENCE_REQUIRED")
        if max(i.low for i in intervals) > min(i.high for i in intervals):
            raise ValueError("REFERENCE_DISAGREEMENT_OR_UNBOUNDED_DRIFT")
        # Hull, not a selected best offset or majority vote. A retained outlier
        # can only widen uncertainty/block readiness, never improve the verdict.
        utc = Interval(min(i.low for i in intervals), max(i.high for i in intervals))
        projected = Interval(utc.low, utc.high+horizon_us+drift(horizon_us,bounds))
        seen = set()
        for w in windows:
            if (type(w) is not OperationWindow or w.operation not in OPERATIONS or not w.provenance
                    or type(w.end_inclusive) is not bool or type(w.valid_utc) is not Interval
                    or w.operation in seen):
                raise ValueError("INVALID_OPERATION_WINDOW")
            seen.add(w.operation)
            text_identity(w.provenance)
            result["clock_ready"][w.operation] = inside(projected,w.valid_utc,w.end_inclusive)
        result.update(status="BOUNDED_OFFLINE_ONLY", utc_interval_us=[utc.low,utc.high],
                      offset_interval_us=[utc.low-host_now_us,utc.high-host_now_us],
                      horizon_utc_interval_us=[projected.low,projected.high],
                      oldest_sample_age_us=max(ages), synchronization_age_us=mono_now_us-ws.last_sync_mono_us)
        if not all(result["clock_ready"].values()):
            result["reasons"].append("UNPROVEN_OR_BOUNDARY_CROSSING_OPERATION_WINDOWS")
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        result["status"] = "UNKNOWN"
        result["clock_ready"] = {op: False for op in OPERATIONS}
        result["reasons"] = [str(error) if type(error) is ValueError else "MALFORMED_EVIDENCE"]
    return result
