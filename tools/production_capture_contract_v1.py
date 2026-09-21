"""Offline Sprint 15W-R1 coordinator contract; no I/O, clocks, threads or activation.

The future adapter must durably publish request_id, obtain a visible operator
acknowledgment, and supply independently verified inputs. No runtime imports it.
Operational budgets below are explicit inputs, never absolute-clock error bounds.
"""
from dataclasses import dataclass
from uuid import UUID

from tools import production_timing_v1 as production
from tools import clock_evidence_v1 as clock


@dataclass(frozen=True)
class Budget:
    activation_s: int
    capture_s: int
    acknowledgement_s: int
    closure_s: int
    final_clock_s: int

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in vars(self).values()):
            raise ValueError('INVALID_OPERATIONAL_BUDGET')


def coverage(proof, *, run_id, references, measurements, bridges, closure_qpc):
    """Require valid probes before every pair and after observed writer closure.

    Reuses native QPC/hash binding and raw NTP decoding; no assumed cross-process
    perf_counter origin. This proves coverage only, never reviewed UTC authority.
    """
    if not references or len(set(references)) != len(references):
        raise ValueError('REFERENCE_SET')
    if type(closure_qpc) is not int or closure_qpc < proof['last_emission']['qpc_after']:
        raise ValueError('CLOSURE_ORDER')
    binding = production.clock_epoch_binding(proof, run_id=run_id, epoch=run_id,
                                            bridges=bridges, measurements=measurements)
    valid = {r: [] for r in references}
    previous_receipt = -1
    for raw, bridge in zip(measurements, bridges):
        r = production.parse(raw)
        if r.get('reference') not in valid or r.get('status') != 'MEASURED_NOT_ATTESTED':
            raise ValueError('INVALID_CLOCK_REFERENCE')
        decoded = clock.decode_reply(bytes.fromhex(r['packet_hex']), clock.encode_time(r['sent']['host_ns']),
                                     r['sent'], r['received'], r['reference'], run_id)
        if decoded != r:
            raise ValueError('CLOCK_PACKET_REPLAY')
        if r['sent']['mono_before_ns'] <= previous_receipt:
            raise ValueError('REUSED_OR_REORDERED_CLOCK_MEASUREMENT')
        previous_receipt = r['received']['mono_after_ns']
        valid[r['reference']].append(bridge)
    first = proof['first_callback']['qpc_before']
    for rows in valid.values():
        if (len(rows) < 2 or not any(b['after']['qpc_after'] <= first for b in rows)
                or not any(b['before']['qpc_before'] >= closure_qpc for b in rows)):
            raise ValueError('REFERENCE_DOES_NOT_BRACKET_CLOSURE')
    binding.update(closure_qpc=closure_qpc, status='PASS_COVERAGE_ONLY')
    return binding


