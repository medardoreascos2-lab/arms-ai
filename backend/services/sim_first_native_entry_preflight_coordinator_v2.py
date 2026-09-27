from __future__ import annotations

from typing import Any


class SimFirstNativeEntryPreflightCoordinatorV2:
    REQUIRED_RUNTIME_FIELDS = {
        "account_name",
        "provider",
        "connection_status",
        "physical_test_readiness",
        "position_state",
        "active_order_count",
        "native_submit_enabled",
        "auto_retry_allowed",
    }

    REQUIRED_ACTIVATION_FIELDS = {
        "valid",
        "consumed",
        "command_id",
        "operation_id",
        "client_order_id",
    }

    REQUIRED_COMMAND_FIELDS = {
        "command_id",
        "operation_id",
        "client_order_id",
    }

    def __init__(
        self,
        *,
        preflight: Any,
        runtime_source: Any,
        activation_source: Any,
        recovery_capability: Any,
        native_evidence_capability: Any,
    ) -> None:
        if not callable(
            getattr(
                preflight,
                "evaluate",
                None,
            )
        ):
            raise TypeError(
                "preflight must provide evaluate()."
            )

        if not callable(
            getattr(
                runtime_source,
                "snapshot",
                None,
            )
        ):
            raise TypeError(
                "runtime_source must provide snapshot()."
            )

        if not callable(
            getattr(
                activation_source,
                "inspect",
                None,
            )
        ):
            raise TypeError(
                "activation_source must provide inspect()."
            )

        if not callable(
            getattr(
                recovery_capability,
                "is_available",
                None,
            )
        ):
            raise TypeError(
                "recovery_capability must provide is_available()."
            )

        if not callable(
            getattr(
                native_evidence_capability,
                "is_available",
                None,
            )
        ):
            raise TypeError(
                "native_evidence_capability must provide is_available()."
            )

        self.preflight = preflight
        self.runtime_source = runtime_source
        self.activation_source = activation_source
        self.recovery_capability = (
            recovery_capability
        )
        self.native_evidence_capability = (
            native_evidence_capability
        )

    @staticmethod
    def _require_dict(
        value: Any,
        *,
        label: str,
    ) -> dict[str, Any]:
        if type(value) is not dict:
            raise RuntimeError(
                f"{label} must be a dict"
            )

        return value

    @staticmethod
    def _require_fields(
        value: dict[str, Any],
        *,
        required: set[str],
        label: str,
    ) -> None:
        missing = required - set(value)

        if missing:
            raise RuntimeError(
                f"{label} missing required fields: "
                + ",".join(
                    sorted(missing)
                )
            )

    def evaluate(
        self,
        *,
        command: Any,
    ) -> dict[str, object]:
        command = self._require_dict(
            command,
            label="command",
        )

        self._require_fields(
            command,
            required=self.REQUIRED_COMMAND_FIELDS,
            label="command",
        )

        runtime = self.runtime_source.snapshot()

        runtime = self._require_dict(
            runtime,
            label="runtime snapshot",
        )

        self._require_fields(
            runtime,
            required=self.REQUIRED_RUNTIME_FIELDS,
            label="runtime snapshot",
        )

        activation = (
            self.activation_source.inspect(
                command_id=command[
                    "command_id"
                ],
            )
        )

        activation = self._require_dict(
            activation,
            label="activation snapshot",
        )

        self._require_fields(
            activation,
            required=self.REQUIRED_ACTIVATION_FIELDS,
            label="activation snapshot",
        )

        if (
            activation["command_id"]
            != command["command_id"]
            or activation["operation_id"]
            != command["operation_id"]
            or activation["client_order_id"]
            != command["client_order_id"]
        ):
            raise RuntimeError(
                "activation durable identity does not match command"
            )

        recovery_available = (
            self.recovery_capability
            .is_available()
        )

        native_evidence_available = (
            self.native_evidence_capability
            .is_available()
        )

        return self.preflight.evaluate(
            account_name=runtime[
                "account_name"
            ],
            provider=runtime[
                "provider"
            ],
            connection_status=runtime[
                "connection_status"
            ],
            physical_test_readiness=runtime[
                "physical_test_readiness"
            ],
            position_state=runtime[
                "position_state"
            ],
            active_order_count=runtime[
                "active_order_count"
            ],
            activation_valid=activation[
                "valid"
            ],
            activation_consumed=activation[
                "consumed"
            ],
            command_id=command[
                "command_id"
            ],
            operation_id=command[
                "operation_id"
            ],
            client_order_id=command[
                "client_order_id"
            ],
            native_submit_enabled=runtime[
                "native_submit_enabled"
            ],
            auto_retry_allowed=runtime[
                "auto_retry_allowed"
            ],
            recovery_available=(
                recovery_available is True
            ),
            native_evidence_available=(
                native_evidence_available
                is True
            ),
        )
