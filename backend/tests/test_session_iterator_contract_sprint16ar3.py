"""Offline capability/representation checks; never claim native iterator outcomes."""
import json
from pathlib import Path
import subprocess

import pytest

from backend.tests.test_historical_diagnostics_sprint16ar1 import CSC, ROOT

SDK = Path('C:/Program Files/NinjaTrader 8/bin')
HARNESS = ROOT / 'backend/tests/fixtures/session_iterator_contract_harness_sprint16ar3.cs'


@pytest.fixture(scope='module')
def probe(tmp_path_factory):
    if not CSC.exists() or not (SDK / 'NinjaTrader.Core.dll').exists():
        pytest.skip('Installed Windows SDK and Framework compiler required')
    executable = tmp_path_factory.mktemp('contract-probe') / 'probe.exe'
    compile_result = subprocess.run([
        str(CSC), '/nologo', '/r:System.Web.Extensions.dll', '/r:System.Core.dll',
        '/out:' + str(executable), str(HARNESS),
    ], capture_output=True, text=True, timeout=30)
    assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr
    result = subprocess.run([str(executable), str(SDK)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(result.stdout) < 1024 * 1024
    return json.loads(result.stdout)


def test_metadata_cannot_be_promoted_to_native_evidence(probe):
    assert probe['classification'] == 'OFFLINE_METADATA_AND_TIMEZONE_ONLY'
    assert probe['native_method_invoked'] is False
    assert probe['reflection_only'] is True
    assert probe['loaded_for_execution'] == []
    assert probe['runtime_admission'] is False
    assert probe['certification_evidence'] is False
    assert probe['native_offline_harness_status'] == 'BLOCKED_NO_VALIDATED_NATIVE_EXECUTION_HOST'
    for scenario in probe['native_boundary_scenarios']:
        assert scenario['boolean_results'] is None and scenario['returned_bounds'] is None
        assert scenario['status'] == 'NOT_EXECUTED_NATIVE_HOST_UNAVAILABLE'


def test_installed_version_and_exposed_body_match_reviewed_capability_limit(probe):
    assert probe['sdk_version'] == '8.1.8.2', 'Different SDK requires a new version-specific review'
    assert probe['core_sha256'] == '89d30ce74dfb21c26c0819db1f5979799b152d522bbfbc436a3b2cfb495b9408'
    assert probe['exposed_getnextsession_constant_false'] is True
    assert probe['execution_gate'] == 'EXPOSED_BODY_CONTRADICTS_OBSERVED_NATIVE_SUCCESS'
    methods = {m['name']: m for m in probe['metadata'][0]['methods']}
    assert methods['GetNextSession']['il_hex'] == '20000000002a'
    assert [p['name'] for p in methods['GetNextSession']['parameters']] == ['timeLocal', 'includesEndTimeStamp']
    assert len(methods['GetNextSession']['parameters']) == 2


@pytest.mark.parametrize('ticks,fraction', [(0, '0000000'), (1, '0000001'), (10000, '0010000'), (10000000, '0000000')])
def test_datetime_precision_and_timezone_matrix(probe, ticks, fraction):
    row = next(r for r in probe['boundary_matrix'] if r['offset_ticks'] == ticks)
    second = '01' if ticks == 10000000 else '00'
    assert row['utc'] == f'2026-09-14T21:00:{second}.{fraction}Z'
    domains = {r['domain']: r for r in row['representations']}
    assert domains['TRADING_HOURS_WALL']['text'] == f'2026-09-14T16:00:{second}.{fraction}'
    assert domains['TRADING_HOURS_WALL']['kind'] == 'Unspecified'
    for name in ('UTC', 'APPLICATION_UTC_WALL', 'TRADING_HOURS_WALL', 'OS_LOCAL'):
        assert domains[name]['equivalent_utc'] == row['utc']
        assert domains[name]['meaningful_for_domain'] is True
        assert domains[name]['native_acceptance'] == 'NOT_OBSERVED'
    assert domains['CHICAGO_WALL_MISLABELED_UTC']['meaningful_for_domain'] is False
    assert domains['CHICAGO_WALL_MISLABELED_UTC']['equivalent_utc'] is None
    assert probe['dotnet_datetime_resolution_ticks'] == 1
    assert probe['ninjatrader_query_precision_ticks'] is None


def test_boundary_candidates_remain_distinct_and_bounded(probe):
    cases = {r['name']: r for r in probe['native_boundary_scenarios']}
    assert len(cases) == 11
    for ticks in (0, 1, 10000, 10000000):
        assert cases[f'REUSED_ITERATOR_END_PLUS_{ticks}_TICKS']['query_sequence'][0] == '2026-09-14T00:00:00.0000000Z'
    assert cases['REPEATED_IDENTICAL_QUERY']['query_sequence'] == ['2026-09-14T00:00:00.0000000Z'] * 2
    assert cases['END_EXCLUSIVE_HYPOTHESIS']['include_end_time'] is False
    assert cases['MAINTENANCE_BREAK']['query_sequence'][-1] == '2026-09-14T21:30:00.0000000Z'
    assert cases['WEEKEND_REOPEN']['query_sequence'][-1] == '2026-09-20T22:00:01.0000000Z'
    assert len(cases['CONSECUTIVE_SESSIONS']['query_sequence']) == 4
