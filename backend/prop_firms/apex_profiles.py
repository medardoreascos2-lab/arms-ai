"""Source-backed Apex Trader Funding profiles reviewed 2026-10-03.

Profiles are pure policy data. They do not authorize trading, create accounts,
submit orders, or issue payouts. Current products introduced on 2026-03-01 are
kept distinct from Legacy products. The 50K performance profile deliberately
fails closed because two official pages disagree at the 5,999/6,000 scaling
boundary.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from .models_v1 import (
    AccountStage, ConsistencyApplication, ConsistencyMode, ConsistencyPolicy,
    ContractLimitEnforcement, ContractLimitPolicy, DailyLossEnforcement,
    DailyLossPolicy, DrawdownModel, DrawdownPolicy, ExposureWeight,
    InactivityPolicy, PayoutFractionBasis, PayoutPolicy, PayoutTier,
    PropFirmProfile, ReferenceUpdateMode, ResetBoundary, ScalingPolicy,
    ScalingTier, SourceEvidence, SourceReview, SourceStatus, TradingDayPolicy,
    ValueBasis, WeightedExposurePolicy,
)

REVIEWED_AT = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
EFFECTIVE_FROM = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
VERSION = "2026-10-03"

EOD_EVALUATION = "https://apextraderfunding.com/help-center/eod-trailing-drawdown-accounts/eod-evaluations/"
INTRADAY_EVALUATION = "https://apextraderfunding.com/help-center/evaluation-accounts-ea/intraday-trailing-drawdown-evaluations/"
POSITION_SIZING = "https://apextraderfunding.com/help-center/additional-helpful-items/position-sizing-evaluation/"
EOD_DRAWDOWN = "https://apextraderfunding.com/help-center/eod-trailing-drawdown-accounts/eod-drawdown-explained/"
INTRADAY_DRAWDOWN = "https://apextraderfunding.com/help-center/intraday-trailing-drawdown-accounts/intraday-trailing-drawdown-explained/"
EOD_PA = "https://apextraderfunding.com/help-center/eod-trailing-drawdown-accounts/eod-performance-accounts-pa/"
INTRADAY_PA = "https://apextraderfunding.com/help-center/intraday-trailing-drawdown-accounts/intraday-trailing-drawdown-performance-accounts-pa/"
SCALING = "https://apextraderfunding.com/help-center/additional-helpful-items/scaling-levels-pa-explained/"
DAILY_LOSS = "https://apextraderfunding.com/help-center/additional-helpful-items/daily-loss-limit-explained/"
INACTIVITY = "https://apextraderfunding.com/help-center/billing/inactivity-policy-on-performance-accounts-pa"
EOD_PAYOUT = "https://apextraderfunding.com/help-center/eod-trailing-drawdown-accounts/eod-payouts/"
INTRADAY_PAYOUT = "https://apextraderfunding.com/help-center/uncategorized/intraday-trailing-drawdown-payouts/"
LEGACY = "https://apextraderfunding.com/help-center/legacy-products/legacy-products-overview/"

SIZES = (D("25000"), D("50000"), D("100000"), D("150000"))
PROFIT_TARGETS = {
    D("25000"): D("1500"), D("50000"): D("3000"),
    D("100000"): D("6000"), D("150000"): D("9000"),
}
MAXIMUM_DRAWDOWNS = {
    D("25000"): D("1000"), D("50000"): D("2000"),
    D("100000"): D("3000"), D("150000"): D("4000"),
}
EVALUATION_DAILY_LOSSES = {
    D("25000"): D("500"), D("50000"): D("1000"),
    D("100000"): D("1500"), D("150000"): D("2000"),
}
EVALUATION_MAXIMUM_UNITS = {
    D("25000"): D("4"), D("50000"): D("6"),
    D("100000"): D("8"), D("150000"): D("12"),
}

SCALING_TIERS = {
    D("25000"): (("L1", "0", "1", "500"), ("L2", "1000", "2", "500"),
                   ("L3", "2000", "2", "1250")),
    D("50000"): (("L1", "0", "2", "1000"), ("L2", "1500", "3", "1000"),
                   ("L3", "3000", "4", "2000"), ("L4", "6000", "4", "3000")),
    D("100000"): (("L1", "0", "3", "1750"), ("L2", "2000", "4", "1750"),
                    ("L3", "3000", "5", "1750"), ("L4", "5000", "6", "2500"),
                    ("L5", "10000", "6", "3500")),
    D("150000"): (("L1", "0", "4", "2500"), ("L2", "2000", "5", "2500"),
                    ("L3", "3000", "7", "2500"), ("L4", "5000", "10", "3000"),
                    ("L5", "10000", "10", "4000")),
}

EOD_QUALIFYING_DAY = {
    D("25000"): D("100"), D("50000"): D("250"),
    D("100000"): D("300"), D("150000"): D("350"),
}
INTRADAY_QUALIFYING_DAY = {
    D("25000"): D("100"), D("50000"): D("200"),
    D("100000"): D("250"), D("150000"): D("300"),
}
EOD_PAYOUT_CAPS = {
    D("25000"): ("1000", "1000", "1000", "1000", "1000", "1000"),
    D("50000"): ("1500", "1500", "2000", "2500", "2500", "3000"),
    D("100000"): ("2000", "2500", "2500", "3000", "4000", "4000"),
    D("150000"): ("2500", "3000", "3000", "3000", "4000", "5000"),
}
INTRADAY_PAYOUT_CAPS = {
    D("25000"): ("1000", "1000", "1000", "1000", "1000", "1000"),
    D("50000"): ("1500", "2000", "2500", "2500", "3000", "3000"),
    D("100000"): ("2000", "2500", "3000", "3000", "4000", "4000"),
    D("150000"): ("2500", "3000", "3000", "4000", "4000", "5000"),
}


def _source(url: str, title: str, heading: str) -> SourceEvidence:
    return SourceEvidence(url, title, REVIEWED_AT, effective_from=EFFECTIVE_FROM,
                          rule_heading=heading)


COMMON_SOURCES = (
    _source(POSITION_SIZING, "Position Sizing - Evaluation", "Maximum contracts and micro ratio"),
)
EOD_EVALUATION_SOURCES = COMMON_SOURCES + (
    _source(EOD_EVALUATION, "EOD Evaluations", "Account parameters and daily loss limit"),
    _source(EOD_DRAWDOWN, "EOD Drawdown Explained", "Evaluation drawdown mechanics"),
)
INTRADAY_EVALUATION_SOURCES = COMMON_SOURCES + (
    _source(INTRADAY_EVALUATION, "Intraday Trailing Drawdown Evaluations", "Account parameters"),
    _source(INTRADAY_DRAWDOWN, "Intraday Trailing Drawdown Explained", "Evaluation mechanics"),
)
PERFORMANCE_COMMON_SOURCES = (
    _source(SCALING, "Scaling Levels - PA Explained", "Scaling tables"),
    _source(DAILY_LOSS, "Daily Loss Limit Explained", "PA limits by scaling level"),
    _source(INACTIVITY, "Inactivity Policy on Performance Accounts", "Rolling 30-day requirement"),
)


def _review(status: SourceStatus, sources: tuple[SourceEvidence, ...]) -> SourceReview:
    return SourceReview(status, REVIEWED_AT, sources, REVIEWED_AT + timedelta(days=30))


def _size(value: D) -> D:
    if value not in SIZES:
        raise ValueError("unsupported Apex account size")
    return value


def _exposure(maximum_units: D) -> ContractLimitPolicy:
    minis = ("ES", "NQ", "RTY", "YM", "GC", "CL")
    micros = ("MES", "MNQ", "M2K", "MYM", "MGC", "MCL")
    weights = tuple(ExposureWeight(symbol, D("1")) for symbol in minis)
    weights += tuple(ExposureWeight(symbol, D("0.1")) for symbol in micros)
    return ContractLimitPolicy(
        None, weighted_exposure=WeightedExposurePolicy(maximum_units, weights),
        breach_enforcement=ContractLimitEnforcement.TRADING_BLOCK,
    )


def _drawdown(size: D, kind: str, stage: AccountStage, platform: str | None = None) -> DrawdownPolicy:
    if kind not in ("eod", "intraday"):
        raise ValueError("drawdown kind must be eod or intraday")
    if stage == AccountStage.EVALUATION:
        if platform not in ("rithmic", "wealthcharts", "tradovate"):
            raise ValueError("evaluation platform must be rithmic, wealthcharts, or tradovate")
        cap = None if platform == "tradovate" else size + PROFIT_TARGETS[size]
    else:
        cap = size + D("100")
    return DrawdownPolicy(
        DrawdownModel.TRAILING_END_OF_DAY if kind == "eod" else DrawdownModel.TRAILING_INTRADAY,
        MAXIMUM_DRAWDOWNS[size], ValueBasis.MIN_BALANCE_OR_EQUITY, cap,
        reference_update_mode=(ReferenceUpdateMode.END_OF_DAY_BALANCE
                               if kind == "eod" else ReferenceUpdateMode.INTRADAY_EQUITY),
    )


def evaluation_profile(account_size: D, *, drawdown_kind: str, platform: str) -> PropFirmProfile:
    size = _size(account_size)
    if drawdown_kind == "eod":
        daily = DailyLossPolicy(EVALUATION_DAILY_LOSSES[size],
                                DailyLossEnforcement.SESSION_BLOCK,
                                ResetBoundary.SESSION_END)
        sources = EOD_EVALUATION_SOURCES
        reference = EOD_EVALUATION
    elif drawdown_kind == "intraday":
        daily = DailyLossPolicy(None, DailyLossEnforcement.NOT_APPLICABLE)
        sources = INTRADAY_EVALUATION_SOURCES
        reference = INTRADAY_EVALUATION
    else:
        raise ValueError("drawdown_kind must be eod or intraday")
    platform = platform.lower()
    return PropFirmProfile(
        firm_id="apex", program_id=f"{drawdown_kind}_evaluation_{platform}",
        stage=AccountStage.EVALUATION, version=VERSION, effective_from=EFFECTIVE_FROM,
        account_size=size, starting_balance=size,
        drawdown=_drawdown(size, drawdown_kind, AccountStage.EVALUATION, platform),
        daily_loss=daily, contract_limit=_exposure(EVALUATION_MAXIMUM_UNITS[size]),
        consistency=ConsistencyPolicy(False), payout=PayoutPolicy(False),
        trading_days=TradingDayPolicy(0), profit_target=PROFIT_TARGETS[size],
        maximum_access_days=30, source_reference=reference,
        source_review=_review(SourceStatus.CURRENT_VERIFIED, sources),
    )


def eod_evaluation_profile(account_size: D, *, platform: str = "rithmic") -> PropFirmProfile:
    return evaluation_profile(account_size, drawdown_kind="eod", platform=platform)


def intraday_evaluation_profile(account_size: D, *, platform: str = "rithmic") -> PropFirmProfile:
    return evaluation_profile(account_size, drawdown_kind="intraday", platform=platform)


def _scaling(size: D) -> ScalingPolicy:
    return ScalingPolicy(tuple(
        ScalingTier(name, D(minimum), D(maximum), D(daily))
        for name, minimum, maximum, daily in SCALING_TIERS[size]
    ))


def _payout(size: D, kind: str) -> PayoutPolicy:
    qualifying = EOD_QUALIFYING_DAY if kind == "eod" else INTRADAY_QUALIFYING_DAY
    caps = EOD_PAYOUT_CAPS if kind == "eod" else INTRADAY_PAYOUT_CAPS
    return PayoutPolicy(
        True, minimum_balance=size + MAXIMUM_DRAWDOWNS[size] + D("100"),
        minimum_qualifying_days_per_cycle=5,
        minimum_qualifying_day_profit=qualifying[size],
        minimum_payout_amount=D("500"), maximum_payout_count=6,
        maximum_fraction_basis=PayoutFractionBasis.AVAILABLE_PROFIT,
        tiers=tuple(PayoutTier(index, maximum_amount=D(cap))
                    for index, cap in enumerate(caps[size])),
        consistency_per_cycle=True,
    )


def performance_profile(account_size: D, *, drawdown_kind: str) -> PropFirmProfile:
    size = _size(account_size)
    if drawdown_kind == "eod":
        program_source = _source(EOD_PA, "EOD Performance Accounts", "PA parameters")
        payout_source = _source(EOD_PAYOUT, "EOD Payouts", "Payout requirements")
        reference = EOD_PA
    elif drawdown_kind == "intraday":
        program_source = _source(INTRADAY_PA, "Intraday Performance Accounts", "PA parameters")
        payout_source = _source(INTRADAY_PAYOUT, "Intraday Payouts", "Payout requirements")
        reference = INTRADAY_PA
    else:
        raise ValueError("drawdown_kind must be eod or intraday")
    scaling = _scaling(size)
    status = SourceStatus.SOURCE_CONFLICT if size == D("50000") else SourceStatus.CURRENT_VERIFIED
    sources = PERFORMANCE_COMMON_SOURCES + (program_source, payout_source)
    return PropFirmProfile(
        firm_id="apex", program_id=f"{drawdown_kind}_performance",
        stage=AccountStage.PERFORMANCE, version=VERSION, effective_from=EFFECTIVE_FROM,
        account_size=size, starting_balance=size,
        drawdown=_drawdown(size, drawdown_kind, AccountStage.PERFORMANCE),
        daily_loss=DailyLossPolicy(scaling.tiers[0].daily_loss_limit,
                                   DailyLossEnforcement.SESSION_BLOCK,
                                   ResetBoundary.SESSION_END),
        contract_limit=_exposure(scaling.tiers[-1].maximum_units),
        consistency=ConsistencyPolicy(
            True, D("0.50"), D("0.01"), ConsistencyMode.TOTAL_PROFIT,
            ConsistencyApplication.PAYOUT_CYCLE, maximum_is_inclusive=False,
        ),
        payout=_payout(size, drawdown_kind), scaling=scaling,
        inactivity=InactivityPolicy(30, 2, D("50")), source_reference=reference,
        source_review=_review(status, sources),
    )


def eod_performance_profile(account_size: D) -> PropFirmProfile:
    return performance_profile(account_size, drawdown_kind="eod")


def intraday_performance_profile(account_size: D) -> PropFirmProfile:
    return performance_profile(account_size, drawdown_kind="intraday")


@dataclass(frozen=True)
class ApexProgramSupport:
    program_id: str
    stage: AccountStage
    source_status: SourceStatus
    implemented: bool
    reason: str | None
    source_url: str


APEX_PROGRAM_SUPPORT = (
    ApexProgramSupport("eod_evaluation", AccountStage.EVALUATION,
                       SourceStatus.CURRENT_VERIFIED, True, None, EOD_EVALUATION),
    ApexProgramSupport("intraday_evaluation", AccountStage.EVALUATION,
                       SourceStatus.CURRENT_VERIFIED, True, None, INTRADAY_EVALUATION),
    ApexProgramSupport("eod_performance", AccountStage.PERFORMANCE,
                       SourceStatus.SOURCE_CONFLICT, True,
                       "50K_SCALING_BOUNDARY_SOURCE_CONFLICT", EOD_PA),
    ApexProgramSupport("intraday_performance", AccountStage.PERFORMANCE,
                       SourceStatus.SOURCE_CONFLICT, True,
                       "50K_SCALING_BOUNDARY_SOURCE_CONFLICT", INTRADAY_PA),
    ApexProgramSupport("legacy_products", AccountStage.UNKNOWN,
                       SourceStatus.INCOMPLETE, False,
                       "LEGACY_PRODUCTS_REQUIRE_SEPARATE_VERSIONED_PROFILES", LEGACY),
)


def standard_apex_profiles() -> tuple[PropFirmProfile, ...]:
    profiles = []
    for size in SIZES:
        for platform in ("rithmic", "wealthcharts", "tradovate"):
            profiles.extend((eod_evaluation_profile(size, platform=platform),
                             intraday_evaluation_profile(size, platform=platform)))
        profiles.extend((eod_performance_profile(size), intraday_performance_profile(size)))
    return tuple(profiles)
