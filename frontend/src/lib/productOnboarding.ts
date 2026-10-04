export const onboardingSteps = [
  "WELCOME", "GOALS", "FINANCIAL_EXPECTATIONS", "MEMORY_CONSENT",
  "NOTIFICATION_PREFS", "PRIVACY", "DONE",
] as const;
export type ProductOnboardingStep = typeof onboardingSteps[number];
export type ProductOnboardingGoal =
  | "TRADING" | "INVESTING" | "PORTFOLIO" | "BUSINESS"
  | "LEARNING" | "PERSONAL_ASSISTANT";
export type ProductMemoryConsent =
  | "SESSION_ONLY" | "ALLOW_LOW_SENSITIVITY"
  | "REVIEW_BEFORE_SAVE" | "DO_NOT_SAVE";
export type ProductNotificationChoice = "IN_APP" | "NONE";

export type ProductOnboardingDraft = Readonly<{
  schemaVersion: 1;
  status: "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED";
  currentStep: ProductOnboardingStep;
  selectedGoals: readonly ProductOnboardingGoal[];
  goalsConfirmed: boolean;
  financialExpectationsAcknowledged: boolean;
  memoryConsent: ProductMemoryConsent | null;
  notificationChoice: ProductNotificationChoice;
  notificationChoiceConfirmed: boolean;
  privacyReviewed: boolean;
}>;

export const onboardingStorageKey = "arms.product.onboarding.v1";

export function initialOnboardingDraft(): ProductOnboardingDraft {
  return {
    schemaVersion: 1,
    status: "NOT_STARTED",
    currentStep: "WELCOME",
    selectedGoals: [],
    goalsConfirmed: false,
    financialExpectationsAcknowledged: false,
    memoryConsent: null,
    notificationChoice: "IN_APP",
    notificationChoiceConfirmed: false,
    privacyReviewed: false,
  };
}

const goals = new Set([
  "TRADING", "INVESTING", "PORTFOLIO", "BUSINESS",
  "LEARNING", "PERSONAL_ASSISTANT",
]);
const consents = new Set([
  "SESSION_ONLY", "ALLOW_LOW_SENSITIVITY",
  "REVIEW_BEFORE_SAVE", "DO_NOT_SAVE",
]);

export function decodeOnboardingDraft(value: unknown): ProductOnboardingDraft {
  if (!value || typeof value !== "object") return initialOnboardingDraft();
  const item = value as Record<string, unknown>;
  if (item.schemaVersion !== 1
      || !onboardingSteps.includes(item.currentStep as ProductOnboardingStep)
      || !["NOT_STARTED", "IN_PROGRESS", "COMPLETED"].includes(item.status as string)
      || !Array.isArray(item.selectedGoals)
      || !item.selectedGoals.every((goal) => goals.has(goal as string))
      || new Set(item.selectedGoals).size !== item.selectedGoals.length
      || typeof item.goalsConfirmed !== "boolean"
      || typeof item.financialExpectationsAcknowledged !== "boolean"
      || (item.memoryConsent !== null && !consents.has(item.memoryConsent as string))
      || !["IN_APP", "NONE"].includes(item.notificationChoice as string)
      || typeof item.notificationChoiceConfirmed !== "boolean"
      || typeof item.privacyReviewed !== "boolean") {
    return initialOnboardingDraft();
  }
  if (item.status === "COMPLETED" && item.currentStep !== "DONE") {
    return initialOnboardingDraft();
  }
  return item as ProductOnboardingDraft;
}

export function loadOnboardingDraft(
  storage: Pick<Storage, "getItem">,
): ProductOnboardingDraft {
  try {
    const raw = storage.getItem(onboardingStorageKey);
    return raw === null ? initialOnboardingDraft() : decodeOnboardingDraft(JSON.parse(raw));
  } catch {
    return initialOnboardingDraft();
  }
}

export function saveOnboardingDraft(
  storage: Pick<Storage, "setItem">,
  draft: ProductOnboardingDraft,
): void {
  storage.setItem(onboardingStorageKey, JSON.stringify(decodeOnboardingDraft(draft)));
}

export function canAdvanceOnboarding(draft: ProductOnboardingDraft): boolean {
  if (draft.currentStep === "GOALS") return draft.goalsConfirmed;
  if (draft.currentStep === "FINANCIAL_EXPECTATIONS") {
    return draft.financialExpectationsAcknowledged;
  }
  if (draft.currentStep === "MEMORY_CONSENT") return draft.memoryConsent !== null;
  if (draft.currentStep === "NOTIFICATION_PREFS") {
    return draft.notificationChoiceConfirmed;
  }
  if (draft.currentStep === "PRIVACY") return draft.privacyReviewed;
  return true;
}

export function advanceOnboarding(
  draft: ProductOnboardingDraft,
): ProductOnboardingDraft {
  if (!canAdvanceOnboarding(draft) || draft.currentStep === "DONE") return draft;
  const index = onboardingSteps.indexOf(draft.currentStep);
  const currentStep = onboardingSteps[index + 1];
  return {
    ...draft,
    currentStep,
    status: currentStep === "DONE" ? "COMPLETED" : "IN_PROGRESS",
  };
}

export function previousOnboarding(
  draft: ProductOnboardingDraft,
): ProductOnboardingDraft {
  const index = onboardingSteps.indexOf(draft.currentStep);
  if (index <= 0) return draft;
  return { ...draft, currentStep: onboardingSteps[index - 1], status: "IN_PROGRESS" };
}
