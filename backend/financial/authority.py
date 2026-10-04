"""Explicit financial analysis authority ceiling."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FinancialAuthority:
    broker: bool = False
    paper_execution: bool = False
    live_execution: bool = False
    exchange_trading: bool = False
    fund_transfer: bool = False
    crypto_withdrawal: bool = False
    portfolio_mutation: bool = False

    def __post_init__(self) -> None:
        if any((
            self.broker, self.paper_execution, self.live_execution,
            self.exchange_trading, self.fund_transfer, self.crypto_withdrawal,
            self.portfolio_mutation,
        )):
            raise ValueError("financial intelligence is analysis only")


FINANCIAL_AUTHORITY = FinancialAuthority()
