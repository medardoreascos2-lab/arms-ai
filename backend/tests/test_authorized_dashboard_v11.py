"""Browser-compatible transport delegates to the existing admin authority."""
import base64
import pytest
from starlette.websockets import WebSocketDisconnect

from backend.tests.test_account_runtime_transition_v2 import hosted, target, trade
from backend.tests.test_runtime_admission_v81 import economic_state
from backend.tests.test_market_to_candidate_v10 import configured_market, market_hosted, qualifying_sequence


def protocol(token):
    return 'arms-admin.' + base64.urlsafe_b64encode(token.encode()).decode().rstrip('=')


@pytest.mark.parametrize('token', [None, 'wrong', 'admin-secret'])
def test_browser_http_control_authorization(hosted, token):
    before = economic_state(hosted.c.published.runtime)
    result = hosted.client.post('/api/v2/dashboard/account-manager/switch',
        json=target(hosted, 'A'), headers={'X-ARMS-ADMIN-TOKEN': token or ''})
    assert result.status_code == (200 if token == 'admin-secret' else 401)
    assert economic_state(hosted.c.published.runtime) == before


@pytest.mark.parametrize('token', [None, 'wrong', 'admin-secret'])
def test_browser_websocket_authorization_and_snapshot(hosted, token):
    before = economic_state(hosted.c.published.runtime)
    protocols = ['arms-dashboard-v1', protocol(token)] if token else []
    if token != 'admin-secret':
        with pytest.raises(WebSocketDisconnect) as exc:
            with hosted.client.websocket_connect('/api/v2/dashboard/ws',
                    headers={'X-ARMS-ADMIN-TOKEN': ''}, subprotocols=protocols):
                pytest.fail('unauthorized socket accepted')
        assert exc.value.code == 1008
    else:
        with hosted.client.websocket_connect('/api/v2/dashboard/ws',
                headers={'X-ARMS-ADMIN-TOKEN': ''}, subprotocols=protocols) as ws:
            assert ws.accepted_subprotocol == 'arms-dashboard-v1'  # never echo credential
            event = ws.receive_json()
            assert event['event_type'] == 'dashboard_snapshot'
            actual = event['data']
            expected = hosted.client.get('/api/v2/dashboard/live').json()
            actual.pop('snapshot_time')
            expected.pop('snapshot_time')
            assert actual == expected
            assert actual['runtime']['account_id'] == hosted.c.identity.account_id
            assert actual['runtime']['runtime_generation'] == hosted.c.published.generation
    assert economic_state(hosted.c.published.runtime) == before


def test_browser_account_retirement_and_authoritative_positions(hosted):
    trade(hosted, 10010.)
    a = hosted.c.published.runtime
    before = economic_state(a)
    with hosted.client.websocket_connect('/api/v2/dashboard/ws',
            headers={'X-ARMS-ADMIN-TOKEN': ''}, subprotocols=[protocol('admin-secret')]) as ws:
        snap = ws.receive_json()['data']
        assert snap['account_state'] == a.account_state_manager_v2.get_state()
        assert snap['positions'] == a.portfolio_manager_v2.get_open_positions()
        assert snap['journal_history']
        assert snap['portfolio_summary']['total_realized_pnl'] > 0
        assert economic_state(a) == before
        assert hosted.client.post('/api/v2/dashboard/account-manager/switch', json=target(hosted, 'B')).status_code == 200
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 1012
    with hosted.client.websocket_connect('/api/v2/dashboard/ws',
            headers={'X-ARMS-ADMIN-TOKEN': ''}, subprotocols=[protocol('admin-secret')]) as ws:
        b = ws.receive_json()['data']
        assert b['runtime']['account_id'] != snap['runtime']['account_id']
        assert b['runtime']['runtime_generation'] > snap['runtime']['runtime_generation']
        assert b['journal_history'] == []
        assert b['positions'] == []


@pytest.mark.parametrize('protocols,header', [
    (['arms-admin.%%%'], ''), (['arms-admin._w'], ''),
    ([protocol('admin-secret'), protocol('wrong')], ''),
    ([protocol('admin-secret')], 'wrong'), (['arms-admin.' + 'A' * 4097], ''),
])
def test_malformed_or_ambiguous_credentials_fail_closed(hosted, protocols, header):
    with pytest.raises(WebSocketDisconnect) as exc:
        with hosted.client.websocket_connect('/api/v2/dashboard/ws',
                headers={'X-ARMS-ADMIN-TOKEN': header}, subprotocols=protocols):
            pytest.fail('invalid credential accepted')
    assert exc.value.code == 1008


def test_browser_projection_is_observational_with_real_candidate(market_hosted, monkeypatch):
    h = market_hosted
    candidate = qualifying_sequence(h)
    from backend.tests.test_dashboard_read_execution_safety_v2 import forbid_mutations
    before = economic_state(h.c.published.runtime)
    guards = forbid_mutations(h.app, monkeypatch)
    analysis = h.client.get('/market/latest-analysis?symbol=MNQ&timeframe=5m').json()
    assert analysis['signal_v2'] == candidate['signal_v2']
    for _ in range(2):
        assert h.client.get('/api/v2/dashboard/live').status_code == 200
        with h.client.websocket_connect('/api/v2/dashboard/ws',
                headers={'X-ARMS-ADMIN-TOKEN': ''}, subprotocols=[protocol('admin-secret')]) as ws:
            assert ws.receive_json()['data']['positions'] == []
    assert economic_state(h.c.published.runtime) == before
    for guard in guards:
        guard.assert_not_called()


def test_disconnect_cleanup_completes_before_next_browser_connection(hosted):
    hub = hosted.app.state.dashboard_websocket_hub_v2
    for _ in range(30):
        with hosted.client.websocket_connect('/api/v2/dashboard/ws') as ws:
            assert ws.receive_json()['event_type'] == 'dashboard_snapshot'
            assert hub.get_connection_count() == 1
        assert hub.get_connection_count() == 0


def test_actual_frontend_client_over_http_and_websocket(market_hosted):
    """Run production TS client against real local ASGI transport, no fetch mocks."""
    import shutil
    import socket
    import subprocess
    import threading
    import time
    from pathlib import Path
    import uvicorn

    root = Path(__file__).resolve().parents[2]
    if not shutil.which('node') or not (root/'frontend/node_modules/typescript').exists():
        pytest.skip('Cross-stack transport requires installed frontend Node dependencies')
    hosted = market_hosted
    qualifying_sequence(hosted)
    trade(hosted, 10010.)
    a = hosted.c.published.runtime
    before = economic_state(a)
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(hosted.app, lifespan='off', log_level='error'))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.01)
        assert server.started
        result = subprocess.run(['node', '--input-type=module', '-', str(port)],
            input=Path(__file__).with_name('dashboard_transport_v11.mjs').read_text(encoding='utf-8'),
            text=True, cwd=root/'frontend', capture_output=True, timeout=40)
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'V11_HTTP_WS_BUNDLE_GREEN' in result.stdout
        assert economic_state(a) == before
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        assert not thread.is_alive()
