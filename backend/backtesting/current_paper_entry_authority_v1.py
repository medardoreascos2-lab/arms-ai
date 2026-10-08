"""Additional fail-closed entry evidence for certified current CLOSED PAPER bars."""
from collections import deque
from datetime import timedelta
from math import isfinite

from backend.indicators.atr_engine import ATREngine
from backend.market_data.current_candle_authority_v1 import CurrentClosedObservationV1
from backend.services.sim_native_l1_authority_v1 import SimNativeL1AuthorityV1
from backend.services.spread_authority_v2 import SpreadAuthorityV2
from backend.strategies.trading_strategy_v2 import TradingActionV2, TradingDecisionV2


class _PaperQuoteAdmissionV1:
    """Only quote/spread plumbing; carries no SIM_NATIVE account or risk grant."""
    def __init__(self, settings):
        self.settings = settings
        self.spread_authority = SpreadAuthorityV2()
        self.quote_authority = None
        self.runtime_spread_authority = None


def current_paper_l1_reader(*, settings, gate, directory, clock,
                            expected_directory_identity=None, elapsed=None):
    if gate.contract.provider != "NINJATRADER:Provider31" or gate.contract.contract != "NQ DEC26":
        raise ValueError("CURRENT_PAPER_NATIVE_L1_BINDING_REQUIRED")
    digest, config = gate.digest, gate.contract

    def context():
        if gate.digest != digest or gate.contract != config or gate.fault:
            raise ValueError("CURRENT_PAPER_FEED_BINDING_CHANGED")
        return digest

    kwargs = {} if elapsed is None else {"elapsed": elapsed}
    return SimNativeL1AuthorityV1(admission=_PaperQuoteAdmissionV1(settings),
        context=context, clock=clock, directory=directory,
        expected_directory_identity=expected_directory_identity, **kwargs)


