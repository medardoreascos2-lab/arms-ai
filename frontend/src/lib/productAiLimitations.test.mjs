import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const notice = readFileSync(new URL("../components/product/ProductTrustNotices.tsx", import.meta.url), "utf8");
const medar = readFileSync(new URL("../components/product/MedarConversation.tsx", import.meta.url), "utf8");

test("AI limitation notice exposes every required trust field", () => {
  for (const label of ["Confidence", "Uncertainty", "Model limitation", "Memory provenance", "Human review"]) {
    assert.match(notice, new RegExp(label));
  }
  assert.match(notice, /Recommended before decisions or actions/);
});

test("MEDAR renders limitations for ready and degraded responses", () => {
  assert.match(medar, /<AiLimitationsNotice/);
  assert.match(medar, /confidence=\{response\.confidence\}/);
  assert.match(medar, /degraded \? degradedMessages/);
  assert.match(medar, /humanReviewRecommended/);
});