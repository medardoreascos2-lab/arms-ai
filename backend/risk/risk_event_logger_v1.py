from datetime import datetime, timezone


class RiskEventLoggerV1:
    """
    Registro de eventos de riesgo
    de ARMS AI.
    """


    def __init__(
        self,
    ):

        self.events = []



    def log_event(
        self,
        event: dict,
    ):

        record = {

            "timestamp":
                datetime.now(timezone.utc)
                .isoformat(),

            **event,

        }


        self.events.append(
            record
        )


        return record



    def get_events(
        self,
    ):

        return self.events
