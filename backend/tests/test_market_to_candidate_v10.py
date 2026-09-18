"""Public controlled PAPER input, real application owners, no approval injection."""
from datetime import datetime, timedelta, timezone
import pytest
import json

from backend.tests.test_account_runtime_transition_v2 import hosted
from backend.tests.test_runtime_admission_v81 import economic_state

NOW = datetime(2026, 9, 8, 15, tzinfo=timezone.utc)


@pytest.fixture
def configured_market(tmp_path, monkeypatch, request):
    """Explicit test-certified files and clock; no owner/indicator/approval fakes."""
    class ClockMeta(type):
        def __instancecheck__(cls, instance):
            return isinstance(instance, datetime)
    class Clock(datetime, metaclass=ClockMeta):
        current = NOW
        @classmethod
        def now(cls, tz=None):
            return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)
    monkeypatch.setattr('backend.services.live_market_analysis_service.datetime', Clock)
    monkeypatch.setattr('backend.services.runtime_admission_v2.datetime', Clock)
    hours = tmp_path/'v10-test-hours.json'
    hours.write_text(json.dumps({'covered_dates': [NOW.date().isoformat()],
                                'closed_dates': [NOW.date().isoformat()] if getattr(request, 'param', '') == 'closed' else [], 'special_hours': []}))
    news = tmp_path/'v10-test-news.json'
    news.write_text(json.dumps({'snapshot_version': 'explicit-v10-test-input',
        'generated_at': (NOW-timedelta(hours=1)).isoformat(),
        'coverage_start': (NOW-timedelta(hours=1)).isoformat(),
        'coverage_end': (NOW+timedelta(hours=1)).isoformat(),
        'high_impact_events': [NOW.isoformat()] if getattr(request, 'param', '') == 'news' else []}))
    monkeypatch.setenv('ARMS_CERTIFIED_MARKET_HOURS_PATH', str(hours))
    monkeypatch.setenv('ARMS_CERTIFIED_ECONOMIC_NEWS_PATH', str(news))
    return Clock


@pytest.fixture
def market_hosted(configured_market, hosted):
    return hosted


def candle(index=0, *, timestamp=None, close=10000.):
    return dict(symbol='MNQ', timeframe='5m', open=close-1, high=close+3,
                low=close-3, close=close, volume=1000.,
                timestamp=(timestamp or datetime.now(timezone.utc)-timedelta(minutes=5*(50-index))).isoformat())


def ingest(h, payload):
    return h.client.post('/market/webhook', json=payload,
        headers={'X-ARMS-TOKEN': h.app.state.webhook_token})


def test_application_candle_ingress_is_idempotent_and_non_executing(hosted):
    before = economic_state(hosted.c.published.runtime)
    payload = candle()
    first = ingest(hosted, payload)
    assert first.status_code == 201, first.text
    assert first.json()['count'] == 1
    duplicate = ingest(hosted, payload)
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()['status'] == 'duplicate'
    assert duplicate.json()['count'] == 1
    assert economic_state(hosted.c.published.runtime) == before


def qualifying_sequence(h, *, flat=False):
    before = economic_state(h.c.published.runtime)
    quote = h.client.post('/market/quote', headers={'X-ARMS-TOKEN': h.app.state.webhook_token},
        json={'symbol': 'MNQ', 'bid': 10103.875, 'ask': 10104.125, 'timestamp': NOW.isoformat()})
    assert quote.status_code == 201
    for timeframe, minutes in [('1m', 1), ('15m', 15), ('1h', 60), ('5m', 5)]:
        for index in range(50):
            payload = candle(index, timestamp=NOW-timedelta(minutes=minutes*(49-index)),
                             close=10104. if flat else 10000.+index*2)
            payload['timeframe'] = timeframe
            if index == 48 and not flat:
                payload.update(open=10100., low=10099., high=10103., close=10102.)
            if index == 49 and not flat:
                payload.update(open=10101., low=10098., high=10105., close=10104., volume=3000.)
            response = ingest(h, payload)
            assert response.status_code == 201, response.text
    a = response.json()['analysis']
    assert economic_state(h.c.published.runtime) == before
    return a


