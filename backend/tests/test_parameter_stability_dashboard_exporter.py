from backend.backtesting.parameter_stability_analyzer import (
    ParameterStabilityAnalysis,
    ParameterStabilitySummary,
)
from backend.backtesting.parameter_stability_dashboard_exporter import (
    ParameterStabilityDashboardExporter,
)


def build_analysis() -> ParameterStabilityAnalysis:
    return ParameterStabilityAnalysis(
        total_windows=4,
        parameters={
            "ema_period": ParameterStabilitySummary(
                name="ema_period",
                total_observations=4,
                frequencies={
                    25: 3,
                    50: 1,
                },
                dominant_value=25,
                dominant_count=3,
                dominant_rate=75.0,
                stability_score=75.0,
            ),
            "rsi_period": ParameterStabilitySummary(
                name="rsi_period",
                total_observations=4,
                frequencies={
                    10: 1,
                    14: 2,
                    21: 1,
                },
                dominant_value=14,
                dominant_count=2,
                dominant_rate=50.0,
                stability_score=50.0,
            ),
            "atr_period": ParameterStabilitySummary(
                name="atr_period",
                total_observations=4,
                frequencies={
                    10: 3,
                    20: 1,
                },
                dominant_value=10,
                dominant_count=3,
                dominant_rate=75.0,
                stability_score=75.0,
            ),
            "risk_percent": ParameterStabilitySummary(
                name="risk_percent",
                total_observations=4,
                frequencies={
                    0.75: 3,
                    0.5: 1,
                },
                dominant_value=0.75,
                dominant_count=3,
                dominant_rate=75.0,
                stability_score=75.0,
            ),
        },
        overall_stability_score=68.75,
    )


def test_dashboard_exporter_creates_html(
    tmp_path,
):
    file_path = tmp_path / "stability.html"

    returned_path = (
        ParameterStabilityDashboardExporter()
        .export_html(
            analysis=build_analysis(),
            file_path=file_path,
        )
    )

    assert returned_path == file_path
    assert file_path.exists()


def test_dashboard_contains_summary(
    tmp_path,
):
    file_path = tmp_path / "stability.html"

    ParameterStabilityDashboardExporter().export_html(
        analysis=build_analysis(),
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "Parameter Stability Dashboard" in html
    assert "Overall Stability" in html
    assert "68.75" in html
    assert "Total Windows" in html
    assert "metric-value" in html
    assert "4" in html


def test_dashboard_contains_parameter_details(
    tmp_path,
):
    file_path = tmp_path / "stability.html"

    ParameterStabilityDashboardExporter().export_html(
        analysis=build_analysis(),
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "ema_period" in html
    assert "rsi_period" in html
    assert "atr_period" in html
    assert "risk_percent" in html

    assert "Dominant Value" in html
    assert "Dominant Rate" in html
    assert "75.00%" in html
    assert "50.00%" in html


def test_dashboard_contains_frequency_data(
    tmp_path,
):
    file_path = tmp_path / "stability.html"

    ParameterStabilityDashboardExporter().export_html(
        analysis=build_analysis(),
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert '"25": 3' in html
    assert '"50": 1' in html
    assert '"14": 2' in html
    assert "stability-chart" in html


def test_dashboard_creates_parent_directory(
    tmp_path,
):
    file_path = (
        tmp_path
        / "reports"
        / "parameter_stability.html"
    )

    ParameterStabilityDashboardExporter().export_html(
        analysis=build_analysis(),
        file_path=file_path,
    )

    assert file_path.exists()


def test_dashboard_handles_empty_analysis(
    tmp_path,
):
    analysis = ParameterStabilityAnalysis(
        total_windows=0,
        parameters={},
        overall_stability_score=0.0,
    )

    file_path = tmp_path / "stability.html"

    ParameterStabilityDashboardExporter().export_html(
        analysis=analysis,
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "Parameter Stability Dashboard" in html
    assert "No parameter stability data available." in html
