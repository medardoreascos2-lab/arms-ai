import test from "node:test";
import assert from "node:assert/strict";
import { decodeMedarResponse } from "./medarProduct.ts";
import { memoryItems, memoryCategories } from "./medarMemory.ts";

const base = {
  request_id: "r1", response_id: "response-1", status: "SUCCESS", answer: "View",
  confidence: 0.7, sources: [], tool_evidence: [], warnings: [], action_proposals: [],
  follow_up_needed: false,
};

test("memory categories stay empty when local runtime supplies no memory", () => {
  assert.equal(memoryCategories.length, 4);
  assert.deepEqual(memoryItems(decodeMedarResponse({ ...base, memory_evidence: [] }, "r1")), []);
});

test("only memory context linked to actual evidence is visible", () => {
  const response = decodeMedarResponse({
    ...base, memory_evidence: [{ evidence_id: "m1", summary: "Preference", digest: "abc" }],
    memory_context: [
      { evidence_id: "m1", category: "PREFERENCE", summary: "Concise answers", provenance: "User statement", sensitivity: "STANDARD" },
      { evidence_id: "m2", category: "GOAL", summary: "Unverified", provenance: "Unknown", sensitivity: "UNKNOWN" },
      { evidence_id: "m1", category: "GOAL", summary: "Missing sensitivity", provenance: "User statement" },
    ],
  }, "r1");
  assert.deepEqual(memoryItems(response).map((item) => item.summary), ["Concise answers"]);
});

test("degraded responses cannot present memory context", () => {
  const response = decodeMedarResponse({
    request_id: "r1", status: "MEMORY_UNAVAILABLE",
    memory_context: [{ evidence_id: "m1", category: "GOAL", summary: "Invented", provenance: "x", sensitivity: "STANDARD" }],
  }, "r1");
  assert.deepEqual(memoryItems(response), []);
});
