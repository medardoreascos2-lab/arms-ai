"""Explicit crypto asset and network identities for analysis only."""

from dataclasses import dataclass
from enum import Enum


class CryptoAssetKind(str, Enum):
    UNKNOWN = "UNKNOWN"
    NATIVE = "NATIVE"
    TOKEN = "TOKEN"


class StablecoinStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    YES = "YES"
    NO = "NO"


@dataclass(frozen=True)
class CryptoAssetIdentity:
    asset_id: str
    base: str
    quote: str
    network: str | None
    kind: CryptoAssetKind
    contract_address: str | None = None
    stablecoin_status: StablecoinStatus = StablecoinStatus.UNKNOWN
    venue_support: tuple[str, ...] = ()
    source: str | None = None

    def __post_init__(self) -> None:
        for name in ("asset_id", "base", "quote"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be explicit")
        if self.base == self.quote:
            raise ValueError("base and quote must differ")
        if not isinstance(self.kind, CryptoAssetKind) or not isinstance(self.stablecoin_status, StablecoinStatus):
            raise TypeError("crypto kind and stablecoin status must be explicit")
        if self.kind in (CryptoAssetKind.NATIVE, CryptoAssetKind.TOKEN) and not self.network:
            raise ValueError("native or token identity requires network")
        if self.kind is CryptoAssetKind.TOKEN and not self.contract_address:
            raise ValueError("token identity requires contract address")
        if self.kind is CryptoAssetKind.NATIVE and self.contract_address is not None:
            raise ValueError("native asset cannot have token contract address")
        if self.venue_support and not self.source:
            raise ValueError("venue support requires source provenance")
        if len(set(self.venue_support)) != len(self.venue_support):
            raise ValueError("duplicate venue support")
        object.__setattr__(self, "venue_support", tuple(self.venue_support))
