"use client";

import { useEffect, useState } from "react";
import { Card, Status } from "./ProductPrimitives";
import {
  advanceOnboarding,
  canAdvanceOnboarding,
  initialOnboardingDraft,
  loadOnboardingDraft,
  onboardingSteps,
  previousOnboarding,
  saveOnboardingDraft,
  type ProductMemoryConsent,
  type ProductOnboardingDraft,
  type ProductOnboardingGoal,
  type ProductNotificationChoice,
} from "@/lib/productOnboarding";
import styles from "./ProductOnboarding.module.css";

const goals: readonly ProductOnboardingGoal[] = [
  "TRADING", "INVESTING", "PORTFOLIO", "BUSINESS",
  "LEARNING", "PERSONAL_ASSISTANT",
];
const consents: readonly ProductMemoryConsent[] = [
  "SESSION_ONLY", "ALLOW_LOW_SENSITIVITY", "REVIEW_BEFORE_SAVE", "DO_NOT_SAVE",
];

export function ProductOnboarding() {
  const [draft, setDraft] = useState<ProductOnboardingDraft>(() =>
    typeof window === "undefined"
      ? initialOnboardingDraft()
      : loadOnboardingDraft(window.localStorage));

  useEffect(() => {
    saveOnboardingDraft(window.localStorage, draft);
  }, [draft]);

  const stepNumber = onboardingSteps.indexOf(draft.currentStep) + 1;
  function update(values: Partial<ProductOnboardingDraft>) {
    setDraft((current) => ({ ...current, ...values }));
  }
  function toggleGoal(goal: ProductOnboardingGoal) {
    const selected = draft.selectedGoals.includes(goal)
      ? draft.selectedGoals.filter((item) => item !== goal)
      : [...draft.selectedGoals, goal];
    update({ selectedGoals: selected, goalsConfirmed: false });
  }

  return <div className={styles.flow}>
    <div className={styles.progress}>
      <Status priority="information" label={"STEP " + stepNumber + " OF " + onboardingSteps.length} />
      <Status priority="watch" label="LOCAL DEVICE PREVIEW" />
      <span>{draft.currentStep.replaceAll("_", " ")}</span>
    </div>
    <Card id="onboarding-step" title={titleFor(draft.currentStep)}
      description="Your choices stay explicit and can be reviewed.">
      {draft.currentStep === "WELCOME" && <p>Set up the Product preview at your pace. Your choices can be changed later.</p>}
      {draft.currentStep === "GOALS" && <fieldset className={styles.options}>
        <legend>Optional goals</legend>
        {goals.map((goal) => <label key={goal}>
          <input type="checkbox" checked={draft.selectedGoals.includes(goal)}
            onChange={() => toggleGoal(goal)} /> {goal.replaceAll("_", " ")}
        </label>)}
        <label><input type="checkbox" checked={draft.goalsConfirmed}
          onChange={(event) => update({ goalsConfirmed: event.target.checked })} />
          Confirm this selection, including no goals</label>
      </fieldset>}
      {draft.currentStep === "FINANCIAL_EXPECTATIONS" && <div>
        <p>Financial surfaces provide analysis and read-only context. They cannot trade, change a portfolio, or provide guaranteed outcomes.</p>
        <Check label="I understand these financial expectations"
          checked={draft.financialExpectationsAcknowledged}
          onChange={(checked) => update({ financialExpectationsAcknowledged: checked })} />
      </div>}
      {draft.currentStep === "MEMORY_CONSENT" && <fieldset className={styles.options}>
        <legend>Choose how Product memory may be used</legend>
        {consents.map((consent) => <label key={consent}>
          <input type="radio" name="memory-consent" value={consent}
            checked={draft.memoryConsent === consent}
            onChange={() => update({ memoryConsent: consent })} />
          {consent.replaceAll("_", " ")}
        </label>)}
      </fieldset>}
      {draft.currentStep === "NOTIFICATION_PREFS" && <fieldset className={styles.options}>
        <legend>Notification preference</legend>
        {(["IN_APP", "NONE"] as readonly ProductNotificationChoice[]).map((choice) => <label key={choice}>
          <input type="radio" name="notification-choice" value={choice}
            checked={draft.notificationChoice === choice}
            onChange={() => update({ notificationChoice: choice, notificationChoiceConfirmed: true })} />
          {choice.replaceAll("_", " ")}
        </label>)}
      </fieldset>}
      {draft.currentStep === "PRIVACY" && <div>
        <p>Review memory, retention, connected-service, and activity controls in the Privacy Center when available.</p>
        <Check label="I reviewed this privacy summary" checked={draft.privacyReviewed}
          onChange={(checked) => update({ privacyReviewed: checked })} />
      </div>}
      {draft.currentStep === "DONE" && <div>
        <Status priority="information" label="COMPLETED" />
        <p>Your local preview setup is complete. No production account, payment, or trading authority was created.</p>
      </div>}
    </Card>
    <div className={styles.actions}>
      <button type="button" onClick={() => setDraft(previousOnboarding(draft))}
        disabled={draft.currentStep === "WELCOME"}>Back</button>
      {draft.currentStep !== "DONE" && <button type="button"
        onClick={() => setDraft(advanceOnboarding(draft))}
        disabled={!canAdvanceOnboarding(draft)}>Continue</button>}
    </div>
  </div>;
}

function Check({ label, checked, onChange }: {
  label: string; checked: boolean; onChange: (checked: boolean) => void;
}) {
  return <label><input type="checkbox" checked={checked}
    onChange={(event) => onChange(event.target.checked)} /> {label}</label>;
}

function titleFor(step: ProductOnboardingDraft["currentStep"]): string {
  return ({
    WELCOME: "Welcome",
    GOALS: "Choose your goals",
    FINANCIAL_EXPECTATIONS: "Financial expectations",
    MEMORY_CONSENT: "Memory consent",
    NOTIFICATION_PREFS: "Notification preferences",
    PRIVACY: "Privacy review",
    DONE: "Setup complete",
  })[step];
}
