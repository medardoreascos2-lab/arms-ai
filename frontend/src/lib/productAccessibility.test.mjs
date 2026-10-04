import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const shell = readFileSync(new URL("../app/product/product.module.css", import.meta.url), "utf8");
const layout = readFileSync(new URL("../app/product/layout.tsx", import.meta.url), "utf8");
const onboarding = readFileSync(new URL("../components/product/ProductOnboarding.tsx", import.meta.url), "utf8");

function hex(name) {
  const match = shell.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, "i"));
  assert.ok(match, `${name} token missing`);
  return match[1];
}
function luminance(value) {
  const channels = value.slice(1).match(/../g).map((part) => parseInt(part, 16) / 255)
    .map((part) => part <= 0.03928 ? part / 12.92 : ((part + 0.055) / 1.055) ** 2.4);
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}
function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

test("Product shell supports skip navigation and consistent visible focus", () => {
  assert.match(layout, /href="#product-content"/);
  assert.match(layout, /id="product-content"/);
  assert.match(shell, /\.skipLink:focus/);
  assert.match(shell, /:where\(a, button, input, select, textarea, summary\):focus-visible/);
  assert.match(shell, /prefers-reduced-motion: reduce/);
});

test("core Product text and status tokens meet WCAG AA normal-text contrast", () => {
  const background = hex("product-bg");
  for (const token of ["product-text", "product-text-muted", "product-accent", "product-status-critical"]) {
    assert.ok(contrast(hex(token), background) >= 4.5, `${token} contrast below 4.5:1`);
  }
});

test("onboarding exposes live form guidance to assistive technology", () => {
  assert.match(onboarding, /id="onboarding-guidance"/);
  assert.match(onboarding, /aria-live="polite"/);
  assert.match(onboarding, /aria-describedby="onboarding-guidance"/);
  assert.match(onboarding, /<fieldset/);
  assert.match(onboarding, /<legend>/);
});