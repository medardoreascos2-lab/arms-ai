import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), "utf8");
const push = read("../components/product/PushToTalk.tsx");
const image = read("../components/product/ImageInteraction.tsx");
const avatar = read("../components/product/AvatarSurface.tsx");
const styles = [
  read("../components/product/PushToTalk.module.css"),
  read("../components/product/ImageInteraction.module.css"),
  read("../components/product/AvatarSurface.module.css"),
].join("\n");

test("voice, image, and avatar surfaces expose live text alternatives", () => {
  for (const source of [push, image, avatar]) {
    assert.match(source, /aria-live="polite"/);
    assert.match(source, /aria-describedby=/);
  }
  assert.match(push, /Transcript/);
  assert.match(push, /Text response/);
  assert.match(image, /Text result/);
  assert.match(avatar, /Visual state/);
});

test("multimodal controls remain keyboard native and visibly grouped", () => {
  assert.match(push, /<button type="button"/);
  assert.match(push, /role="group" aria-label="Microphone controls"/);
  assert.match(image, /htmlFor="medar-image-input"/);
  assert.match(image, /role="group" aria-label="Image controls"/);
  assert.doesNotMatch(push + image, /tabIndex=\{-1\}/);
});

test("multimodal presentation honors reduced motion and visible focus", () => {
  assert.match(styles, /prefers-reduced-motion:\s*reduce/);
  assert.match(styles, /:focus-visible/);
});