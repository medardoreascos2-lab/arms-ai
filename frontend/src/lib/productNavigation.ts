export type ProductArea =
  | "HOME" | "MEDAR" | "MARKETS" | "TRADING" | "PORTFOLIO"
  | "COACH" | "RESEARCH" | "ALERTS" | "MEMORY" | "SETTINGS";

export type NavigationEntry = Readonly<{
  id: ProductArea;
  label: string;
  description: string;
  availability: "available" | "planned";
  href?: string;
}>;

/** Only routes that exist at this base are linked. Planned areas have no href. */
export const primaryNavigation: readonly NavigationEntry[] = [
  { id: "HOME", label: "Home", description: "Your product starting point", availability: "available", href: "/product" },
  { id: "MEDAR", label: "MEDAR", description: "Personal AI assistance", availability: "available", href: "/product/medar" },
  { id: "MARKETS", label: "Markets", description: "Market analysis", availability: "available", href: "/market-analysis" },
  { id: "TRADING", label: "Trading", description: "Read-only Product trading workspace", availability: "available", href: "/product/trading" },
  { id: "PORTFOLIO", label: "Portfolio", description: "Read-only portfolio health and risk", availability: "available", href: "/product/portfolio" },
  { id: "COACH", label: "Coach", description: "Read-only trading review and improvement", availability: "available", href: "/product/coach" },
  { id: "RESEARCH", label: "Research", description: "Evidence and sources", availability: "planned" },
  { id: "ALERTS", label: "Alerts", description: "Attention and notifications", availability: "planned" },
  { id: "MEMORY", label: "Memory", description: "Review remembered context", availability: "planned" },
  { id: "SETTINGS", label: "Settings", description: "Account and privacy controls", availability: "planned" },
];

/** Roadmap taxonomy only; these are intentionally excluded from product navigation. */
export const futureProductAreas = [
  { id: "BUSINESS", label: "Business" },
  { id: "FAMILY", label: "Family" },
  { id: "LEARNING", label: "Learning" },
  { id: "PERSONAL_HOME", label: "Home" },
  { id: "HEALTH", label: "Health" },
  { id: "LEGACY", label: "Legacy" },
] as const;

export function linkedNavigation(): readonly (NavigationEntry & { href: string })[] {
  return primaryNavigation.filter(
    (entry): entry is NavigationEntry & { href: string } =>
      entry.availability === "available" && typeof entry.href === "string",
  );
}
