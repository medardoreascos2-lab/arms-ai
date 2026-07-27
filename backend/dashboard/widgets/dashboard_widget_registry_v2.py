from __future__ import annotations


class DashboardWidgetRegistryV2:

    def __init__(
        self,
        *,
        widgets=None,
    ) -> None:

        if widgets is None:
            widgets = []

        if not isinstance(
            widgets,
            list,
        ):
            raise TypeError(
                "widgets debe ser una lista."
            )

        for widget in widgets:
            if not callable(
                getattr(
                    widget,
                    "render",
                    None,
                )
            ):
                raise TypeError(
                    "Cada widget debe implementar render()."
                )

        self.widgets = widgets

    def render_all(
        self,
    ) -> dict[str, object]:

        if not self.widgets:
            return {
                "status": "EMPTY",
                "widget_count": 0,
                "widgets": {},
            }

        rendered_widgets: dict[str, dict] = {}

        statuses: list[str] = []

        for widget in self.widgets:

            result = widget.render()

            if not isinstance(
                result,
                dict,
            ):
                raise TypeError(
                    "render() debe devolver un dict."
                )

            widget_name = result.get(
                "widget"
            )

            rendered_widgets[
                str(widget_name)
            ] = result

            statuses.append(
                str(
                    result.get(
                        "status",
                        "READY",
                    )
                )
            )

        if any(
            status == "BLOCKED"
            for status in statuses
        ):
            overall_status = "BLOCKED"

        elif all(
            status == "EMPTY"
            for status in statuses
        ):
            overall_status = "EMPTY"

        else:
            overall_status = "READY"

        return {
            "status": overall_status,
            "widget_count": len(
                rendered_widgets
            ),
            "widgets": rendered_widgets,
        }
