"""Transport adapters only; AdminAuthorizationV2 remains the sole authority."""
import base64
import binascii
from dataclasses import asdict
from fastapi.encoders import jsonable_encoder


def browser_admin_token(websocket, header):
    # Native clients keep the canonical header. A supplied wrong header must
    # never be rescued by an alternative credential.
    token = websocket.headers.get(header)
    if token:
        return token
    protocols = websocket.scope.get('subprotocols', [])
    credentials = [p[11:] for p in protocols if p.startswith('arms-admin.')]
    if len(credentials) != 1 or len(credentials[0]) > 4096:
        return None
    try:
        return base64.b64decode(credentials[0] + '=' * (-len(credentials[0]) % 4),
                               altchars=b'-_', validate=True).decode('ascii')
    except (ValueError, UnicodeError, binascii.Error):
        return None


def dashboard_snapshot(state, service):
    snapshot = service.get_snapshot() if service is not None else None
    runtime = getattr(state, 'runtime_context_v2', None)
    if (snapshot is None or runtime is None
            or not isinstance(runtime.execution_state_store.account_identity, dict)):
        return snapshot
    # Fixed published runtime identity, never a lookup of the next account.
    snapshot = dict(snapshot)
    snapshot['runtime'] = dict(runtime.execution_state_store.account_identity)
    snapshot['execution_mode'] = runtime.execution_manager.execution_mode
    snapshot['positions'] = runtime.portfolio_manager_v2.get_open_positions()
    journal = runtime.trade_lifecycle_service.trade_journal_v2
    snapshot['journal_history'] = [asdict(t) for t in journal.get_trades()] if journal else []
    return jsonable_encoder(snapshot)
