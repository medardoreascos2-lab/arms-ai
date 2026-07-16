from backend.backtesting.walk_forward_optimization_dashboard_exporter import (
    WalkForwardOptimizationDashboardExporter,
)
from backend.backtesting.walk_forward_optimization_report import (
    WalkForwardOptimizationReport,
    WalkForwardOptimizationWindowReport,
)


def build_report():
    return WalkForwardOptimizationReport(
        total_windows=2,
        profitable_testing_windows=1,
        losing_testing_windows=1,
        breakeven_testing_windows=0,
        total_training_net_profit=180.0,
        total_testing_net_profit=30.0,
        average_training_net_profit=90.0,
        average_testing_net_profit=15.0,
        average_performance_degradation=75.0,
        testing_profitable_rate=50.0,
        overfit_windows=1,
        overfit_rate=50.0,
        windows=[
            WalkForwardOptimizationWindowReport(
                window_number=1,
                selected_parameters={
                    "ema_period":20,
                    "rsi_period":14,
                },
                training_net_profit=100.0,
                testing_net_profit=40.0,
                performance_degradation=60.0,
                degradation_rate=60.0,
                overfit_suspected=False,
            ),
            WalkForwardOptimizationWindowReport(
                window_number=2,
                selected_parameters={
                    "ema_period":50,
                    "rsi_period":21,
                },
                training_net_profit=80.0,
                testing_net_profit=-10.0,
                performance_degradation=90.0,
                degradation_rate=112.5,
                overfit_suspected=True,
            ),
        ],
    )


def test_dashboard_exporter_creates_html(tmp_path):
    report = build_report()

    html = tmp_path / "dashboard.html"

    returned = (
        WalkForwardOptimizationDashboardExporter()
        .export_html(
            report=report,
            file_path=html,
        )
    )

    assert returned == html
    assert html.exists()


def test_dashboard_contains_summary(tmp_path):
    report = build_report()

    html = tmp_path / "dashboard.html"

    WalkForwardOptimizationDashboardExporter().export_html(
        report,
        html,
    )

    text = html.read_text(
        encoding="utf-8",
    )

    assert "Optimization Dashboard" in text
    assert "Total Windows" in text
    assert "Overfit Rate" in text
    assert "Testing Net Profit" in text


def test_dashboard_contains_parameters(tmp_path):
    report = build_report()

    html = tmp_path / "dashboard.html"

    WalkForwardOptimizationDashboardExporter().export_html(
        report,
        html,
    )

    text = html.read_text(
        encoding="utf-8",
    )

    assert "ema_period" in text
    assert "rsi_period" in text


def test_dashboard_contains_window_table(tmp_path):
    report = build_report()

    html = tmp_path / "dashboard.html"

    WalkForwardOptimizationDashboardExporter().export_html(
        report,
        html,
    )

    text = html.read_text(
        encoding="utf-8",
    )

    assert "<table" in text
    assert "Window" in text
    assert "Training" in text
    assert "Testing" in text


def test_dashboard_creates_parent_directory(tmp_path):
    html = (
        tmp_path
        / "reports"
        / "dashboard.html"
    )

    WalkForwardOptimizationDashboardExporter().export_html(
        build_report(),
        html,
    )

    assert html.exists()
