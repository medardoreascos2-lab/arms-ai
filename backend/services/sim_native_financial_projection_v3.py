"""Durable presentation consumer. Native checkpoint remains financial authority."""
from copy import deepcopy
import json

from backend.services.durable_execution_state_v2 import atomic_write, canonical
from backend.services.sim_native_authority_v3 import safe_path
from backend.services.sim_native_financial_checkpoint_v3 import execution_values


class SimNativeFinancialProjectionV3:
    SCHEMA = "SIM_NATIVE_DASHBOARD_PROJECTION_V3"

    def __init__(self, *, store, path):
        self.store = store
        self.path = safe_path(path, authority=True)

    def _events(self):
        store = self.store
        events = {}
        for event_id, event in store._native["outbox"].items():
            role, price, _ = execution_values(store._native["executions"][event["execution_id"]])
            events[event_id] = {**event, "event_id": event_id, "position_id": store.position_id,
                                "order_role": role, "execution_price": float(price)}
        return events

    def _document(self, events):
        # Canonical role ordering, independent of hash order or transport retries.
        ordered = sorted(events.values(), key=lambda event: (event["order_role"] != "ENTRY", event["event_id"]))
        return {"schema": self.SCHEMA, "identity": self.store.binding.claims(), "events": events,
                "processed_event_count": len(events),
                "last_financial_event_id": ordered[-1]["event_id"] if ordered else None}

    def read(self):
        safe_path(self.path, authority=True)
        if not self.path.exists():
            return self._document({})
        with self.path.open("rb") as stream:
            raw = stream.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ValueError("oversized financial projection")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate projection field")
                result[key] = value
            return result
        document = json.loads(raw, object_pairs_hook=unique)
        events = document.get("events") if type(document) is dict else None
        expected = self._events()
        if (type(events) is not dict or any(expected.get(key) != value for key, value in events.items())
                or canonical(document) != canonical(self._document(events))):
            raise ValueError("projection does not match canonical financial evidence")
        return document

    def rebuild(self):
        """Explicit startup reconstruction, including previously acknowledged events."""
        with self.store._durability.admission_barrier():
            self.store.receipt()
            previous = self.read()  # Corruption is never silently repaired.
            document = self._document(self._events())
            if previous != document or not self.path.exists():
                self._write(document)

    def _write(self, document):
        safe_path(self.path, authority=True)
        safe_path(self.path.with_suffix(self.path.suffix + ".tmp"), authority=True)
        atomic_write(self.path, document)

    def publish(self, *, event_type, payload):
        with self.store._durability.admission_barrier():
            self.store.receipt()
            expected = self._events().get(payload.get("event_id")) if type(payload) is dict else None
            if expected is None or any(payload.get(k) != v for k, v in expected.items() if k != "execution_price"):
                raise ValueError("unbound SIM_NATIVE projection event")
            role = expected["order_role"]
            if event_type != ("trade_opened" if role == "ENTRY" else "trade_closed"):
                raise ValueError("native projection event role mismatch")
            price_field = "entry_price" if role == "ENTRY" else "exit_price"
            if type(payload.get(price_field)) not in (float, int) or payload[price_field] != expected["execution_price"]:
                raise ValueError("native projection execution price mismatch")
            entry = next(execution_values(value) for value in self.store._native["executions"].values()
                         if execution_values(value)[0] == "ENTRY")
            position = (self.store._position(entry[1], entry[2]) if role == "ENTRY" else
                        self.store.trade_lifecycle_service.portfolio_manager_v2.get_closed_positions()[0])
            if any(payload.get(key) != value for key, value in position.items()):
                raise ValueError("projection position differs from canonical financial state")
            previous = self.read()
            events = deepcopy(previous["events"])
            event_id = expected["event_id"]
            if event_id not in events:
                events[event_id] = expected
                # Effect and dedup identity share one fsynced atomic replacement.
                self._write(self._document(events))
            return {"published": True, "listener_errors": 0}
