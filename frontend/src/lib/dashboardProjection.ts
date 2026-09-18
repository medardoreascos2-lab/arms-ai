import type { JsonObject } from "./dashboardApi";

/** Field mapping only. Percentages and financial totals come from the backend. */
export function journalCardData(snapshot: JsonObject | null) {
  if (!snapshot?.trade_journal_summary || !snapshot.analytics ||
      !snapshot.portfolio_summary || !snapshot.performance_overview) return null;
  const journal = snapshot.trade_journal_summary as JsonObject;
  const analytics = snapshot.analytics as JsonObject;
  const portfolio = snapshot.portfolio_summary as JsonObject;
  const performance = snapshot.performance_overview as JsonObject;
  return {
    open_trades: Number(journal.open_trades),
    closed_trades: Number(journal.closed_trades),
    winning_trades: Number(analytics.wins),
    losing_trades: Number(analytics.losses),
    total_realized_pnl: Number(portfolio.total_realized_pnl),
    win_rate: Number(performance.win_rate),
  };
}
