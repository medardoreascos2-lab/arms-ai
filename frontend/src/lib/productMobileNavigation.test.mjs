import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const component = readFileSync(new URL("../components/product/ProductNavigation.tsx", import.meta.url), "utf8");
const css = readFileSync(new URL("../components/product/ProductNavigation.module.css", import.meta.url), "utf8");

test("mobile navigation uses a keyboard-accessible native disclosure", () => {
  assert.match(component, /<details className=\{styles\.mobileNav\}>/);
  assert.match(component, /<summary className=\{styles\.mobileSummary\}>Product navigation<\/summary>/);
  assert.match(component, /aria-label="Product mobile"/);
  assert.match(css, /\.mobileSummary:focus-visible/);
});

test("navigation swaps mobile and desktop presentations at the desktop breakpoint", () => {
  assert.match(css, /\.desktopNav \{ display: none; \}/);
  assert.match(css, /@media \(min-width: 64rem\)/);
  assert.match(css, /\.mobileNav \{ display: none; \}/);
  assert.match(css, /position: sticky/);
});