class CurrentPaperEntryAuthorityV1:
    """Owns current-only vetoes. It never prepares or submits an order."""

    def __init__(self, *, gate, news, l1, settings, clock):
        if not callable(clock) or news is None or l1 is None:
            raise ValueError("CURRENT_PAPER_ENTRY_AUTHORITIES_REQUIRED")
        expected = dict(maximum_quote_age_seconds=30, maximum_spread_points=5,
            minimum_atr_points=1, maximum_signal_age_seconds=300,
            minimum_stop_points=1, maximum_stop_points=100,
            minimum_reward_risk_ratio=2, minimum_a_plus_probability=.8,
            minimum_a_plus_confluence_score=.8, maximum_open_positions=1)
        if any(getattr(settings, key) != value for key, value in expected.items()):
            raise ValueError("CURRENT_PAPER_ENTRY_POLICY_CHANGED")
        self.gate, self.news, self.l1, self.settings, self.clock = gate, news, l1, settings, clock
        self.rows = deque(maxlen=15)

    def observe(self, row):
        if type(row) is not CurrentClosedObservationV1 or row.calendar_sha256 != self.gate.digest:
            raise ValueError("CURRENT_CLOSED_OBSERVATION_REQUIRED")
        if self.rows and row.available_at <= self.rows[-1].available_at:
            raise ValueError("CURRENT_CLOSED_ORDER_INVALID")
        self.rows.append(row)

    def inspect(self, *, row, decision, open_positions, diagnostic=None):
        reasons = []
        if diagnostic is not None:
            diagnostic.update({name: dict(status="NOT_EVALUATED", reasons=[])
                for name in ("market_session", "max_position", "probability",
                    "confluence", "atr", "signal_age", "news", "l1",
                    "quote_freshness", "spread", "stop", "target", "plan_direction", "rr")})

        def record(name, before, source=None):
            if diagnostic is not None:
                vetoes = list(dict.fromkeys(reasons[before:]))
                diagnostic[name] = dict(status="BLOCKED" if vetoes else "PASS",
                    reasons=vetoes)
                if source is not None:
                    diagnostic[name]["source"] = source

        if row is None or not self.rows or row is not self.rows[-1]:
            reasons.append("CURRENT_CLOSED_OBSERVATION_REQUIRED")
            return reasons
        before = len(reasons)
        market_reasons = self.gate.reasons()
        if market_reasons:
            reasons.append("MARKET_CLOSED_OR_UNAVAILABLE")
        record("market_session", before, list(market_reasons))
        before = len(reasons)
        if type(open_positions) is not int or open_positions >= self.settings.maximum_open_positions:
            reasons.append("MAX_POSITION_REACHED")
        record("max_position", before)
        if type(decision) is not TradingDecisionV2 or decision.action not in (
                TradingActionV2.BUY, TradingActionV2.SELL):
            reasons.append("SIGNAL_INVALID")
            return reasons
        before = len(reasons)
        if decision.confidence < self.settings.minimum_a_plus_probability:
            reasons.append("PROBABILITY_TOO_LOW")
        record("probability", before)
        before = len(reasons)
        confluence = decision.metadata.get("confluence_score")
        if type(confluence) not in (int, float) or not isfinite(confluence) or (
                confluence < self.settings.minimum_a_plus_confluence_score):
            reasons.append("CONFLUENCE_TOO_LOW")
        record("confluence", before)

        # A current 1m bar is the only ATR input. Historical bootstrap never enters rows.
        before = len(reasons)
        if len(self.rows) < 15 or any(
            a.available_at + timedelta(minutes=1) != b.available_at
            or a.trading_date != b.trading_date or a.provider != b.provider or a.contract != b.contract
            for a, b in zip(self.rows, list(self.rows)[1:])):
            reasons.append("ATR_NOT_READY")
        else:
            try:
                atr = ATREngine(period=14).calculate([item.candle() for item in self.rows])
                if not isfinite(atr) or atr <= 0:
                    reasons.append("ATR_INVALID")
                elif atr < self.settings.minimum_atr_points:
                    reasons.append("ATR_TOO_LOW")
            except (ValueError, TypeError, OverflowError):
                reasons.append("ATR_INVALID")
        record("atr", before)

        before = len(reasons)
        try:
            now = self.clock()
            age = (now - row.available_at).total_seconds()
            if not 0 <= age <= self.settings.maximum_signal_age_seconds:
                reasons.append("SIGNAL_TOO_OLD")
        except (ValueError, TypeError, OverflowError):
            reasons.append("SIGNAL_TIME_INVALID")
            now = None
        record("signal_age", before)

        before = len(reasons)
        try:
            news = self.news.inspect(symbol="NQ", timestamp=now)
            if news.get("blocked") or news.get("status") != "CERTIFIED_CLEAR":
                status = news.get("reason") or news.get("status")
                reasons.append({"PACKAGE_MISSING":"NEWS_MISSING", "EXPIRED":"NEWS_EXPIRED",
                    "OUTSIDE_CERTIFIED_COVERAGE":"NEWS_OUTSIDE_COVERAGE",
                    "HIGH_IMPACT_BLOCK":"NEWS_BLACKOUT"}.get(status, "NEWS_UNAVAILABLE"))
        except (ValueError, TypeError, RuntimeError, OSError):
            reasons.append("NEWS_MISSING")
            news = None
        record("news", before, news)

        before = len(reasons)
        quote_freshness_evaluated = spread_evaluated = False
        l1_source = None
        try:
            view, quote = self.l1.inspect()
            l1_source = dict(view=view, quote=quote)
            if quote is None or view.get("status") != "FRESH":
                quote_freshness_evaluated = view.get("status") == "STALE"
                reasons.append({"STALE":"QUOTE_STALE", "REVOKED":"QUOTE_REVOKED"}.get(
                    view.get("status"), "QUOTE_MISSING"))
            elif view.get("provider") != "Provider31":
                reasons.append("QUOTE_WRONG_PROVIDER")
            elif (view.get("contract") != "NQ DEC26" or view.get("instrument") != "NQ"
                    or quote.get("symbol") != "NQ"):
                reasons.append("QUOTE_WRONG_CONTRACT")
            elif (type(quote.get("bid")) not in (int, float) or
                  type(quote.get("ask")) not in (int, float) or
                  not isfinite(quote["bid"]) or not isfinite(quote["ask"]) or
                  quote["bid"] <= 0 or quote["ask"] <= 0):
                reasons.append("QUOTE_INVALID")
            elif quote["ask"] < quote["bid"]:
                reasons.append("QUOTE_CROSSED")
            elif (view.get("quote_age_seconds") is None or
                  not 0 <= view["quote_age_seconds"] <= self.settings.maximum_quote_age_seconds):
                quote_freshness_evaluated = True
                reasons.append("QUOTE_STALE")
            else:
                quote_freshness_evaluated = True
                spread_evaluated = True
                if quote["ask"] - quote["bid"] > self.settings.maximum_spread_points:
                    reasons.append("SPREAD_TOO_WIDE")
        except (ValueError, TypeError, RuntimeError, KeyError, OSError):
            reasons.append("QUOTE_MISSING")
        if diagnostic is not None:
            l1_vetoes = [reason for reason in reasons[before:] if reason != "SPREAD_TOO_WIDE"]
            diagnostic["l1"] = dict(status="BLOCKED" if l1_vetoes else "PASS",
                reasons=l1_vetoes, source=l1_source)
        if quote_freshness_evaluated:
            if diagnostic is not None:
                vetoes = [reason for reason in reasons[before:] if reason == "QUOTE_STALE"]
                diagnostic["quote_freshness"] = dict(
                    status="BLOCKED" if vetoes else "PASS", reasons=vetoes)
        if spread_evaluated:
            if diagnostic is not None:
                vetoes = [reason for reason in reasons[before:] if reason == "SPREAD_TOO_WIDE"]
                diagnostic["spread"] = dict(
                    status="BLOCKED" if vetoes else "PASS", reasons=vetoes)

        before = len(reasons)
        stop_evaluated = target_evaluated = rr_evaluated = False
        try:
            entry = float(row.ohlcv[3])
            stop = float(decision.metadata["stop_loss"])
            target = float(decision.metadata["take_profit"])
            if not isfinite(entry) or entry <= 0:
                reasons.append("ENTRY_INVALID")
            else:
                stop_evaluated = True
                if not isfinite(stop) or stop <= 0:
                    reasons.append("STOP_INVALID")
                else:
                    target_evaluated = True
                    if not isfinite(target) or target <= 0:
                        reasons.append("TARGET_INVALID")
                    else:
                        is_buy = decision.action is TradingActionV2.BUY
                        if (is_buy and not stop < entry < target) or (
                                not is_buy and not target < entry < stop):
                            reasons.append("PLAN_DIRECTION_INVALID")
                        distance = abs(entry - stop)
                        if distance < self.settings.minimum_stop_points:
                            reasons.append("STOP_TOO_SMALL")
                        elif distance > self.settings.maximum_stop_points:
                            reasons.append("STOP_TOO_LARGE")
                        rr_evaluated = True
                        if distance <= 0:
                            reasons.append("RR_INVALID")
                        elif abs(target - entry) / distance < self.settings.minimum_reward_risk_ratio:
                            reasons.append("RR_TOO_LOW")
        except (ValueError, TypeError, KeyError, OverflowError):
            reasons.append("PLAN_INVALID")
        if diagnostic is not None:
            plan_reasons = reasons[before:]
            if rr_evaluated:
                direction_reasons = [reason for reason in plan_reasons
                    if reason == "PLAN_DIRECTION_INVALID"]
                diagnostic["plan_direction"] = dict(
                    status="BLOCKED" if direction_reasons else "PASS",
                    reasons=direction_reasons)
            for name, evaluated, relevant in (
                ("stop", stop_evaluated, ("STOP_INVALID", "STOP_TOO_SMALL", "STOP_TOO_LARGE")),
                ("target", target_evaluated, ("TARGET_INVALID",)),
                ("rr", rr_evaluated, ("RR_INVALID", "RR_TOO_LOW"))):
                if not evaluated:
                    continue
                vetoes = [reason for reason in plan_reasons if reason in relevant]
                diagnostic[name] = dict(status="BLOCKED" if vetoes else "PASS",
                    reasons=vetoes)
        return list(dict.fromkeys(reasons))
