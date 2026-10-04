/** UI formatting only. Invalid or missing probabilities remain unknown. */
export function formatConfidence(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
    return "Unknown";
  }
  return `${value === 1 ? 100 : Math.min(99, Math.round(value * 100))}%`;
}
