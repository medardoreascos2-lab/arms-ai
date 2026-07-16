from backend.backtesting.walk_forward_dashboard_exporter import (
    WalkForwardDashboardExporter,
)
from backend.backtesting.walk_forward_report import (
    WalkForwardReport,
    WalkForwardWindowReport,
)


def build_report():
    return WalkForwardReport(
        total_windows=4,
        profitable_windows=3,
        losing_windows=1,
        breakeven_windows=0,
        total_net_profit=40.0,
        average_net_profit=10.0,
        profitable_window_rate=75.0,
        net_profit_std_dev=9.35,
        stability_score=72.41,
        best_window_number=2,
        best_window_profit=20.0,
        worst_window_number=3,
        worst_window_profit=-5.0,
        windows=[
            WalkForwardWindowReport(
                window_number=1,
                training_start=0,
                training_end=100,
                testing_start=100,
                testing_end=120,
                net_profit=10.0,
            ),
            WalkForwardWindowReport(
                window_number=2,
                training_start=20,
                training_end=120,
                testing_start=120,
                testing_end=140,
                net_profit=20.0,
            ),
            WalkForwardWindowReport(
                window_number=3,
                training_start=40,
                training_end=140,
                testing_start=140,
                testing_end=160,
                net_profit=-5.0,
            ),
            WalkForwardWindowReport(
                window_number=4,
                training_start=60,
                training_end=160,
                testing_start=160,
                testing_end=180,
                net_profit=15.0,
            ),
        ],
    )


def test_dashboard_is_created(tmp_path):
    file_path = tmp_path / "dashboard.html"

    returned = WalkForwardDashboardExporter().export_html(
        report=build_report(),
        file_path=file_path,
    )

    assert returned == file_path
    assert file_path.exists()


def test_dashboard_contains_summary(tmp_path):
    file_path = tmp_path / "dashboard.html"

    WalkForwardDashboardExporter().export_html(
        report=build_report(),
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "Walk Forward Dashboard" in html
    assert "40.00" in html
    assert "75.00%" in html
    assert "72.41" in html


def test_dashboard_contains_window_table(tmp_path):
    file_path = tmp_path / "dashboard.html"

    WalkForwardDashboardExporter().export_html(
        report=build_report(),
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "Window" in html
    assert "Net Profit" in html

    assert ">1<" in html
    assert ">2<" in html
    assert ">3<" in html
    assert ">4<" in html


def test_dashboard_creates_parent_directory(
    tmp_path,
):
    file_path = (
        tmp_path
        / "reports"
        / "dashboard.html"
    )

    WalkForwardDashboardExporter().export_html(
        report=build_report(),
        file_path=file_path,
    )

    assert file_path.exists()


def test_dashboard_handles_empty_report(
    tmp_path,
):
    report = WalkForwardReport(
        total_windows=0,
        profitable_windows=0,
        losing_windows=0,
        breakeven_windows=0,
        total_net_profit=0,
        average_net_profit=0,
        profitable_window_rate=0,
        net_profit_std_dev=0,
        stability_score=0,
        best_window_number=None,
        best_window_profit=None,
        worst_window_number=None,
        worst_window_profit=None,
        windows=[],
    )

    file_path = tmp_path / "dashboard.html"

    WalkForwardDashboardExporter().export_html(
        report=report,
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "Walk Forward Dashboard" in html
    assert "No windows available" in html
