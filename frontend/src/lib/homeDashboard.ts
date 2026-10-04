export type HomeSectionId =
  | "DAILY_INTELLIGENCE" | "MARKET_STATUS" | "PORTFOLIO_HEALTH"
  | "TRADING_COACH" | "ALERTS" | "TASKS"
  | "RECENT_MEDAR_ACTIVITY" | "MEMORY_HIGHLIGHTS"
  | "VOICE" | "CAMERA" | "AVATAR" | "PRESENCE" | "NOTIFICATIONS"
  | "QUICK_ACTIONS";

export type HomeSectionContent =
  | Readonly<{ state: "unavailable"; reason: string }>
  | Readonly<{ state: "ready"; summary: string; source: string; asOf: string }>
  | Readonly<{ state: "navigation"; actions: readonly Readonly<{ label: string; href: string }>[] }>;

export type HomeSection = Readonly<{
  id: HomeSectionId;
  title: string;
  purpose: string;
  content: HomeSectionContent;
}>;

const unavailable: HomeSectionContent = {
  state: "unavailable",
  reason: "No verified source is connected to this Home section yet.",
};

/** Honest initial state. A section becomes ready only with a source and observation time. */
export const initialHomeSections: readonly HomeSection[] = [
  { id: "DAILY_INTELLIGENCE", title: "Daily Intelligence", purpose: "What matters today", content: unavailable },
  { id: "MARKET_STATUS", title: "Market Status", purpose: "Current market context and freshness", content: unavailable },
  { id: "PORTFOLIO_HEALTH", title: "Portfolio Health", purpose: "Allocation and risk overview", content: unavailable },
  { id: "TRADING_COACH", title: "Trading Coach", purpose: "Review and improvement", content: unavailable },
  { id: "ALERTS", title: "Alerts", purpose: "Items needing attention", content: unavailable },
  { id: "TASKS", title: "Tasks", purpose: "What to review next", content: unavailable },
  { id: "RECENT_MEDAR_ACTIVITY", title: "Recent MEDAR activity", purpose: "Recent assistant work", content: unavailable },
  { id: "MEMORY_HIGHLIGHTS", title: "Memory highlights", purpose: "Relevant remembered context", content: unavailable },
  { id: "VOICE", title: "Voice", purpose: "Push to talk and spoken responses", content: {
    state: "unavailable",
    reason: "Production speech recognition and speech output providers are not connected.",
  } },
  { id: "CAMERA", title: "Camera", purpose: "Explicit visual context sessions", content: {
    state: "unavailable",
    reason: "Camera access is off by default and no production vision provider is connected.",
  } },
  { id: "AVATAR", title: "Avatar", purpose: "Visual MEDAR presence", content: {
    state: "unavailable",
    reason: "Only the local placeholder avatar is available; production animation is not connected.",
  } },
  { id: "PRESENCE", title: "Presence", purpose: "Coarse session and device presence", content: {
    state: "unavailable",
    reason: "Distributed presence is modeled locally without a production device provider.",
  } },
  { id: "NOTIFICATIONS", title: "Notifications", purpose: "Consent-aware multimodal updates", content: {
    state: "unavailable",
    reason: "External notification delivery is not connected.",
  } },
  { id: "QUICK_ACTIONS", title: "Quick actions", purpose: "Open existing market analysis", content: {
    state: "navigation",
    actions: [
      { label: "Onboarding", href: "/product/onboarding" },
      { label: "Daily Intelligence", href: "/product/daily-intelligence" },
      { label: "Shadow MEDAR", href: "/product/shadow-medar" },
      { label: "Avatar preview", href: "/product/avatar" },
      { label: "Multimodal settings", href: "/product/settings/multimodal" },
      { label: "Market analysis", href: "/market-analysis" },
    ],
  } },
];