export type DailyInsight = Readonly<{
  id: "BRIEF" | "MARKET" | "PORTFOLIO" | "PRIORITIES";
  title: string;
  purpose: string;
  content: Readonly<{ state: "unavailable"; reason: string }>;
}>;

const unavailable = { state: "unavailable", reason: "No verified daily source is connected." } as const;

/** Read-only initial projection; never substitutes demonstration data for a daily brief. */
export const initialDailyInsights: readonly DailyInsight[] = [
  { id: "BRIEF", title: "Daily brief", purpose: "Today's verified overview", content: unavailable },
  { id: "MARKET", title: "Market context", purpose: "Current market conditions and freshness", content: unavailable },
  { id: "PORTFOLIO", title: "Portfolio context", purpose: "Account-specific risk and exposure", content: unavailable },
  { id: "PRIORITIES", title: "Review priorities", purpose: "Items needing your attention", content: unavailable },
];
