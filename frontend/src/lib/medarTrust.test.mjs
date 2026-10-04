import test from "node:test";
import assert from "node:assert/strict";
import { decodeMedarResponse } from "./medarProduct.ts";
import { trustSections } from "./medarTrust.ts";

const base = {
  request_id: "r1", response_id: "response-1", status: "SUCCESS",
  answer: "Review the evidence.", confidence: 0.8,
  sources: [], tool_evidence: [], memory_evidence: [], warnings: [],
  action_proposals: [], follow_up_needed: false,
};

test("trust panel only exposes sections backed by response data", () => {
  const minimal = trustSections(decodeMedarResponse(base, "r1"));
  assert.deepEqual(minimal.map((section) => section.label), ["Confidence"]);
  const rich = trustSections(decodeMedarResponse({
    ...base, reasoning_summary: "Price evidence", why_not: ["No volume confirmation"],
    risks: ["Stale quote"], data_used: ["Market snapshot"],
    sources: [{ source_id: "s1", title: "Report", locator: "report:1" }],
    what_would_change_the_view: ["Fresh quote"],
  }, "r1"));
  assert.deepEqual(rich.map((section) => section.label), [
    "Why", "Why not", "Confidence", "Risks", "Data used", "Sources", "What would change the view",
  ]);
  assert.deepEqual(rich.find((section) => section.label === "Sources")?.details, ["Report: report:1"]);
});

test("degraded and malformed evidence cannot populate the trust panel", () => {
  assert.deepEqual(trustSections(decodeMedarResponse({
    request_id: "r1", status: "MEDAR_UNAVAILABLE", risks: ["Invented"],
  }, "r1")), []);
  const response = decodeMedarResponse({ ...base, sources: [{ title: "Malformed" }] }, "r1");
  assert.equal(response.sources.length, 0);
});
