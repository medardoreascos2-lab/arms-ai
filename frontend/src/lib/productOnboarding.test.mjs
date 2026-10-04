import test from "node:test";
import assert from "node:assert/strict";
import {
  advanceOnboarding,
  canAdvanceOnboarding,
  decodeOnboardingDraft,
  initialOnboardingDraft,
  loadOnboardingDraft,
  onboardingStorageKey,
  saveOnboardingDraft,
} from "./productOnboarding.ts";

test("onboarding cannot advance past explicit-choice steps without confirmation", () => {
  let draft = advanceOnboarding(initialOnboardingDraft());
  assert.equal(draft.currentStep, "GOALS");
  assert.equal(canAdvanceOnboarding(draft), false);
  assert.equal(advanceOnboarding(draft), draft);

  draft = { ...draft, goalsConfirmed: true };
  draft = advanceOnboarding(draft);
  assert.equal(draft.currentStep, "FINANCIAL_EXPECTATIONS");
  assert.equal(canAdvanceOnboarding(draft), false);
});

test("DO_NOT_SAVE is a valid explicit memory choice and no default consent exists", () => {
  const initial = initialOnboardingDraft();
  assert.equal(initial.memoryConsent, null);
  let draft = { ...initial, currentStep: "MEMORY_CONSENT", status: "IN_PROGRESS" };
  assert.equal(canAdvanceOnboarding(draft), false);
  draft = { ...draft, memoryConsent: "DO_NOT_SAVE" };
  assert.equal(canAdvanceOnboarding(draft), true);
});

test("validated local storage makes onboarding resumable", () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
  const draft = {
    ...initialOnboardingDraft(),
    status: "IN_PROGRESS",
    currentStep: "MEMORY_CONSENT",
    selectedGoals: ["LEARNING"],
    goalsConfirmed: true,
    financialExpectationsAcknowledged: true,
  };
  saveOnboardingDraft(storage, draft);
  assert.equal(values.has(onboardingStorageKey), true);
  assert.deepEqual(loadOnboardingDraft(storage), draft);
});

test("malformed or invented onboarding values fail closed to initial state", () => {
  assert.deepEqual(decodeOnboardingDraft({
    ...initialOnboardingDraft(),
    selectedGoals: ["HEALTH_DIAGNOSIS"],
  }), initialOnboardingDraft());
  assert.deepEqual(decodeOnboardingDraft({
    ...initialOnboardingDraft(),
    memoryConsent: "ALLOW_ALL",
  }), initialOnboardingDraft());
});
