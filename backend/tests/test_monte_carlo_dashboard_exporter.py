from backend.backtesting.monte_carlo_dashboard_exporter import (
    MonteCarloDashboardExporter,
)
from backend.backtesting.monte_carlo_report import (
    MonteCarloReport,
)


def build_report() -> MonteCarloReport:
    return MonteCarloReport(
        total_simulations=1000,
        average_final_balance=11250.0,
        median_final_balance=11180.0,
        best_final_balance=13800.0,
        worst_final_balance=8700.0,
        average_max_drawdown=950.0,
        worst_max_drawdown=2400.0,
        loss_probability=7.5,
        ruin_probability=1.2,
        final_balance_percentile_5=9400.0,
        final_balance_percentile_50=11180.0,
        final_balance_percentile_95=12950.0,
        drawdown_percentile_50=880.0,
        drawdown_percentile_95=1850.0,
        drawdown_percentile_99=2200.0,
    )


def test_monte_carlo_dashboard_creates_html(
    tmp_path,
):
    file_path = tmp_path / "monte_carlo.html"

    returned_path = (
        MonteCarloDashboardExporter()
        .export_html(
            report=build_report(),
            file_path=file_path,
        )
    )

    assert returned_path == file_path
    assert file_path.exists()


def test_monte_carlo_dashboard_contains_summary(
    tmp_path,
):
    file_path = tmp_path / "monte_carlo.html"

    MonteCarloDashboardExporter().export_html(
        report=build_report(),
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "Monte Carlo Dashboard" in html
    assert "Simulation Method" in html
    assert "shuffle" in html
    assert "Total Simulations" in html
    assert "1000" in html

    assert "Average Final Balance" in html
    assert "11250.00" in html

    assert "Worst Final Balance" in html
    assert "8700.00" in html


def test_monte_carlo_dashboard_contains_risk_metrics(
    tmp_path,
):
    file_path = tmp_path / "monte_carlo.html"

    MonteCarloDashboardExporter().export_html(
        report=build_report(),
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "Average Max Drawdown" in html
    assert "950.00" in html

    assert "Worst Max Drawdown" in html
    assert "2400.00" in html

    assert "Loss Probability" in html
    assert "7.50%" in html

    assert "Ruin Probability" in html
    assert "1.20%" in html


def test_monte_carlo_dashboard_contains_percentiles(
    tmp_path,
):
    file_path = tmp_path / "monte_carlo.html"

    MonteCarloDashboardExporter().export_html(
        report=build_report(),
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "Final Balance Percentiles" in html
    assert "9400.00" in html
    assert "11180.00" in html
    assert "12950.00" in html

    assert "Drawdown Percentiles" in html
    assert "880.00" in html
    assert "1850.00" in html
    assert "2200.00" in html


def test_monte_carlo_dashboard_contains_charts(
    tmp_path,
):
    file_path = tmp_path / "monte_carlo.html"

    MonteCarloDashboardExporter().export_html(
        report=build_report(),
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "final-balance-chart" in html
    assert "drawdown-chart" in html
    assert "new Chart" in html


def test_monte_carlo_dashboard_creates_parent_directory(
    tmp_path,
):
    file_path = (
        tmp_path
        / "reports"
        / "monte_carlo.html"
    )

    MonteCarloDashboardExporter().export_html(
        report=build_report(),
        file_path=file_path,
    )

    assert file_path.exists()
