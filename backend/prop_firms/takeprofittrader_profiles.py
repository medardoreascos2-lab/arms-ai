"""Source-backed TakeProfitTrader profiles reviewed 2026-10-03.

The profiles are read-only policy configuration. They never activate accounts,
route orders, or request withdrawals. Every current stage remains INCOMPLETE
until calendar/session/counter-position compliance has a dedicated, auditable
snapshot contract, so no profile can yield a complete trading authorization.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from .models_v1 import (
    AccountStage, ConsistencyMode, ConsistencyPolicy, ContractLimitEnforcement,
    ContractLimitPolicy, DailyLossEnforcement, DailyLossPolicy, DrawdownModel,
    DrawdownPolicy, ExposureWeight, PayoutPolicy, PropFirmProfile,
    ReferenceUpdateMode, SourceEvidence, SourceReview, SourceStatus,
    TradingDayPolicy, ValueBasis, WeightedExposurePolicy,
)

REVIEWED_AT = datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc)
EFFECTIVE_FROM = datetime(2026, 9, 22, 0, 0, tzinfo=timezone.utc)
VERSION = "2026-10-03"

PROFIT_TARGET = "https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15169070804125-Rule-1-Hit-Your-Profit-Target"
POSITION_SIZE = "https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15169066911133-Rule-2-Do-Not-Exceed-Maximum-Position-Size"
TEST_DRAWDOWN = "https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15170265979165-Rule-3-Do-Not-Hit-End-Of-Day-EOD-Maximum-Trailing-Drawdown"
TRADING_HOURS = "https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15170347090461-Rule-4-Trade-Approved-Products-During-Approved-Hours"
CONSISTENCY = "https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15170316538013-Rule-5-Be-Consistent"
PRODUCTS = "https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15172629238301-Approved-Instruments-Permitted-Products-List"
UNIVERSAL = "https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/34431153546397-TakeProfitTrader-Universal-Trading-Policies-UTP"
PRO_RULES = "https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15171769361053-PRO-Account-Rules"
PRO_PAYOUT = "https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15172219527581-PRO-Account-Profit-Split-Withdrawal-Rules"
WITHDRAWAL = "https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15172253980061-How-to-Withdraw-from-PRO-Account-to-the-Wallet"
PRO_PLUS_RULES = "https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15172006753821-PRO-Account-Rules"
PRO_PLUS = "https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15171929948829-Advantages-of-PRO"
CURRENT_PROGRAM = "https://takeprofittrader.com/control-center"

SIZES = (D("25000"), D("50000"), D("75000"), D("100000"), D("150000"))
PROFIT_TARGETS = {
    D("25000"): D("1500"), D("50000"): D("3000"),
    D("75000"): D("4500"), D("100000"): D("6000"),
    D("150000"): D("9000"),
}
MAXIMUM_DRAWDOWNS = {
    D("25000"): D("1500"), D("50000"): D("2000"),
    D("75000"): D("2500"), D("100000"): D("3000"),
    D("150000"): D("4500"),
}
MAXIMUM_UNITS = {
    D("25000"): D("3"), D("50000"): D("6"), D("75000"): D("9"),
    D("100000"): D("12"), D("150000"): D("15"),
}

MICRO_PRODUCTS = ("MBT", "M2K", "M6E", "MET", "MCL", "MES", "MGC", "MNQ", "M6A", "MYM")
STANDARD_PRODUCTS = (
    "6A", "6B", "6C", "6E", "6J", "6N", "6S", "CL", "ES", "GC", "HG",
    "LE", "NG", "NQ", "RTY", "SI", "UB", "YM", "ZF", "ZL", "ZS", "ZN",
    "ZT", "ZW",
)


def _source(url: str, title: str, heading: str) -> SourceEvidence:
    return SourceEvidence(url, title, REVIEWED_AT, effective_from=EFFECTIVE_FROM,
                          rule_heading=heading)


TEST_SOURCES = (
    _source(PROFIT_TARGET, "Rule 1: Hit Your Profit Target", "Profit targets by account size"),
    _source(POSITION_SIZE, "Rule 2: Maximum Position Size", "Maximum position by account size"),
    _source(TEST_DRAWDOWN, "Rule 3: EOD Maximum Trailing Drawdown", "EOD trailing drawdown"),
    _source(TRADING_HOURS, "Rule 4: Products and Hours", "Approved products and daily window"),
    _source(CONSISTENCY, "Rule 5: Be Consistent", "Three days and below 50 percent"),
    _source(PRODUCTS, "Approved Instruments", "Official permitted product list"),
    _source(UNIVERSAL, "Universal Trading Policies", "All account types"),
    _source(CURRENT_PROGRAM, "Current Program Comparison", "Test, PRO and PRO+"),
)
PRO_SOURCES = TEST_SOURCES + (
    _source(PRO_RULES, "PRO Account Rules", "Intraday drawdown, weekly activity and news"),
    _source(PRO_PAYOUT, "PRO Profit Split and Withdrawal Rules", "Buffer and 80/20 split"),
    _source(WITHDRAWAL, "Withdraw from PRO to Wallet", "Flat account requirement"),
)
PRO_PLUS_SOURCES = TEST_SOURCES + (
    _source(PRO_PLUS_RULES, "PRO+ Account Rules", "EOD drawdown, weekly activity and news"),
    _source(PRO_PLUS, "Advantages of PRO+", "Live stage and 90/10 split"),
)


def _review(sources: tuple[SourceEvidence, ...]) -> SourceReview:
    return SourceReview(SourceStatus.INCOMPLETE, REVIEWED_AT, sources,
                        REVIEWED_AT + timedelta(days=30))


def _size(value: D) -> D:
    if value not in SIZES:
        raise ValueError("unsupported TakeProfitTrader account size")
    return value


def _exposure(size: D) -> ContractLimitPolicy:
    weights = tuple(ExposureWeight(symbol, D("1")) for symbol in STANDARD_PRODUCTS)
    weights += tuple(ExposureWeight(symbol, D("0.1")) for symbol in MICRO_PRODUCTS)
    return ContractLimitPolicy(
        None, weighted_exposure=WeightedExposurePolicy(MAXIMUM_UNITS[size], weights),
        breach_enforcement=ContractLimitEnforcement.ACCOUNT_FAIL,
    )


def _drawdown(size: D, stage: AccountStage) -> DrawdownPolicy:
    intraday = stage == AccountStage.PRO
    return DrawdownPolicy(
        DrawdownModel.TRAILING_INTRADAY if intraday else DrawdownModel.TRAILING_END_OF_DAY,
        MAXIMUM_DRAWDOWNS[size], ValueBasis.MIN_BALANCE_OR_EQUITY, size,
        reference_update_mode=(ReferenceUpdateMode.INTRADAY_EQUITY
                               if intraday else ReferenceUpdateMode.END_OF_DAY_BALANCE),
    )


def test_profile(account_size: D) -> PropFirmProfile:
    size = _size(account_size)
    return PropFirmProfile(
        firm_id="takeprofittrader", program_id="test", stage=AccountStage.EVALUATION,
        version=VERSION, effective_from=EFFECTIVE_FROM,
        account_size=size, starting_balance=size, drawdown=_drawdown(size, AccountStage.EVALUATION),
        daily_loss=DailyLossPolicy(None, DailyLossEnforcement.NOT_APPLICABLE),
        contract_limit=_exposure(size),
        consistency=ConsistencyPolicy(
            True, D("0.50"), D("0.01"), ConsistencyMode.TOTAL_PROFIT,
            maximum_is_inclusive=False,
        ),
        payout=PayoutPolicy(False), trading_days=TradingDayPolicy(3),
        profit_target=PROFIT_TARGETS[size], source_reference=PROFIT_TARGET,
        source_review=_review(TEST_SOURCES),
    )


def pro_profile(account_size: D) -> PropFirmProfile:
    size = _size(account_size)
    return PropFirmProfile(
        firm_id="takeprofittrader", program_id="pro", stage=AccountStage.PRO,
        version=VERSION, effective_from=EFFECTIVE_FROM,
        account_size=size, starting_balance=size, drawdown=_drawdown(size, AccountStage.PRO),
        daily_loss=DailyLossPolicy(None, DailyLossEnforcement.NOT_APPLICABLE),
        contract_limit=_exposure(size), consistency=ConsistencyPolicy(False),
        payout=PayoutPolicy(
            True, minimum_balance=size + MAXIMUM_DRAWDOWNS[size],
            trader_profit_fraction=D("0.80"), require_flat=True,
        ),
        source_reference=PRO_RULES, source_review=_review(PRO_SOURCES),
    )


def pro_plus_profile(account_size: D) -> PropFirmProfile:
    """Return a read-only LIVE-stage policy profile; it grants no LIVE authority."""
    size = _size(account_size)
    return PropFirmProfile(
        firm_id="takeprofittrader", program_id="pro_plus", stage=AccountStage.LIVE,
        version=VERSION, effective_from=EFFECTIVE_FROM,
        account_size=size, starting_balance=size, drawdown=_drawdown(size, AccountStage.LIVE),
        daily_loss=DailyLossPolicy(None, DailyLossEnforcement.NOT_APPLICABLE),
        contract_limit=_exposure(size), consistency=ConsistencyPolicy(False),
        payout=PayoutPolicy(
            True, trader_profit_fraction=D("0.90"), require_flat=True,
        ),
        source_reference=PRO_PLUS_RULES, source_review=_review(PRO_PLUS_SOURCES),
    )


@dataclass(frozen=True)
class TakeProfitTraderStageSupport:
    program_id: str
    stage: AccountStage
    next_stage: AccountStage | None
    transition_discretionary: bool
    source_status: SourceStatus
    reason: str
    source_url: str


TAKEPROFITTRADER_STAGE_SUPPORT = (
    TakeProfitTraderStageSupport(
        "test", AccountStage.EVALUATION, AccountStage.PRO, False,
        SourceStatus.INCOMPLETE,
        "TRADING_HOURS_AND_COUNTER_POSITION_STATE_UNMODELED", TRADING_HOURS,
    ),
    TakeProfitTraderStageSupport(
        "pro", AccountStage.PRO, AccountStage.LIVE, True,
        SourceStatus.INCOMPLETE,
        "WEEKLY_ACTIVITY_NEWS_AND_LIMIT_STATE_UNMODELED", PRO_RULES,
    ),
    TakeProfitTraderStageSupport(
        "pro_plus", AccountStage.LIVE, None, False,
        SourceStatus.INCOMPLETE,
        "LIVE_POLICY_ONLY_WEEKLY_ACTIVITY_NEWS_AND_LIMIT_STATE_UNMODELED", PRO_PLUS_RULES,
    ),
    TakeProfitTraderStageSupport(
        "pro_closure_withdrawal", AccountStage.PRO, None, False,
        SourceStatus.INCOMPLETE,
        "ACCOUNT_CLOSURE_PAYOUT_ROUTE_UNSUPPORTED", PRO_PAYOUT,
    ),
)


def standard_takeprofittrader_profiles() -> tuple[PropFirmProfile, ...]:
    return tuple(factory(size) for size in SIZES
                 for factory in (test_profile, pro_profile, pro_plus_profile))
