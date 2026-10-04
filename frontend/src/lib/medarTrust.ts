import type { ProductMedarResponse } from "./medarProduct";

export type TrustSection = Readonly<{ label: string; details: readonly string[] }>;

export function trustSections(response: ProductMedarResponse): readonly TrustSection[] {
  if (response.answer === null) return [];
  const sections: TrustSection[] = [];
  if (response.reasoning_summary?.trim())
    sections.push({ label: "Why", details: [response.reasoning_summary] });
  if (response.why_not.length)
    sections.push({ label: "Why not", details: response.why_not });
  if (response.confidence !== null)
    sections.push({ label: "Confidence", details: [`${Math.round(response.confidence * 100)}%`] });
  if (response.risks.length)
    sections.push({ label: "Risks", details: response.risks });
  const dataUsed = [...response.data_used, ...response.tool_evidence.map((item) => item.summary)];
  if (dataUsed.length)
    sections.push({ label: "Data used", details: dataUsed });
  if (response.sources.length)
    sections.push({ label: "Sources", details: response.sources.map((item) => `${item.title}: ${item.locator}`) });
  if (response.what_would_change_the_view.length)
    sections.push({ label: "What would change the view", details: response.what_would_change_the_view });
  return sections;
}
