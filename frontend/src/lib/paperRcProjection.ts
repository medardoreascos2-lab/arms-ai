import type { JsonObject, JsonValue } from "./dashboardApi";

const object = (value: JsonValue | undefined): JsonObject =>
  value !== null && typeof value === "object" && !Array.isArray(value) ? value : {};

const status = (value: JsonValue | undefined, allowed: string[]): JsonValue | undefined =>
  value === undefined ? undefined : typeof value === "string" && allowed.includes(value) ? value : "UNKNOWN";

/** Display published canonical values only. Missing evidence is never zero. */
export function paperRcRows(snapshot: JsonObject): [string, JsonValue | undefined][] {
  const account = object(snapshot.account_overview);
  const decision = object(snapshot.latest_decision);
  const evidence = object(snapshot.strategy_evidence);
  const config = object(snapshot.configuration);
  return [
    ["MODE", snapshot.mode],
    ["PAPER STATUS", snapshot.mode === "PAPER_RESEARCH" && snapshot.paper_ready === true ? "PAPER READY" : "BLOCKED"],
    ["READINESS REASONS", snapshot.readiness_reasons],
    ["EVIDENCE STATUS", snapshot.evidence_status],
    ["CONFIGURATION", snapshot.config_hash],
    ["EFFECTIVE RISK / SIGNAL POLICY", snapshot.effective_policy],
    ["CANONICAL TIME", snapshot.canonical_time],
    ["TIMEFRAME HISTORY COUNTS", snapshot.timeframe_readiness],
    ["STARTING BALANCE", account.starting_balance],
    ["BALANCE", account.balance], ["EQUITY", account.equity],
    ["PEAK EQUITY", account.peak_equity], ["REALIZED PNL", account.realized_pnl],
    ["DAILY PNL", account.daily_pnl], ["DRAWDOWN", account.drawdown],
    ["RISK BLOCKED", account.trading_blocked], ["RISK REASONS", account.blocking_reasons],
    ["ACCOUNT REPORTED OPEN RISK", account.open_risk],
    ["OPEN EXPOSURE", snapshot.active_simulated_positions],
    ["CURRENT DECISION", decision.action], ["DECISION REASONS", decision.reason],
    ["CONFLUENCE", evidence.confluence], ["CONFLUENCE THRESHOLD", config.boundary],
    ["QUALITY", evidence.quality], ["QUALITY THRESHOLD", config.quality],
    ["TREND", evidence.trend], ["STRUCTURE", evidence.structure],
    ["LIQUIDITY", evidence.liquidity], ["FVG", evidence.fvg], ["REGIME", evidence.regime],
    ["RISK EVALUATION", snapshot.risk_evaluation], ["PLAN", snapshot.plan],
    ["SUBMISSION", snapshot.submission], ["EXECUTION", snapshot.execution_state],
    ["ACTIVE PAPER POSITION", snapshot.active_simulated_positions],
    ["LATEST TRADE", snapshot.latest_canonical_trade],
    ["JOURNAL COMPLETED", snapshot.journal_completed], ["JOURNAL TOTAL", snapshot.journal_total],
  ];
}

/** Current-feed mode is explicit; no balance/score/time inference on the client. */
export function currentPaperRows(snapshot: JsonObject): [string, JsonValue | undefined][] {
  const market = object(snapshot.market_data);
  const session = object(snapshot.session_state);
  return paperRcRows(snapshot).map(([label, value]): [string, JsonValue | undefined] =>
    label === "PAPER STATUS" ? [label, snapshot.mode === "CURRENT_MARKET_PAPER" &&
      snapshot.paper_ready === true ? "PAPER READY" : "BLOCKED"] : [label, value]).concat([
    ["EXECUTION KIND", snapshot.execution_kind],
    ["MARKET SESSION STATE", session.state], ["SESSION REASON", session.reason],
    ["PROVIDER STATE", snapshot.provider_state], ["DATA FRESHNESS", snapshot.data_freshness],
    ["SESSION READINESS", snapshot.session_readiness],
    ["CURRENT SESSION COMPLETE 15M / 1H BARS", snapshot.htf_current_session],
    ["SIM ELIGIBILITY STATUS", snapshot.sim_eligibility_status],
    ["SIM DISCOVERY STATUS", status(snapshot.sim_discovery_status, ["NOT_IMPLEMENTED_AUTHORITY_UNPROVEN"])],
    ["SIM CLASSIFICATION STATUS", status(snapshot.sim_classification_status, ["UNKNOWN"])],
    ["SIM BINDING STATUS", status(snapshot.sim_binding_status, ["NOT_CONFIGURED", "INELIGIBLE", "REVOKED_REVIEW_REQUIRED"])],
    ["SIM RUNTIME REVALIDATION", status(snapshot.sim_runtime_revalidation, ["NOT_PERFORMED", "REVOKED"])],
    ["SIM EXECUTION AUTHORITY", status(snapshot.sim_execution_authority, ["DISABLED"])],
    ["MARKET DATA PROVIDER", market.provider], ["CONNECTION", market.connected],
    ["CURRENT CONTRACT", market.contract], ["INSTRUMENT", market.instrument],
    ["TICK SIZE", market.tick_size], ["POINT VALUE", market.point_value],
    ["TRADING HOURS", market.trading_hours_template], ["SOURCE TIMEZONE", market.source_timezone],
    ["BAR LABEL", market.bar_label], ["SYNTHETIC FIXTURE", market.fixture],
    ["FEED STATUS", market.status], ["FEED VERSION", market.version],
    ["LAST RAW EVENT TIME", market.last_raw_event_time],
    ["LAST CLOSED 1M TIME", market.last_closed_1m_time], ["DATA AGE SECONDS", market.data_age_seconds],
    ["RECOVERY REQUIRED", snapshot.recovery_required], ["FEED CONTRACT", snapshot.feed_contract_sha256],
  ]);
}
