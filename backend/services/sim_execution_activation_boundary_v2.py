"""Activation boundary between the SIM gate and connector capabilities.

This object exposes capability probes only.
It has no native order transport surface.

Every capability read revalidates the activation gate first.
"""

from __future__ import annotations

from copy import deepcopy


class SimExecutionActivationBoundaryV2:
    def __init__(
        self,
        *,
        gate,
        ack_capability_probe,
        mutation_capability_probe,
    ) -> None:
        if gate is None:
            raise TypeError(
                "gate is required."
            )

        if not callable(
            getattr(
                gate,
                "status",
                None,
            )
        ):
            raise TypeError(
                "gate must provide status()."
            )

        if not callable(
            getattr(
                gate,
                "revalidate",
                None,
            )
        ):
            raise TypeError(
                "gate must provide revalidate()."
            )

        if not callable(
            ack_capability_probe
        ):
            raise TypeError(
                "ack_capability_probe must be callable."
            )

        if not callable(
            mutation_capability_probe
        ):
            raise TypeError(
                "mutation_capability_probe must be callable."
            )

        self.gate = gate
        self._raw_ack_capability_probe = (
            ack_capability_probe
        )
        self._raw_mutation_capability_probe = (
            mutation_capability_probe
        )

    def status(
        self,
    ) -> dict[str, object]:
        state = self.gate.status()

        if type(state) is not dict:
            raise RuntimeError(
                "invalid activation gate state."
            )

        return {
            "state": state.get(
                "state",
                "DISABLED",
            ),
            "armed": (
                state.get("armed") is True
            ),
            "external_order_authority": (
                state.get(
                    "external_order_authority"
                )
                is True
            ),
        }

    def _require_armed_gate(
        self,
    ) -> dict[str, object]:
        state = self.gate.revalidate()

        if (
            type(state) is not dict
            or state.get("state") != "ARMED"
            or state.get("armed") is not True
            or state.get(
                "external_order_authority"
            ) is not True
        ):
            raise RuntimeError(
                "SIM execution authority is disabled."
            )

        return deepcopy(state)

    def ack_authority_probe(
        self,
    ) -> dict[str, object]:
        self._require_armed_gate()

        capability = (
            self._raw_ack_capability_probe()
        )

        if (
            type(capability) is not dict
            or capability.get(
                "ack_submit_enabled"
            ) is not True
            or capability.get("scope")
            != "SIM_ACK_TEST_ONLY"
        ):
            raise RuntimeError(
                "SIM execution authority is disabled."
            )

        return deepcopy(capability)

    def mutation_authority_probe(
        self,
    ) -> dict[str, object]:
        self._require_armed_gate()

        capability = (
            self._raw_mutation_capability_probe()
        )

        if (
            type(capability) is not dict
            or capability.get(
                "native_mutation_enabled"
            ) is not True
            or capability.get("scope")
            != "SIM_MUTATION_TEST_ONLY"
        ):
            raise RuntimeError(
                "SIM execution authority is disabled."
            )

        return deepcopy(capability)
