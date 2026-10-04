import type { MemoryContextItem, ProductMedarResponse } from "./medarProduct";

export const memoryCategories = [
  ["PREFERENCE", "Remembered preferences"],
  ["GOAL", "Active goals"],
  ["DECISION", "Recent decisions"],
  ["PROJECT", "Relevant project context"],
] as const;

export function memoryItems(response: ProductMedarResponse): readonly MemoryContextItem[] {
  if (response.answer === null) return [];
  const evidenceIds = new Set(response.memory_evidence.map((item) => item.evidence_id));
  return response.memory_context.filter((item) => evidenceIds.has(item.evidence_id));
}
