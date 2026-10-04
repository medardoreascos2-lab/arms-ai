import test from "node:test";
import assert from "node:assert/strict";
import { privacyCenterItems } from "./productPrivacy.ts";

test("Privacy Center exposes every required seam without claiming data", () => {
  assert.deepEqual(privacyCenterItems.map((item) => item.id), [
    "MEMORY", "RETENTION", "EXPORT", "REMOVAL", "SERVICES", "ACTIVITY",
    "MICROPHONE", "CAMERA", "VOICE", "IMAGE_RETENTION", "CAMERA_RETENTION",
    "PRESENCE", "WEARABLES", "HOME_INTEGRATIONS", "AVATAR_ACTIVITY",
  ]);
  assert.ok(privacyCenterItems.every((item) =>
    item.status === "UNKNOWN" || item.status === "INTEGRATION_PENDING"));
  const removal = privacyCenterItems.find((item) => item.id === "REMOVAL");
  assert.match(removal.description, /no direct deletion/i);
});
