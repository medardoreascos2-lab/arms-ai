"""Executable V9 audit: current barriers are evidence, not MVP acceptance.

No production owner is replaced and no market/financial state is injected.
The hosted fixture supplies isolated PAPER account configuration only.
The companion manifest distinguishes these characterizations from future gates.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from starlette.websockets import WebSocketDisconnect

from backend.tests.test_account_runtime_transition_v2 import hosted
from backend.tests.test_phase1_consolidated_acceptance_v8 import submission
from backend.tests.test_runtime_admission_v81 import economic_state


def test_public_quote_ingress_reaches_canonical_owner_without_execution(hosted):
    runtime = hosted.c.published.runtime
    app = hosted.c.published.application
    before = economic_state(runtime)
    now = datetime.now(timezone.utc)
    response = hosted.client.post('/market/quote', json={
        'symbol': 'MNQ', 'bid': 9999.875, 'ask': 10000.125,
        'timestamp': now.isoformat(),
    }, headers={'X-ARMS-TOKEN': app.state.webhook_token})
    assert response.status_code == 201, response.text
    admission = runtime.trade_lifecycle_service.runtime_admission_v2
    assert admission.quote_authority is app.state.runtime_quote_authority_v2
    assert admission.quote_authority.get_quote(symbol='MNQ')['timestamp'] == now
    assert economic_state(runtime) == before
    # A quote alone never grants certified calendar/news permission.
    rejected = hosted.client.post('/v2/trades/submit', json=submission(hosted))
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()['accepted'] is False
    assert economic_state(runtime) == before
    assert runtime.trade_lifecycle_service.broker_connector_v2.get_fills() == []


@pytest.mark.parametrize('entry', ['webhook', 'analyze'])
def test_current_public_candle_analysis_barrier_is_explicit_and_safe(hosted, entry):
    runtime = hosted.c.published.runtime
    app = hosted.c.published.application
    before = economic_state(runtime)
    if entry == 'webhook':
        payload = {'symbol': 'MNQ', 'timeframe': '5m', 'open': 10000.,
                   'high': 10001., 'low': 9999., 'close': 10000., 'volume': 100,
                   'timestamp': datetime.now(timezone.utc).isoformat()}
    else:
        payload = {'symbol': 'MNQ', 'timeframe': '5m', 'candle_limit': 50,
                   'account_balance': 150000., 'risk_percent': .5,
                   'point_value': 2., 'reward_risk_ratio': 2.}
    response = hosted.client.post('/market/'+entry, json=payload,
        headers={'X-ARMS-TOKEN': app.state.webhook_token})
    assert response.status_code == 503, response.text
    assert response.json()['detail'] == 'legacy_position_manager_unavailable'
    assert app.state.live_candle_store.count(symbol='MNQ', timeframe='5m') == 0
    assert economic_state(runtime) == before
    assert runtime.trade_lifecycle_service.broker_connector_v2.get_fills() == []


def test_browser_shaped_unauthorized_requests_do_not_bypass_phase1(hosted):
    runtime = hosted.c.published.runtime
    before = economic_state(runtime)
    # The current browser client supplies neither this header nor a session.
    context = hosted.client.get('/api/v2/dashboard/account-manager/switch-context').json()
    response = hosted.client.post('/api/v2/dashboard/account-manager/switch',
        json={'account_id': context['account_id'], 'profile_name': context['profile_name']},
        headers={'X-ARMS-ADMIN-TOKEN': ''})
    assert response.status_code == 401, response.text
    with pytest.raises(WebSocketDisconnect) as exc:
        with hosted.client.websocket_connect('/api/v2/dashboard/ws',
                 headers={'X-ARMS-ADMIN-TOKEN': ''}):
            pytest.fail('Unauthenticated browser socket accepted')
    assert exc.value.code == 1008
    assert economic_state(runtime) == before


def test_authorized_dashboard_and_socket_project_same_runtime_without_trading(hosted):
    runtime = hosted.c.published.runtime
    before = economic_state(runtime)
    response = hosted.client.get('/api/v2/dashboard/live')
    assert response.status_code == 200, response.text
    with hosted.client.websocket_connect('/api/v2/dashboard/ws') as ws:
        event = ws.receive_json()
        assert event['event_type'] == 'dashboard_snapshot'
        socket_snapshot = event['data']
        http_snapshot = response.json()
        assert socket_snapshot.pop('snapshot_time')
        assert http_snapshot.pop('snapshot_time')
        assert socket_snapshot == http_snapshot
    assert economic_state(runtime) == before


def test_inventory_counts_dependencies_and_evidence_are_complete():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads(Path(__file__).with_name(
        'phase2_mvp_capability_inventory_v9.json').read_text(encoding='utf-8'))
    rows = manifest['capabilities']
    ids = {r['CAPABILITY_ID'] for r in rows}
    assert len(ids) == len(rows)
    statuses = {'CLOSED_CERTIFIED', 'IMPLEMENTED_NOT_INTEGRATED',
                'IMPLEMENTED_NEEDS_E2E_PROOF', 'PARTIAL', 'MISSING',
                'POST_MVP', 'BLOCKED_EXTERNAL'}
    for row in rows:
        assert row['STATUS'] in statuses
        assert row['MVP_REQUIRED'] in {'YES', 'NO'}
        assert set(row['DEPENDENCIES']) <= ids
        for field in ['NAME', 'OWNER', 'IMPLEMENTATION_STATUS', 'INTEGRATION_STATUS',
                      'TEST_STATUS', 'END_TO_END_STATUS', 'BLOCKER', 'EVIDENCE']:
            assert row[field]
        for evidence in row['EVIDENCE']:
            assert (root / evidence.split('::')[0]).exists(), evidence
    mandatory = [r for r in rows if r['MVP_REQUIRED'] == 'YES']
    closed = sum(r['STATUS'] == 'CLOSED_CERTIFIED' for r in mandatory)
    assert manifest['counts']['MVP_COMPLETION_PERCENT'] == 100 * closed // len(mandatory)
    assert manifest['counts']['TOTAL_MVP_CAPABILITIES'] == len(rows)
    assert manifest['counts']['CLOSED_CERTIFIED'] == closed
    for priority in ['P0', 'P1', 'P2']:
        assert manifest['counts'][priority+'_GAPS'] == sum(
            r['PRIORITY'] == priority and r['STATUS'] != 'CLOSED_CERTIFIED'
            for r in mandatory)
    visited = set()
    def visit(ident, stack):
        assert ident not in stack, 'Capability dependency cycle'
        if ident in visited:
            return
        for dependency in next(r for r in rows if r['CAPABILITY_ID'] == ident)['DEPENDENCIES']:
            visit(dependency, stack | {ident})
        visited.add(ident)
    for ident in ids:
        visit(ident, set())
    assert len(manifest['acceptance_specification']) == 12
    assert {step['STEP'] for step in manifest['acceptance_specification']} == set(range(1, 13))
    assert all(t['STATUS'] in {'CONNECTED', 'PARTIAL', 'DISCONNECTED', 'TEST_ONLY', 'MANUAL_ONLY'}
               for t in manifest['transitions'])
