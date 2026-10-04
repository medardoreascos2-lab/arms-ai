import test from "node:test";
import assert from "node:assert/strict";
import { formatConfidence } from "./productPresentation.ts";

test("confidence formatting preserves unknown and invalid inputs", () => {
  for (const value of [null, undefined, Number.NaN, Infinity, -0.1, 1.1]) {
    assert.equal(formatConfidence(value), "Unknown");
  }
});

test("valid normalized confidence is displayed as a percentage", () => {
  assert.equal(formatConfidence(0), "0%");
  assert.equal(formatConfidence(0.805), "81%");
  assert.equal(formatConfidence(0.999), "99%");
  assert.equal(formatConfidence(1), "100%");
});
