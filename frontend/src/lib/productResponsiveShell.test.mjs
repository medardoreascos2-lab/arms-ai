import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../app/product/product.module.css", import.meta.url), "utf8");
const layout = readFileSync(new URL("../app/product/layout.tsx", import.meta.url), "utf8");

test("Product shell defines mobile, tablet, and desktop layouts", () => {
  assert.match(css, /padding: var\(--product-space-4\)/);
  assert.match(css, /@media \(min-width: 40rem\)/);
  assert.match(css, /@media \(min-width: 64rem\)/);
  assert.match(css, /grid-template-columns: minmax\(14rem, 17rem\) minmax\(0, 1fr\)/);
  assert.match(css, /overflow-wrap: anywhere/);
  assert.match(layout, /className=\{styles\.content\}/);
});