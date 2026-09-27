"""Fail-closed SIM execution activation gate.

This gate has no native order transport surface.
It only decides whether the current SIM runtime may be considered ARMED.

Any failed revalidation revokes the gate for the lifetime of the instance.
"""

from __future__ import annotations

from copy import deepcopy


class SimExecutionActivationGateV2:
    ARM_TOKEN = "ARM_SIM_EXECUTION_V2"

    def __init__(
        self,
        *,
        binding_probe,
        health_probe,
        recovery_probe,
        native_inventory_probe,
        ack_capability_probe,
        mutation_capability_probe,
    ) -> None:
        probes = {
            "binding_probe": binding_probe,
            "health_probe": health_probe,
            "recovery_probe": recovery_probe,
            "native_inventory_probe": native_inventory_probe,
            "ack_capability_probe": ack_capability_probe,
            "mutation_capability_probe": mutation_capability_probe,
        }

        for name, probe in probes.items():
            if not callable(probe):
                raise TypeError(
                    f"{name} must be callable."
                )

        self.binding_probe = binding_probe
        self.health_probe = health_probe
        self.recovery_probe = recovery_probe
        self.native_inventory_probe = (
            native_inventory_probe
        )
        self.ack_capability_probe = (
            ack_capability_probe
        )
        self.mutation_capability_probe = (
            mutation_capability_probe
        )

        self._state = "DISABLED"
        self._reason = "not_armed"

    def _projection(self) -> dict[str, object]:
        armed = self._state == "ARMED"

        return {
            "state": self._state,
            "armed": armed,
            "reason": self._reason,
            "sim_execution_authority": (
                "ARMED"
                if armed
                else "DISABLED"
            ),
            "external_order_authority": armed,
        }

    def status(self) -> dict[str, object]:
        return deepcopy(
            self._projection()
        )

    def _evaluate_preconditions(
        self,
    ) -> str | None:
        binding = self.binding_probe()

        if (
            type(binding) is not dict
            or binding.get(
                "future_sim_eligible"
            ) is not True
            or binding.get(
                "sim_runtime_revalidation"
            ) != "PASS"
            or binding.get(
                "sim_execution_authority"
            ) != "DISABLED"
            or binding.get(
                "external_order_authority"
            ) is not False
        ):
            return "binding_not_eligible"

        health = self.health_probe()

        if (
            type(health) is not dict
            or health.get("healthy") is not True
            or health.get("connected") is not True
            or health.get("execution_mode") != "SIM"
            or health.get(
                "sim_execution_authority"
            ) != "DISABLED"
            or health.get(
                "external_order_authority"
            ) is not False
        ):
            return "native_health_not_ready"

        recovery = self.recovery_probe()

        if (
            type(recovery) is not dict
            or recovery.get("resolved") is not True
            or recovery.get("status")
            not in {
                "CONFIRMED_NOT_EXECUTED",
                "CONFIRMED_EXECUTED",
            }
        ):
            return "pending_recovery_unresolved"

        inventory = (
            self.native_inventory_probe()
        )

        if type(inventory) is not dict:
            return "native_inventory_ambiguous"

        for key in (
            "ambiguous_orders",
            "ambiguous_positions",
            "unresolved_orders",
            "unresolved_positions",
        ):
            value = inventory.get(key)

            if (
                type(value) is not int
                or value != 0
            ):
                return (
                    "native_inventory_ambiguous"
                )

        ack = self.ack_capability_probe()

        if (
            type(ack) is not dict
            or ack.get(
                "ack_submit_enabled"
            ) is not True
            or ack.get("scope")
            != "SIM_ACK_TEST_ONLY"
        ):
            return "ack_capability_missing"

        mutation = (
            self.mutation_capability_probe()
        )

        if (
            type(mutation) is not dict
            or mutation.get(
                "native_mutation_enabled"
            ) is not True
            or mutation.get("scope")
            != "SIM_MUTATION_TEST_ONLY"
        ):
            return "mutation_capability_missing"

        return None

    def arm(
        self,
        *,
        operator_token: str,
    ) -> dict[str, object]:
        if self._state == "REVOKED":
            raise RuntimeError(
                "activation gate is revoked."
            )

        if (
            type(operator_token) is not str
            or operator_token.strip()
            != self.ARM_TOKEN
        ):
            raise ValueError(
                "explicit operator arm token required."
            )

        reason = (
            self._evaluate_preconditions()
        )

        if reason is not None:
            self._state = "DISABLED"
            self._reason = reason

            return self.status()

        self._state = "ARMED"
        self._reason = "all_preconditions_passed"

        return self.status()

    def revalidate(
        self,
    ) -> dict[str, object]:
        if self._state == "REVOKED":
            return self.status()

        if self._state != "ARMED":
            return self.status()

        reason = (
            self._evaluate_preconditions()
        )

        if reason is not None:
            self._state = "REVOKED"
            self._reason = reason

        return self.status()

    def revoke(
        self,
        *,
        reason: str,
    ) -> dict[str, object]:
        if (
            type(reason) is not str
            or not reason.strip()
        ):
            raise ValueError(
                "reason is required."
            )

        self._state = "REVOKED"
        self._reason = reason.strip()

        return self.status()
