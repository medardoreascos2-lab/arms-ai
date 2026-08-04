from backend.backtesting.backtesting_orchestrator_v2 import (
    BacktestingOrchestratorResultV2,
)
from backend.backtesting.institutional_backtesting_report_v2 import (
    InstitutionalBacktestingReportV2,
)

from backend.tests.test_backtesting_orchestrator_v2 import (
    build_orchestrator,
)


def test_orchestrator_returns_institutional_report(
    tmp_path,
):

    orchestrator, *_ = build_orchestrator()

    result = orchestrator.run(
        candles=[object()],
        output_directory=tmp_path,
    )

    assert isinstance(
        result,
        BacktestingOrchestratorResultV2,
    )

    assert isinstance(
        result.institutional_report,
        InstitutionalBacktestingReportV2,
    )

    payload = result.to_dict()

    assert "institutional_report" in payload

    assert (
        payload[
            "institutional_report"
        ]["executive_summary"]["status"]
        == "CERTIFIED"
    )