def test_qualifying_market_sequence_evaluates_canonical_candidate(market_hosted, monkeypatch):
    h = market_hosted
    from backend.tests.test_dashboard_read_execution_safety_v2 import forbid_mutations
    with monkeypatch.context() as scope:
        guards = forbid_mutations(h.app, scope)
        a = qualifying_sequence(h)
        for guard in guards:
            guard.assert_not_called()
    signal = a['signal_v2']
    assert signal['approved'], signal
    assert signal['grade'] == 'A+'
    assert signal['confluence_score'] == .9412
    assert signal['generated_at'] == NOW.isoformat()
    assert signal['entry_price'] == 10104.
    assert len(signal['source_hash']) == len(signal['submission_id']) == 64
    assert a['ema_alignment']['ema'] == a['indicators']['ema']
    runtime = h.c.published.runtime
    assert runtime.trade_lifecycle_service.broker_connector_v2.get_fills() == []
    response = h.client.post('/v2/trades/submit', json=a['admission_request'])
    assert response.status_code == 200, response.text
    assert response.json()['accepted'], response.text
    assert len(runtime.trade_lifecycle_service.broker_connector_v2.get_fills()) == 1
    assert len(runtime.trade_lifecycle_service.get_active_positions()) == 1
    after = economic_state(runtime)
    retry = h.client.post('/v2/trades/submit', json=a['admission_request'])
    assert retry.status_code == 409
    assert economic_state(runtime) == after


def test_no_trade_with_valid_market_inputs(market_hosted):
    a = qualifying_sequence(market_hosted, flat=True)
    assert not a['signal_v2']['approved']
    before = economic_state(market_hosted.c.published.runtime)
    response = market_hosted.client.post('/v2/trades/submit', json=a['admission_request'])
    assert response.status_code == 200, response.text
    assert response.json()['accepted'] is False
    assert economic_state(market_hosted.c.published.runtime) == before


@pytest.mark.parametrize('configured_market', ['closed', 'news'], indirect=True)
def test_required_permission_blocks_generated_candidate(market_hosted, configured_market):
    a = qualifying_sequence(market_hosted)
    assert not a['signal_v2']['approved']
    before = economic_state(market_hosted.c.published.runtime)
    response = market_hosted.client.post('/v2/trades/submit', json=a['admission_request'])
    assert response.status_code == 200, response.text
    assert response.json()['accepted'] is False
    assert economic_state(market_hosted.c.published.runtime) == before


@pytest.mark.parametrize('damage', ['expired_quote', 'account_context', 'retired_generation'])
def test_generated_ready_candidate_still_requires_runtime_admission(market_hosted, configured_market, monkeypatch, damage):
    from unittest.mock import Mock
    from backend.tests.test_account_runtime_transition_v2 import switch
    h = market_hosted
    a = qualifying_sequence(h)
    assert a['signal_v2']['approved']
    if damage == 'expired_quote':
        configured_market.current = NOW+timedelta(seconds=31)
    elif damage == 'account_context':
        a['admission_request']['risk_context']['risk_percent'] = 100.
    else:
        assert switch(h, 'B').status_code == 200
        assert switch(h, 'A').status_code == 200
    runtime = h.c.published.runtime
    before = economic_state(runtime)
    guards = []
    for owner, name in [(runtime.execution_manager, 'prepare_order'),
                        (runtime.trade_lifecycle_service.broker_connector_v2, 'submit_order'),
                        (runtime.paper_execution_engine, 'execute')]:
        guard = Mock(side_effect=AssertionError('Rejected candidate reached execution'))
        monkeypatch.setattr(owner, name, guard)
        guards.append(guard)
    response = h.client.post('/v2/trades/submit', json=a['admission_request'])
    assert response.status_code in {200, 409, 422}, response.text
    assert response.json().get('accepted') is not True
    assert economic_state(runtime) == before
    assert runtime.trade_lifecycle_service.broker_connector_v2.get_fills() == []
    for guard in guards:
        guard.assert_not_called()


def test_application_rejects_conflicting_and_out_of_order_candles(hosted):
    payload = candle(timestamp=datetime.now(timezone.utc)-timedelta(minutes=5))
    assert ingest(hosted, payload).status_code == 201
    before = economic_state(hosted.c.published.runtime)
    conflict = dict(payload, close=10001.)
    assert ingest(hosted, conflict).status_code == 409
    assert ingest(hosted, candle(timestamp=datetime.now(timezone.utc)-timedelta(minutes=10))).status_code == 409
    assert hosted.app.state.live_candle_store.count(symbol='MNQ', timeframe='5m') == 1
    assert economic_state(hosted.c.published.runtime) == before


