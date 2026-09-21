"""Bounded diagnostic evidence, never a clock setter or market admission owner.

Public UDP replies and observed rates are measurements, NOT ReviewedBounds.
Run explicitly with --output <new private file>. No runtime imports or startup.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import ctypes
from dataclasses import asdict
import ipaddress
import json
import os
from pathlib import Path
import socket
import statistics
import struct
import subprocess
import sys
import time
import uuid

from tools.clock_preflight_v1 import Interval, OperationWindow, Sample, assess, boundary_proof

REFERENCES = {"time.cloudflare.com": "cloudflare", "time.google.com": "google",
              "time.windows.com": "microsoft"}
NTP_EPOCH = 2_208_988_800
NS = 1_000_000_000


def pair():
    """Bracket a wall read; do not claim that bracket bounds wall-clock error."""
    before = time.perf_counter_ns()
    wall = time.time_ns()
    after = time.perf_counter_ns()
    return dict(host_ns=wall, mono_before_ns=before, mono_after_ns=after)


def encode_time(ns):
    seconds, fraction = divmod(ns, NS)
    seconds += NTP_EPOCH
    if not 0 < seconds < 2**32:
        raise ValueError("NTP_ERA_UNSUPPORTED")
    return struct.pack("!II", seconds, fraction * 2**32 // NS)


def decode_time(raw):
    seconds, fraction = struct.unpack("!II", raw)
    if seconds < NTP_EPOCH:
        raise ValueError("NTP_ERA_OR_ZERO_TIMESTAMP")
    return (seconds - NTP_EPOCH) * NS + fraction * NS // 2**32


def decode_reply(raw, origin, sent, received, reference, epoch):
    """Parse only plain NTPv3/v4 server replies; no extension/auth inference."""
    if len(raw) != 48:
        raise ValueError("PACKET_SIZE_OR_UNSUPPORTED_EXTENSION")
    if (raw[0] & 7) != 4 or ((raw[0] >> 3) & 7) not in (3, 4):
        raise ValueError("PACKET_MODE_OR_VERSION")
    if raw[0] >> 6 != 0 or not 1 <= raw[1] <= 15:
        raise ValueError("UNSYNCHRONIZED_LEAP_OR_KISS_OF_DEATH")
    if raw[24:32] != origin:
        raise ValueError("ORIGIN_MISMATCH")
    if reference not in REFERENCES or not epoch:
        raise ValueError("REFERENCE_OR_EPOCH")
    for p in (sent, received):
        if (any(type(p[k]) is not int for k in ("host_ns", "mono_before_ns", "mono_after_ns"))
                or p["mono_before_ns"] < 0 or p["mono_before_ns"] > p["mono_after_ns"]):
            raise ValueError("INVALID_PAIRED_READ")
    if sent["mono_after_ns"] > received["mono_before_ns"]:
        raise ValueError("MONOTONIC_ORDER")
    t1, t4 = sent["host_ns"], received["host_ns"]
    t2, t3 = decode_time(raw[32:40]), decode_time(raw[40:48])
    if t4 < t1 or t3 < t2:
        raise ValueError("REVERSED_WALL_OR_REFERENCE_TIME")
    # Outermost bracket includes send/read scheduling. No favorable RTT filter.
    elapsed = received["mono_after_ns"] - sent["mono_before_ns"]
    if t3 - t2 > elapsed:
        raise ValueError("REFERENCE_DURATION_EXCEEDS_LOCAL_ROUNDTRIP")
    root_delay = struct.unpack("!i", raw[4:8])[0] * NS // 65536
    dispersion = struct.unpack("!I", raw[8:12])[0] * NS // 65536
    sample = Sample(reference, epoch, t1 // 1000, t4 // 1000,
                    sent["mono_before_ns"] // 1000,
                    (received["mono_after_ns"] + 999) // 1000,
                    t2 // 1000, (t3 + 999) // 1000, True, True)
    return dict(status="MEASURED_NOT_ATTESTED", reference=reference,
                independence_group=REFERENCES[reference], epoch=epoch,
                sent=sent, received=received, sample=asdict(sample),
                packet_hex=raw.hex(), origin_echo_matched=True, authenticated=False,
                stratum=raw[1], leap_indicator=raw[0] >> 6,
                advertised_precision_exponent=struct.unpack("!b", raw[3:4])[0],
                advertised_root_delay_ns=root_delay,
                advertised_root_dispersion_ns=dispersion,
                reference_receive_ns=t2, reference_send_ns=t3,
                midpoint_offset_ns=((t2-t1)+(t3-t4)) // 2,
                roundtrip_bracket_ns=elapsed,
                wall_minus_mono_elapsed_ns=(t4-t1)-elapsed,
                # Conditional on exact reference and rate; NOT an absolute bound.
                conditional_receipt_utc_ns=[t3, t2+elapsed],
                conditional_asymmetry_radius_ns=(elapsed+1)//2,
                reviewed_reference_error_us=None, reviewed_rate_error_ppb=None)


def resolve(reference):
    """A timed child bounds otherwise potentially unbounded OS DNS lookup."""
    if reference not in REFERENCES:
        raise ValueError("REFERENCE_NOT_ALLOWLISTED")
    command = [sys.executable, "-B", "-c",
               "import socket,sys; print(socket.gethostbyname(sys.argv[1]))", reference]
    result = subprocess.run(command, capture_output=True, text=True, timeout=3, check=True)
    address = result.stdout.strip()
    ipaddress.IPv4Address(address)
    return address


def probe(reference, address, epoch, timeout=2):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            connection.settimeout(timeout)
            connection.connect((address, 123))  # Pins reply endpoint; not authentication.
            request = bytearray(48)
            request[0] = 0x23
            sent = pair()
            request[40:48] = encode_time(sent["host_ns"])
            connection.send(request)
            raw = connection.recv(1024)
            received = pair()
        return decode_reply(raw, request[40:48], sent, received, reference, epoch)
    except (OSError, ValueError, KeyError, struct.error):
        return dict(reference=reference, epoch=epoch, status="PROBE_INVALID_OR_UNAVAILABLE")


def clock_rate():
    if os.name != "nt":
        return dict(status="UNSUPPORTED")
    from ctypes import wintypes
    adjustment, increment, disabled = wintypes.DWORD(), wintypes.DWORD(), wintypes.BOOL()
    api = ctypes.WinDLL("kernel32", use_last_error=True).GetSystemTimeAdjustment
    api.argtypes = [ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                    ctypes.POINTER(wintypes.BOOL)]
    api.restype = wintypes.BOOL
    before = pair()
    if not api(ctypes.byref(adjustment), ctypes.byref(increment), ctypes.byref(disabled)):
        return dict(status="UNAVAILABLE")
    return dict(status="OBSERVED_ONLY", before=before, after=pair(),
                adjustment_100ns=adjustment.value, increment_100ns=increment.value,
                adjustment_disabled=bool(disabled.value),
                nominal_adjustment_ppm=((adjustment.value/increment.value)-1)*1e6
                if increment.value and not disabled.value else None)


def windows_snapshot():
    if os.name != "nt":
        return dict(status="UNSUPPORTED", last_sync_mono_us=None)
    commands = {
        "status": ["w32tm", "/query", "/status", "/verbose"],
        "peers": ["w32tm", "/query", "/peers", "/verbose"],
        "configuration": ["w32tm", "/query", "/configuration"],
        "service": ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                    "Get-CimInstance Win32_Service -Filter \"Name='W32Time'\" | "
                    "Select-Object State,StartMode | ConvertTo-Json -Compress"],
    }
    result = {"before": pair(), "last_sync_mono_us": None}
    for name, command in commands.items():
        try:
            query = subprocess.run(command, capture_output=True, text=True, timeout=5)
            result[name] = dict(exit_code=query.returncode, text=query.stdout[:12000])
        except (OSError, subprocess.TimeoutExpired):
            result[name] = dict(status="UNAVAILABLE")
    result["after"] = pair()
    return result


def summarize(records, now):
    """Descriptive statistics only. Lowest half by RTT is explicitly diagnostic."""
    result = {}
    for reference in REFERENCES:
        rows = [r for r in records if r["reference"] == reference
                and r["status"] == "MEASURED_NOT_ATTESTED"]
        if not rows:
            result[reference] = {"count": 0}
            continue
        rows.sort(key=lambda r:r["received"]["mono_after_ns"])
        low = sorted(rows, key=lambda r:r["roundtrip_bracket_ns"])[:max(1, len(rows)//2)]
        first, last = rows[0], rows[-1]
        duration = last["received"]["mono_after_ns"]-first["received"]["mono_after_ns"]
        host_change = last["received"]["host_ns"]-first["received"]["host_ns"]
        result[reference] = dict(count=len(rows), total_attempts=sum(r["reference"] == reference for r in records),
            low_delay_median_offset_ns=statistics.median(r["midpoint_offset_ns"] for r in low),
            all_sample_offset_range_ns=[min(r["midpoint_offset_ns"] for r in rows), max(r["midpoint_offset_ns"] for r in rows)],
            roundtrip_range_ns=[min(r["roundtrip_bracket_ns"] for r in rows),max(r["roundtrip_bracket_ns"] for r in rows)],
            oldest_sample_age_ns=now["mono_before_ns"]-first["received"]["mono_after_ns"],
            offset_change_ns=last["midpoint_offset_ns"]-first["midpoint_offset_ns"],
            observed_host_mono_rate_ppb=(host_change-duration)*NS/duration if duration else None,
            observed_offset_slope_ppb=(last["midpoint_offset_ns"]-first["midpoint_offset_ns"])*NS/duration if duration else None,
            reviewed_rate_bound_ppb=None)
    offsets = [r["low_delay_median_offset_ns"] for r in result.values() if r["count"]]
    return dict(references=result, representative_disagreement_ns=max(offsets)-min(offsets) if len(offsets)>1 else None,
                reference_bound_status="UNREVIEWED", drift_bound_status="EMPIRICAL_ONLY",
                absolute_uncertainty_status="UNKNOWN")


def analysis_window(kind, close_us, freshness_us, session_start_us, session_end_us, provenance):
    """Only a supplied, reviewed ordinary minute/session. No calendar invention."""
    values = (close_us, freshness_us, session_start_us, session_end_us)
    if (any(type(v) is not int for v in values) or freshness_us <= 0
            or close_us % 60_000_000 or kind not in ("FORMING", "CLOSED")
            or session_start_us > close_us-60_000_000 or close_us > session_end_us
            or not isinstance(provenance, str) or not provenance.strip()):
        raise ValueError("UNREVIEWED_MINUTE_OR_SESSION")
    low = close_us - (60_000_000 if kind == "FORMING" else 0)
    high = min(close_us+freshness_us, session_end_us)
    if low >= high:
        raise ValueError("NO_OPEN_ANALYSIS_WINDOW")
    return OperationWindow("MARKET_ANALYSIS", Interval(low, high),
                           high < session_end_us, provenance)


def native_candidate_proof(record, *, epoch, native_session, calendar_hash, window,
                           event_utc, receipt_utc, now_utc, maximum_age_us):
    """Offline witness contract only. No admission, queue, or persistent state.

    Identity/provenance is caller-reviewed input, not inferred by equal bar labels.
    A sibling indicator callback cannot attest the exporter's emission instant.
    """
    try:
        if (record["epoch"] != epoch or record["native_session"] != native_session
                or record["calendar_sha256"] != calendar_hash
                or not all(isinstance(x,str) and x for x in (epoch,native_session,calendar_hash))
                or record["state"] != "Realtime" or record["connection_continuity"] is not True
                or record["callback_bound_to_exporter_record"] is not True
                or record["source"] != ["Provider31","NQ DEC26","Minute",1,"UTC","CME US Index Futures ETH"]
                or type(window) is not OperationWindow or window.operation != "MARKET_ANALYSIS"
                or not window.provenance or type(window.end_inclusive) is not bool
                or type(now_utc) is not Interval or now_utc.low < window.valid_utc.low
                or now_utc.high > window.valid_utc.high
                or (not window.end_inclusive and now_utc.high == window.valid_utc.high)):
            return "UNKNOWN"
        return boundary_proof(kind=record["kind"],close_label_us=record["close_label_us"],
                              event_utc=event_utc,receipt_utc=receipt_utc,now_utc=now_utc,
                              maximum_age_us=maximum_age_us)
    except (KeyError, TypeError, ValueError, AttributeError):
        return "UNKNOWN"


def collect(rounds=12, period=5):
    if type(rounds) is not int or not 2 <= rounds <= 12 or type(period) is not int or not 1 <= period <= 5:
        raise ValueError("BOUNDED_CAPTURE_PARAMETERS_REQUIRED")
    epoch = str(uuid.uuid4())  # Process capture epoch; NOT an OS boot attestation.
    before = windows_snapshot()
    addresses = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks = {r:pool.submit(resolve,r) for r in REFERENCES}
        for r,future in tasks.items():
            try:
                addresses[r] = future.result()
            except (OSError, ValueError, subprocess.SubprocessError):
                addresses[r] = None
        start = time.perf_counter_ns()
        records, rates = [], []
        for index in range(rounds):
            # Monotonic pacing controls measurement load only; never admission.
            remaining = (start+index*period*NS-time.perf_counter_ns())/NS
            if remaining > 0:
                time.sleep(remaining)
            rates.append(clock_rate())
            futures = {r:pool.submit(probe,r,a,epoch) for r,a in addresses.items() if a}
            for r in REFERENCES:
                records.append(futures[r].result() if r in futures else
                               dict(reference=r,epoch=epoch,status="DNS_UNAVAILABLE"))
    after = windows_snapshot()
    now = pair()
    # Real acquired samples, but intentionally no invented ReviewedBounds/state mapping.
    samples = [Sample(**r["sample"]) for r in records if "sample" in r]
    verdict = assess(samples=samples,bounds=None,windows=[],windows_state=None,
                     epoch=epoch,host_now_us=now["host_ns"]//1000,
                     mono_now_us=now["mono_after_ns"]//1000)
    return dict(schema="arms.clock-evidence.v1",epoch=epoch,now=now,
                clock_basis=time.get_clock_info("perf_counter").implementation,
                references=REFERENCES,records=records,rates=rates,
                windows_before=before,windows_after=after,summary=summarize(records,now),
                preflight=verdict,windows_changed=False,watcher_armed=False,
                paper_entries="DISABLED",news="UNCERTIFIED",sim_execution="DISABLED",live_authority=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    # Exclusive output reservation prevents accidental reuse, even on partial failure.
    with args.output.open("x",encoding="utf-8") as output:
        result = collect()
        json.dump(result,output,indent=2,allow_nan=False)
        output.write("\n")
    print(json.dumps({"status":result["preflight"]["status"],"summary":result["summary"]}))


if __name__ == "__main__":
    main()
