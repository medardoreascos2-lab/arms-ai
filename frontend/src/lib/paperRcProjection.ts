import type { JsonObject, JsonValue } from "./dashboardApi";

const object = (value: JsonValue | undefined): JsonObject =>
  value !== null && typeof value === "object" && !Array.isArray(value) ? value : {};

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
