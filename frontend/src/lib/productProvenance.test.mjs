import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describeProductProvenance } from "./productTrust.ts";


test("provenance reports source, freshness, and current state", () => {
  assert.deepEqual(describeProductProvenance({
    source: "Trusted projection", asOf: "2026-10-04T12:00:00Z", freshnessSeconds: 8,
  }), {
    source: "Trusted projection", asOf: "2026-10-04T12:00:00Z", freshness: "8s", state: "CURRENT",
  });
});

test("missing and pending provenance remain explicit", () => {
  assert.deepEqual(describeProductProvenance({}), {
    source: "UNKNOWN", asOf: "UNKNOWN", freshness: "UNKNOWN", state: "UNKNOWN",
  });
  assert.equal(describeProductProvenance({ integrationPending: true }).state, "INTEGRATION_PENDING");
});

test("shared provenance badge renders every required field", () => {
  const source = readFileSync(new URL("../components/product/ProductPrimitives.tsx", import.meta.url), "utf8");
  for (const label of ["Source:", "Freshness:", "As of:", "State:"]) assert.match(source, new RegExp(label));
});