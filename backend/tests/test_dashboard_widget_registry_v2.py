import pytest

from backend.dashboard.widgets.dashboard_widget_registry_v2 import (
    DashboardWidgetRegistryV2,
)


class FakeWidget:

    def __init__(
        self,
        *,
        name,
        status="READY",
    ):
        self.name = name
        self.status = status

    def render(self):
        return {
            "widget": self.name,
            "status": self.status,
            "data": {
                "value": self.name,
            },
        }


def build_registry(
    widgets=None,
):
    return DashboardWidgetRegistryV2(
        widgets=widgets,
    )


def test_accepts_none_widgets():
    registry = build_registry()

    assert registry.widgets == []


def test_accepts_valid_widgets():
    widgets = [
        FakeWidget(
            name="performance_score",
        ),
        FakeWidget(
            name="account_overview",
        ),
    ]

    registry = build_registry(
        widgets=widgets,
    )

    assert registry.widgets == widgets


def test_rejects_invalid_widgets_type():
    with pytest.raises(
        TypeError,
        match="widgets",
    ):
        build_registry(
            widgets=object(),
        )


def test_rejects_widget_without_render():
    with pytest.raises(
        TypeError,
        match="render",
    ):
        build_registry(
            widgets=[
                object(),
            ],
        )


def test_renders_empty_registry():
    registry = build_registry()

    result = registry.render_all()

    assert result["status"] == "EMPTY"
    assert result["widgets"] == {}
    assert result["widget_count"] == 0


def test_renders_all_widgets():
    registry = build_registry(
        widgets=[
            FakeWidget(
                name="performance_score",
            ),
            FakeWidget(
                name="account_overview",
            ),
            FakeWidget(
                name="risk_status",
            ),
        ],
    )

    result = registry.render_all()

    assert result["status"] == "READY"
    assert result["widget_count"] == 3

    assert (
        result["widgets"][
            "performance_score"
        ]["data"]["value"]
        == "performance_score"
    )

    assert (
        result["widgets"][
            "account_overview"
        ]["status"]
        == "READY"
    )

    assert (
        result["widgets"][
            "risk_status"
        ]["widget"]
        == "risk_status"
    )


def test_detects_blocked_widget():
    registry = build_registry(
        widgets=[
            FakeWidget(
                name="performance_score",
            ),
            FakeWidget(
                name="risk_status",
                status="BLOCKED",
            ),
        ],
    )

    result = registry.render_all()

    assert result["status"] == "BLOCKED"


def test_detects_all_empty_widgets():
    registry = build_registry(
        widgets=[
            FakeWidget(
                name="performance_score",
                status="EMPTY",
            ),
            FakeWidget(
                name="account_overview",
                status="EMPTY",
            ),
        ],
    )

    result = registry.render_all()

    assert result["status"] == "EMPTY"
    assert result["widget_count"] == 2


def test_rejects_invalid_render_result():
    class InvalidWidget:

        def render(self):
            return object()

    registry = build_registry(
        widgets=[
            InvalidWidget(),
        ],
    )

    with pytest.raises(
        TypeError,
        match="render",
    ):
        registry.render_all()
