import test from "node:test";
import assert from "node:assert/strict";
import { localMedarEnabled, localMedarEndpoint } from "./medarLocalConfig.ts";
import { decodeMedarResponse, degradedResponse } from "./medarProduct.ts";

test("local MEDAR requires explicit nonproduction enablement", () => {
  assert.equal(localMedarEnabled({ NODE_ENV: "development", PRODUCT_MEDAR_LOCAL_TEST_ENABLED: "true" }), true);
  assert.equal(localMedarEnabled({ NODE_ENV: "production", PRODUCT_MEDAR_LOCAL_TEST_ENABLED: "true" }), false);
  assert.equal(localMedarEnabled({ NODE_ENV: "development" }), false);
});

test("local MEDAR endpoint rejects external and credential URLs", () => {
  assert.equal(localMedarEndpoint("http://127.0.0.1:8001/"), "http://127.0.0.1:8001/product/medar/conversations");
  for (const value of [
    undefined, "https://127.0.0.1:8001/", "http://example.com/",
    "http://user:pass@127.0.0.1:8001/", "http://127.0.0.1:8001/other",
  ]) {
    assert.equal(localMedarEndpoint(value), null);
  }
});

test("response decoder preserves supported evidence and rejects fabricated degraded answers", () => {
  const success = decodeMedarResponse({
    request_id: "r1", response_id: "response-1", status: "SUCCESS",
    answer: "Supported answer", confidence: 0.8, reasoning_summary: "Evidence",
    sources: [{ source_id: "source-1", title: "Report", locator: "report:1" }],
    memory_evidence: [], tool_evidence: [], warnings: [],
    action_proposals: [], follow_up_needed: false,
  }, "r1");
  assert.equal(success.answer, "Supported answer");
  assert.equal(success.sources[0].title, "Report");
  const fabricated = decodeMedarResponse({
    request_id: "r1", status: "MEDAR_UNAVAILABLE", answer: "Invented",
  }, "r1");
  assert.equal(fabricated.status, "MEDAR_UNAVAILABLE");
  assert.equal(fabricated.answer, null);
  assert.equal(degradedResponse("r1", "SESSION_INVALID").answer, null);
});
