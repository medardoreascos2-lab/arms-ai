import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";

function files(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const path = join(root, entry.name);
    return entry.isDirectory() ? files(path) : [path];
  });
}

const roots = [new URL("../components/product", import.meta.url), new URL("../app/product", import.meta.url)];
const sources = roots.flatMap((url) => files(fileURLToPath(url))).filter((path) => [".ts", ".tsx"].includes(extname(path)))
  .map((path) => [path, readFileSync(path, "utf8")]);

test("Product source has no unsafe HTML or dynamic-code sink", () => {
  const forbidden = /dangerouslySetInnerHTML|\.innerHTML\s*=|\.outerHTML\s*=|document\.write|\beval\s*\(|new Function|javascript:/;
  for (const [path, source] of sources) assert.doesNotMatch(source, forbidden, path);
});

test("Product components do not expose secrets or debug logging", () => {
  const forbidden = /console\.(log|debug|info)|password|private[_-]?key|api[_-]?key|bearer\s/i;
  for (const [path, source] of sources) assert.doesNotMatch(source, forbidden, path);
});

test("notification browser contract excludes tenant and user scope", () => {
  const source = readFileSync(new URL("./productNotifications.ts", import.meta.url), "utf8");
  assert.doesNotMatch(source, /^\s*(tenant_id|user_id):/m);
  assert.match(source, /!\("user_id" in item\)/);
  assert.match(source, /!\("tenant_id" in item\)/);
});