class Coordinator:
    """Deterministic transition engine for a future visible coordinator adapter.

    tick time MUST be raw Windows QPC from one unchanged boot/frequency epoch.
    Wall time is display-only. Faults latch. An acknowledgment records receipt of
    a request, NOT the operator's remove click or native callback entry.
    """
    def __init__(self, *, run_id, epoch, frequency, ready_qpc, budget):
        if str(UUID(run_id)) != run_id or not epoch or type(budget) is not Budget:
            raise ValueError('IDENTITY_OR_BUDGET')
        if type(frequency) is not int or frequency <= 0 or type(ready_qpc) is not int or ready_qpc < 0:
            raise ValueError('QPC_BASIS')
        self.run_id, self.epoch, self.frequency, self.budget = run_id, epoch, frequency, budget
        self.ready_qpc = self.last_qpc = ready_qpc
        self.state = 'WAITING_FOR_ACTIVATION'
        self.reason = None
        self.session = self.first_seen = self.request_qpc = self.ack_qpc = self.closure_qpc = None
        self.request_id = None
        self.closed = 0
        self.proof = None
        self.binding = None
        self.events = []

    def fail(self, reason):
        self.state, self.reason = 'FAILED', reason
        return self.snapshot()

    def snapshot(self):
        return dict(state=self.state, reason=self.reason, run_id=self.run_id, session=self.session,
                    request_id=self.request_id, request_qpc=self.request_qpc, acknowledged_qpc=self.ack_qpc,
                    closure_deadline_qpc=None if self.ack_qpc is None else self.ack_qpc+self.budget.closure_s*self.frequency,
                    closure_observed_qpc=self.closure_qpc,
                    collector_must_continue=self.state not in ('FAILED', 'COMPLETE'),
                    runtime_admission=False, reference_bound='UNKNOWN', drift_bound='UNKNOWN')

    def tick(self, qpc, *, epoch, frequency, collector_alive=True, session=None, closed=0,
             acknowledged_request=None, sealed=None, exclusive_closed=False, wall_utc=None):
        if self.state in ('FAILED', 'COMPLETE'):
            return self.snapshot()
        if epoch != self.epoch or frequency != self.frequency or type(qpc) is not int or qpc < self.last_qpc:
            return self.fail('MONOTONIC_CONTINUITY_LOST')
        self.last_qpc = qpc
        if collector_alive is not True:
            return self.fail('CLOCK_COLLECTOR_STOPPED_EARLY')
        if type(closed) is not int or closed < self.closed:
            return self.fail('PREFIX_COUNT_REGRESSION')
        self.closed = closed
        if session is not None:
            try:
                valid = str(UUID(session)) == session
            except (ValueError, TypeError, AttributeError):
                valid = False
            if not valid or (self.session is not None and session != self.session):
                return self.fail('SESSION_CHANGED')
        if self.state == 'WAITING_FOR_ACTIVATION':
            if qpc-self.ready_qpc >= self.budget.activation_s*self.frequency:
                return self.fail('ACTIVATION_TIMEOUT')
            if session is None:
                return self.snapshot()
            self.session, self.first_seen, self.state = session, qpc, 'CAPTURING'
        if self.state == 'CAPTURING' and qpc-self.first_seen >= self.budget.capture_s*self.frequency:
            if closed < 3:
                return self.fail('MINIMUM_CLOSED_NOT_OBSERVED')
            self.state, self.request_qpc = 'REMOVE_REQUESTED', qpc
            self.request_id = self.run_id + ':remove:1'
            self.events.append(dict(kind='CAPTURE_COMPLETE_REMOVE_REQUEST', qpc=qpc,
                                    request_id=self.request_id, wall_utc=wall_utc))
        if self.state == 'REMOVE_REQUESTED':
            if qpc-self.request_qpc >= self.budget.acknowledgement_s*self.frequency:
                return self.fail('REMOVE_REQUEST_NOT_ACKNOWLEDGED')
            if acknowledged_request is not None:
                if acknowledged_request != self.request_id:
                    return self.fail('REQUEST_ACK_IDENTITY')
                self.ack_qpc, self.state = qpc, 'WAITING_FOR_CLOSURE'
                self.events.append(dict(kind='REMOVE_REQUEST_ACKNOWLEDGED', qpc=qpc,
                                        request_id=self.request_id, wall_utc=wall_utc))
        if self.state == 'WAITING_FOR_CLOSURE' and qpc-self.ack_qpc >= self.budget.closure_s*self.frequency:
            return self.fail('WRITER_CLOSURE_TIMEOUT')
        if sealed is not None and self.state != 'FINAL_CLOCK':
            if self.state != 'WAITING_FOR_CLOSURE':
                return self.fail('EARLY_OR_UNACKNOWLEDGED_CLOSURE')
            try:
                proof = production.adjudicate(*sealed)
            except (ValueError, TypeError):
                return self.fail('INVALID_SEALED_STREAM')
            if (proof['status'] != 'PASS' or exclusive_closed is not True or proof['session'] != self.session
                    or proof['qpc_frequency'] != self.frequency
                    or not self.first_seen <= proof['first_callback']['qpc_before'] <= proof['last_emission']['qpc_after'] <= qpc):
                return self.fail('INVALID_SEALED_STREAM')
            self.proof, self.closure_qpc, self.state = proof, qpc, 'FINAL_CLOCK'
            self.events.append(dict(kind='SEALED_WRITERS_OBSERVED', qpc=qpc, wall_utc=wall_utc))
        if self.state == 'FINAL_CLOCK' and qpc-self.closure_qpc >= self.budget.final_clock_s*self.frequency:
            return self.fail('FINAL_CLOCK_TIMEOUT')
        return self.snapshot()

    def finish(self, *, qpc, epoch, frequency, measurements, bridges, references, unchanged_closed):
        self.tick(qpc, epoch=epoch, frequency=frequency, closed=self.closed)
        if self.state != 'FINAL_CLOCK':
            return self.snapshot()
        if unchanged_closed is not True:
            return self.fail('SEALED_FILES_CHANGED')
        try:
            if any(b['after']['qpc_after'] > qpc for b in bridges):
                raise ValueError('FUTURE_CLOCK_SAMPLE')
            self.binding = coverage(self.proof, run_id=self.run_id, references=references,
                                    measurements=measurements, bridges=bridges, closure_qpc=self.closure_qpc)
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
            return self.fail('CLOCK_COVERAGE_UNPROVEN')
        self.state = 'COMPLETE'
        return self.snapshot()
