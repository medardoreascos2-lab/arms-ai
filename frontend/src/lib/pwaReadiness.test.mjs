import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import manifest from "../app/manifest.ts";
import { productPwaReadiness } from "./pwaReadiness.ts";


test("manifest exposes a bounded Product installability seam", () => {
  const value = manifest();
  assert.equal(value.name, "ARMS AI + MEDAR");
  assert.equal(value.start_url, "/product");
  assert.equal(value.display, "standalone");
  assert.ok(Array.isArray(value.icons) && value.icons.length > 0);
});

test("offline behavior is a truthful shell and does not claim cached Product data", () => {
  const source = readFileSync(new URL("../app/offline/page.tsx", import.meta.url), "utf8");
  assert.equal(productPwaReadiness.offlineShellRoute, "/offline");
  assert.equal(productPwaReadiness.serviceWorkerRegistered, false);
  assert.equal(productPwaReadiness.offlineProductDataAvailable, false);
  assert.equal(productPwaReadiness.nativeApplication, false);
  assert.match(source, /Product data is unavailable without a verified connection/);
  assert.doesNotMatch(source, /serviceWorker|mock data|demo data/i);
});