@pytest.mark.parametrize('step', [0., 2.])
def test_public_sequence_reaches_real_intelligence_and_admission(hosted, step):
    before = economic_state(hosted.c.published.runtime)
    end = datetime.now(timezone.utc)-timedelta(seconds=1)
    for index in range(50):
        response = ingest(hosted, candle(index,
            timestamp=end-timedelta(minutes=5*(49-index)), close=10000.+step*index))
        assert response.status_code == 201, response.text
    analysis = response.json()['analysis']
    assert analysis['candidate_only'] is True
    assert analysis['current_price'] == 10000.+step*49
    assert analysis['indicators']
    assert analysis['smart_money_v2']
    assert analysis['confluence_v2']
    assert analysis['probability_v2']
    candidate = analysis['signal_v2']
    assert candidate['source'] == 'LIVE_MARKET_ANALYSIS'
    assert candidate['runtime_generation'] == hosted.c.published.generation
    assert candidate['status'] == 'BLOCKED'  # No quote or certified permission supplied.
    assert economic_state(hosted.c.published.runtime) == before
    admission = hosted.client.post('/v2/trades/submit', json=analysis['admission_request'])
    assert admission.status_code == 200, admission.text
    assert admission.json()['accepted'] is False
    assert economic_state(hosted.c.published.runtime) == before


@pytest.mark.parametrize('damage', ['future', 'naive', 'negative', 'nan', 'infinite_volume'])
def test_invalid_candle_never_contaminates_market_or_financial_state(hosted, damage):
    payload = candle()
    if damage == 'future':
        payload['timestamp'] = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    elif damage == 'naive':
        payload['timestamp'] = '2026-09-08T15:00:00'
    elif damage == 'negative':
        payload.update(open=-2, high=-1, low=-3, close=-2)
    elif damage == 'nan':
        payload['open'] = 'NaN'
    else:
        payload['volume'] = 'Infinity'
    before = economic_state(hosted.c.published.runtime)
    response = ingest(hosted, payload)
    assert response.status_code in {400, 422}, response.text
    assert hosted.app.state.live_candle_store.count(symbol='MNQ', timeframe='5m') == 0
    assert economic_state(hosted.c.published.runtime) == before


def test_repeated_input_and_analysis_preserve_candidate_and_authoritative_inputs(market_hosted):
    h = market_hosted
    a = qualifying_sequence(h)
    before = economic_state(h.c.published.runtime)
    history = h.client.get('/market/signals', params={'symbol': 'MNQ', 'timeframe': '5m'}).json()
    last = candle(timestamp=NOW, close=10104.)
    last.update(open=10101., low=10098., high=10105., volume=3000.)
    for _ in range(3):
        response = ingest(h, last)
        assert response.json()['status'] == 'duplicate'
        assert response.json()['analysis_generated'] is False
    assert h.client.get('/market/signals', params={'symbol': 'MNQ', 'timeframe': '5m'}).json() == history
    response = h.client.post('/market/analyze', json={
        'symbol': 'MNQ', 'timeframe': '5m', 'candle_limit': 50,
        'account_balance': 1., 'risk_percent': 99., 'point_value': 100., 'reward_risk_ratio': 1.})
    assert response.status_code == 200, response.text
    assert response.json()['admission_request'] == a['admission_request']
    assert response.json()['indicators'] == a['indicators']
    assert economic_state(h.c.published.runtime) == before
    assert h.app.state.trend_engine_v2.live_candle_store is h.app.state.live_candle_store


def test_older_quote_cannot_overwrite_canonical_quote(market_hosted):
    h = market_hosted
    body = {'symbol': 'MNQ', 'bid': 10000., 'ask': 10000.25, 'timestamp': NOW.isoformat()}
    headers = {'X-ARMS-TOKEN': h.app.state.webhook_token}
    assert h.client.post('/market/quote', json=body, headers=headers).status_code == 201
    before = h.app.state.runtime_quote_authority_v2.get_quote(symbol='MNQ')
    response = h.client.post('/market/quote', json={**body, 'bid': 9999.,
        'timestamp': (NOW-timedelta(seconds=1)).isoformat()}, headers=headers)
    assert response.status_code == 400, response.text
    assert h.app.state.runtime_quote_authority_v2.get_quote(symbol='MNQ') == before


def test_concurrent_duplicate_ingress_applies_once(hosted):
    from concurrent.futures import ThreadPoolExecutor
    payload = candle()
    before = economic_state(hosted.c.published.runtime)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: ingest(hosted, payload), range(2)))
    assert all(r.status_code == 201 for r in responses)
    assert sorted(r.json()['status'] for r in responses) == ['duplicate', 'stored']
    assert hosted.app.state.live_candle_store.count(symbol='MNQ', timeframe='5m') == 1
    assert economic_state(hosted.c.published.runtime) == before
