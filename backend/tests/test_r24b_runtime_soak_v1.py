"""Offline-only regression for the bounded R24B soak harness."""
import sys

import pytest

from tools.r24b_runtime_soak_v1 import run_soak


pytestmark = pytest.mark.skipif(sys.platform!='win32',reason='Windows Job Object required')


def test_short_soak_exercises_runtime_and_has_zero_order_side_effects(tmp_path):
    result=run_soak(result_path=tmp_path/'result.json',wall_seconds=1,
        synthetic_hours=1)
    assert result['health_checks']==60
    assert result['decision_total']>0
    assert result['l1_segments']==1 and result['l1_sequence_gaps']==0
    assert result['l1_terminal_reason']=='L1_STREAM_TERMINATED:SESSION_TERMINATED'
    assert result['sqlite_journal_mode']=='wal'
    assert result['authority_transitions']==2
    assert result['paper_enabled'] is False
    assert result['paper_orders_filled']==result['broker_order_calls']==0
    assert result['open_paper_positions']==result['closed_paper_trades']==0
    assert result['supervisor_report']['child_cleanup_confirmed'] is True
    assert result['supervisor_report']['windows_exit_code']==0
