"""Explicit native-simulation identity; no discovery or execution authority.

IDs follow the existing account catalog's opaque uppercase key convention.
Risk profiles come from AccountRegistryV1, never from native account labels.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re

from backend.accounts.account_config_manager_v2 import AccountConfigManagerV2
from backend.accounts.account_registry_v1 import AccountRegistryV1
from backend.instruments.instrument_profile_engine import InstrumentProfileEngine


DEFAULT_BINDING = Path(__file__).resolve().parents[1] / "config/sim_native_accounts_v3.json"
CLAIM_NAMES = ("backend_account_id", "execution_domain", "risk_profile_id", "risk_profile_digest",
               "ledger_id", "journal_account_id", "instrument_authority_id", "binding_digest")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class SimNativeAccountV3:
    backend_account_id: str
    execution_domain: str
    provider: str
    native_account_name: str
    risk_profile_id: str
    ledger_id: str
    journal_account_id: str
    instrument: str
    instrument_root: str
    enabled: bool
    execution_capability: str
    runtime_generation: int
    risk_profile_digest: str
    instrument_authority_id: str

    def __post_init__(self):
        if ((self.execution_domain, self.provider, self.native_account_name) != ("SIM_NATIVE", "Simulator", "Sim101")
                or type(self.backend_account_id) is not str or not re.fullmatch(r"SIM_NATIVE-[A-F0-9]{32}", self.backend_account_id)
                or self.ledger_id != self.backend_account_id or self.journal_account_id != self.backend_account_id
                or self.enabled is not True or self.execution_capability != "DISABLED"
                or type(self.runtime_generation) is not int or self.runtime_generation < 1
                or self.instrument_root != "NQ" or not re.fullmatch(r"NQ [A-Z]{3}[0-9]{2}", self.instrument)):
            raise ValueError("invalid native-simulation account authority")
        if self.risk_profile_id not in AccountRegistryV1().list_accounts():
            raise ValueError("explicit canonical risk profile required")
        profile = AccountRegistryV1().get_account(self.risk_profile_id)
        instrument = InstrumentProfileEngine().get_profile(symbol=self.instrument_root)
        if (digest(asdict(profile)) != self.risk_profile_digest
                or digest({"contract": self.instrument, "profile": instrument}) != self.instrument_authority_id):
            raise ValueError("canonical risk/instrument authority digest mismatch")

    @classmethod
    def resolve(cls, *, document, execution_domain, provider, native_account_name, registry=None):
        # No fallback, normalization, wildcard, or best-effort account selection.
        if (execution_domain, provider, native_account_name) != ("SIM_NATIVE", "Simulator", "Sim101"):
            raise ValueError("unknown native-simulation account/domain/provider")
        if type(document) is not dict or set(document) != {"version", "accounts"} or document["version"] != 3:
            raise ValueError("explicit native-simulation catalog required")
        rows = document["accounts"]
        if type(rows) is not list or len(rows) != 1 or type(rows[0]) is not dict:
            raise ValueError("exactly one controlled native-simulation account required")
        row = deepcopy(rows[0])
        expected = set(cls.__dataclass_fields__) - {"risk_profile_digest", "instrument_authority_id"}
        if set(row) != expected:
            raise ValueError("incomplete native-simulation binding")
        if (row["execution_domain"], row["provider"], row["native_account_name"]) != (
                execution_domain, provider, native_account_name):
            raise ValueError("native-simulation binding mismatch")
        account_id = row["backend_account_id"]
        if (type(account_id) is not str or not re.fullmatch(r"SIM_NATIVE-[A-F0-9]{32}", account_id)
                or row["ledger_id"] != account_id or row["journal_account_id"] != account_id
                or row["enabled"] is not True or row["execution_capability"] != "DISABLED"
                or type(row["runtime_generation"]) is not int or row["runtime_generation"] < 1):
            raise ValueError("invalid native-simulation authority")
        registry = registry or AccountRegistryV1()
        profile_id = row["risk_profile_id"]
        if type(profile_id) is not str or profile_id not in registry.list_accounts():
            raise ValueError("explicit canonical risk profile required")
        profile = registry.get_account(profile_id)
        instrument = InstrumentProfileEngine().get_profile(symbol=row["instrument_root"])
        if (row["instrument_root"] != "NQ" or type(row["instrument"]) is not str
                or not re.fullmatch(r"NQ [A-Z]{3}[0-9]{2}", row["instrument"])
                or profile.get_contract_limit(instrument["contract_class"]) < 1):
            raise ValueError("controlled instrument authority mismatch")
        return cls(**row, risk_profile_digest=digest(asdict(profile)),
                   instrument_authority_id=digest({"contract": row["instrument"], "profile": instrument}))

    @classmethod
    def load(cls, *, path=DEFAULT_BINDING, **selection):
        return cls.resolve(document=json.loads(Path(path).read_text(encoding="utf-8")), **selection)

    def claims(self):
        values = asdict(self)
        return {**{name: values[name] for name in CLAIM_NAMES if name != "binding_digest"},
                "binding_digest": digest(values)}

    def assert_claims(self, values):
        expected = {**self.claims(), "account": self.native_account_name, "provider": self.provider,
                    "instrument": self.instrument, "runtime_generation": str(self.runtime_generation)}
        if any(type(values.get(k)) is not str or values[k] != v for k, v in expected.items()):
            raise ValueError("native-simulation account/risk/instrument/generation mismatch")

    def manager(self, *, registry=None):
        registry = registry or AccountRegistryV1()
        if digest(asdict(registry.get_account(self.risk_profile_id))) != self.risk_profile_digest:
            raise ValueError("canonical risk profile changed")
        return AccountConfigManagerV2.for_runtime(config_path=DEFAULT_BINDING, registry=registry,
                                                  profile_name=self.risk_profile_id)

    def checkpoint_path(self, root):
        root = Path(root).resolve()
        path = root / "SIM_NATIVE" / self.backend_account_id / "runtime-state.json"
        if path.resolve().parent.parent != root / "SIM_NATIVE":
            raise ValueError("native-simulation namespace escape")
        return path
