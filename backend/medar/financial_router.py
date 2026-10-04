"""Advisory financial routing into current or future ARMS modules."""

from dataclasses import dataclass
from enum import Enum

from backend.phase6.instrument_registry import InstrumentDefinition, get_instrument


class FinancialProduct(str, Enum):
    FUTURES = "FUTURES"
    STOCK = "STOCK"
    ETF = "ETF"
    CRYPTO = "CRYPTO"
    PORTFOLIO = "PORTFOLIO"
    ARBITRAGE = "ARBITRAGE"


@dataclass(frozen=True)
class FinancialRoute:
    product: FinancialProduct
    target_module: str
    symbol: str | None
    instrument: InstrumentDefinition | None
    execution_authority: bool = False

    def __post_init__(self) -> None:
        if self.execution_authority:
            raise ValueError("financial routing cannot authorize broker execution")
        if self.product is FinancialProduct.FUTURES and self.instrument is None:
            raise ValueError("futures routing requires a canonical instrument")


def route_financial_task(product: FinancialProduct, symbol: str | None = None) -> FinancialRoute:
    if not isinstance(product, FinancialProduct):
        raise TypeError("product must be FinancialProduct")
    normalized = symbol.strip().upper() if isinstance(symbol, str) and symbol.strip() else None
    if product is FinancialProduct.FUTURES:
        if normalized is None:
            raise ValueError("futures tasks require an instrument symbol")
        instrument = get_instrument(normalized)
        return FinancialRoute(product, "backend.phase6", normalized, instrument)
    targets = {
        FinancialProduct.STOCK: "future.stocks",
        FinancialProduct.ETF: "future.etfs",
        FinancialProduct.CRYPTO: "future.crypto",
        FinancialProduct.PORTFOLIO: "future.portfolio",
        FinancialProduct.ARBITRAGE: "future.crypto_arbitrage",
    }
    return FinancialRoute(product, targets[product], normalized, None)
