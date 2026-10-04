import test from "node:test";
import assert from "node:assert/strict";
import { canSend, completeTurn, pendingTurn, requestMedarResponse } from "./medarConversation.ts";
import { memoryItems } from "./medarMemory.ts";
import { trustSections } from "./medarTrust.ts";

const supported = {
  request_id: "r1", response_id: "answer-1", status: "SUCCESS",
  answer: "Evidence supports caution.", confidence: 0.81,
  reasoning_summary: "Two observations align.",
  sources: [{ source_id: "s1", title: "Report", locator: "report:1" }],
  tool_evidence: [], memory_evidence: [{ evidence_id: "m1", summary: "Preference", digest: "abc" }],
  memory_context: [{ evidence_id: "m1", category: "PREFERENCE", summary: "Concise answers", provenance: "User statement", sensitivity: "STANDARD" }],
  warnings: ["Quote age unknown"], action_proposals: [], follow_up_needed: false,
};

test("send gating and pending turn represent loading without a response", () => {
  assert.equal(canSend(true, false, " question "), true);
  assert.equal(canSend(false, false, "question"), false);
  assert.equal(canSend(true, true, "question"), false);
  assert.equal(canSend(true, false, "   "), false);
  const turn = pendingTurn("r1", "Question");
  assert.equal(turn.response, null);
  assert.equal(completeTurn([turn], "other", { status: "SUCCESS" })[0].response, null);
});

test("send uses only Product proxy and success retains evidence", async () => {
  const calls = [];
  const response = await requestMedarResponse("r1", "c1", "Question", async (url, init) => {
    calls.push([url, init]);
    return { ok: true, json: async () => supported };
  });
  const completed = completeTurn([pendingTurn("r1", "Question")], "r1", response);
  assert.deepEqual(calls.map(([url]) => url), ["/api/product/medar"]);
  assert.equal(calls[0][1].method, "POST");
  assert.deepEqual(JSON.parse(calls[0][1].body), {
    request_id: "r1", conversation_id: "c1", message: "Question",
  });
  assert.equal(completed[0].response.answer, supported.answer);
  assert.equal(response.confidence, 0.81);
  assert.equal(response.sources[0].title, "Report");
  assert.deepEqual(response.warnings, ["Quote age unknown"]);
  assert.equal(memoryItems(response)[0].summary, "Concise answers");
  assert.deepEqual(trustSections(response).map((item) => item.label), ["Why", "Confidence", "Sources"]);
});

for (const status of [
  "ENTITLEMENT_REQUIRED", "SESSION_INVALID", "MEDAR_UNAVAILABLE", "MODEL_UNAVAILABLE", "RATE_LIMITED",
]) {
  test(`send preserves explicit ${status} state without answer or evidence`, async () => {
    const response = await requestMedarResponse("r1", "c1", "Question", async () => ({
      ok: true, json: async () => ({ request_id: "r1", status }),
    }));
    assert.equal(response.status, status);
    assert.equal(response.answer, null);
    assert.deepEqual(trustSections(response), []);
    assert.deepEqual(memoryItems(response), []);
  });
}

test("network failure produces MEDAR unavailable", async () => {
  const response = await requestMedarResponse("r1", "c1", "Question", async () => {
    throw new Error("offline");
  });
  assert.equal(response.status, "MEDAR_UNAVAILABLE");
  assert.equal(response.answer, null);
});
