from __future__ import annotations

from pathlib import Path
from typing import Any


class SimNativeEvidenceCapabilityV2:
    """
    Structural availability probe for native SIM evidence infrastructure.

    Availability means:
    - a reader exists,
    - it exposes read_for_command(),
    - its configured evidence directory still exists and is a directory.

    It does NOT read command evidence.
    """

    def __init__(
        self,
        *,
        evidence_reader: Any,
    ) -> None:
        self._evidence_reader = evidence_reader

    def is_available(
        self,
    ) -> bool:
        reader = self._evidence_reader

        if reader is None:
            return False

        if not callable(
            getattr(
                reader,
                "read_for_command",
                None,
            )
        ):
            return False

        directory = getattr(
            reader,
            "_directory",
            None,
        )

        if directory is None:
            return False

        try:
            path = Path(directory)

            return (
                path.exists()
                and path.is_dir()
            )
        except (
            OSError,
            TypeError,
            ValueError,
        ):
            return False


class SimNativeRecoveryCapabilityV2:
    """
    Structural availability probe for native SIM recovery infrastructure.

    Availability means:
    - recovery exposes reconcile(),
    - it is wired to a broker_connector,
    - broker_connector.execution_mode is exactly SIM.

    It never calls reconcile().
    """

    def __init__(
        self,
        *,
        recovery: Any,
    ) -> None:
        self._recovery = recovery

    def is_available(
        self,
    ) -> bool:
        recovery = self._recovery

        if recovery is None:
            return False

        if not callable(
            getattr(
                recovery,
                "reconcile",
                None,
            )
        ):
            return False

        broker_connector = getattr(
            recovery,
            "broker_connector",
            None,
        )

        if broker_connector is None:
            return False

        execution_mode = getattr(
            broker_connector,
            "execution_mode",
            None,
        )

        return (
            type(execution_mode) is str
            and execution_mode.strip().upper()
            == "SIM"
        )
