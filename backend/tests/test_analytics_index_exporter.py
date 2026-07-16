from backend.backtesting.analytics_index_exporter import (
    AnalyticsIndexExporter,
)


def test_analytics_index_exporter_creates_html(
    tmp_path,
):
    file_path = tmp_path / "index.html"

    returned = AnalyticsIndexExporter().export_html(
        file_path=file_path,
        backtest_dashboard="backtest_dashboard.html",
        walk_forward_dashboard=(
            "walk_forward_dashboard.html"
        ),
        optimization_dashboard=(
            "walk_forward_optimization_dashboard.html"
        ),
        parameter_stability_dashboard=(
            "parameter_stability_dashboard.html"
        ),
    )

    assert returned == file_path
    assert file_path.exists()


def test_analytics_index_contains_dashboard_links(
    tmp_path,
):
    file_path = tmp_path / "index.html"

    AnalyticsIndexExporter().export_html(
        file_path=file_path,
        backtest_dashboard="backtest_dashboard.html",
        walk_forward_dashboard=(
            "walk_forward_dashboard.html"
        ),
        optimization_dashboard=(
            "walk_forward_optimization_dashboard.html"
        ),
        parameter_stability_dashboard=(
            "parameter_stability_dashboard.html"
        ),
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "ARMS AI Analytics" in html

    assert (
        'href="backtest_dashboard.html"'
        in html
    )
    assert (
        'href="walk_forward_dashboard.html"'
        in html
    )
    assert (
        'href="walk_forward_optimization_dashboard.html"'
        in html
    )
    assert (
        'href="parameter_stability_dashboard.html"'
        in html
    )


def test_analytics_index_contains_section_names(
    tmp_path,
):
    file_path = tmp_path / "index.html"

    AnalyticsIndexExporter().export_html(
        file_path=file_path,
        backtest_dashboard="backtest.html",
        walk_forward_dashboard="walk_forward.html",
        optimization_dashboard="optimization.html",
        parameter_stability_dashboard="stability.html",
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "Backtest" in html
    assert "Walk Forward" in html
    assert "Optimization" in html
    assert "Parameter Stability" in html


def test_analytics_index_creates_parent_directory(
    tmp_path,
):
    file_path = (
        tmp_path
        / "reports"
        / "index.html"
    )

    AnalyticsIndexExporter().export_html(
        file_path=file_path,
    )

    assert file_path.exists()


def test_analytics_index_handles_missing_links(
    tmp_path,
):
    file_path = tmp_path / "index.html"

    AnalyticsIndexExporter().export_html(
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "ARMS AI Analytics" in html
    assert "Not generated yet" in html
