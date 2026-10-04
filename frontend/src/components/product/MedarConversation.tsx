"use client";

import { useState, type FormEvent } from "react";
import { ConfidenceBadge, EmptyState, LoadingState, Status } from "@/components/product/ProductPrimitives";
import { decodeMedarResponse, degradedMessages, degradedResponse, type ProductMedarResponse } from "@/lib/medarProduct";
import styles from "./MedarConversation.module.css";

type Turn = Readonly<{
  id: string;
  prompt: string;
  response: ProductMedarResponse | null;
}>;

export function MedarConversation({ localTestEnabled }: { localTestEnabled: boolean }) {
  const [conversationId] = useState(() => crypto.randomUUID());
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<readonly Turn[]>([]);
  const [pending, setPending] = useState(false);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!localTestEnabled || pending || !message) return;
    const requestId = crypto.randomUUID();
    setDraft("");
    setTurns((current) => [...current, { id: requestId, prompt: message, response: null }]);
    setPending(true);
    let response: ProductMedarResponse;
    try {
      const result = await fetch("/api/product/medar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_id: requestId,
          conversation_id: conversationId,
          message,
        }),
        cache: "no-store",
      });
      response = result.ok
        ? decodeMedarResponse(await result.json(), requestId)
        : degradedResponse(requestId, "MEDAR_UNAVAILABLE");
    } catch {
      response = degradedResponse(requestId, "MEDAR_UNAVAILABLE");
    }
    setTurns((current) => current.map((turn) =>
      turn.id === requestId ? { ...turn, response } : turn
    ));
    setPending(false);
  }

  return (
    <section className={styles.workspace} aria-label="MEDAR conversation">
      <div className={styles.intro}>
        <div>
          <p className={styles.eyebrow}>Personal intelligence</p>
          <h1>MEDAR</h1>
          <p className={styles.lead}>
            Ask for a careful view of the context available to this local test.
            Responses show what is supported and what remains unknown.
          </p>
        </div>
        <Status priority={localTestEnabled ? "information" : "unknown"}
          label={localTestEnabled ? "LOCAL TEST" : "UNAVAILABLE"} />
      </div>

      <div className={styles.thread} aria-live="polite" aria-relevant="additions">
        {turns.length === 0 && (
          <EmptyState title="Start a conversation"
            detail={localTestEnabled
              ? "Your conversation stays in this browser view. No durable memory is written."
              : "Product MEDAR local testing is disabled. No request will be sent."} />
        )}
        {turns.map((turn) => (
          <article className={styles.turn} key={turn.id}>
            <div className={styles.prompt}>
              <span className={styles.speaker}>You</span>
              <p>{turn.prompt}</p>
            </div>
            {turn.response ? (
              <MedarAnswer response={turn.response} />
            ) : (
              <LoadingState label="Waiting for MEDAR" />
            )}
          </article>
        ))}
      </div>

      <form className={styles.composer} onSubmit={send}>
        <label htmlFor="medar-message">Message MEDAR</label>
        <textarea id="medar-message" value={draft} maxLength={8192} rows={4}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={localTestEnabled ? "What would you like to understand?" : "Local testing is disabled"}
          disabled={!localTestEnabled || pending} />
        <div className={styles.composerFooter}>
          <small>No tool execution, portfolio mutation, or durable memory write.</small>
          <button type="submit" disabled={!localTestEnabled || pending || !draft.trim()}>
            {pending ? "Waitingâ€¦" : "Send"}
          </button>
        </div>
      </form>
    </section>
  );
}

function MedarAnswer({ response }: { response: ProductMedarResponse }) {
  const degraded = response.answer === null;
  return (
    <div className={styles.answer}>
      <div className={styles.answerHeader}>
        <span className={styles.speaker}>MEDAR</span>
        <Status priority={degraded ? "unknown" : "information"} label={response.status.replaceAll("_", " ")} />
        {!degraded && <ConfidenceBadge value={response.confidence} />}
      </div>
      {degraded ? (
        <p role="alert">{degradedMessages[response.status]}</p>
      ) : (
        <>
          <p className={styles.answerText}>{response.answer}</p>
          {response.sources.length > 0 && (
            <section aria-label="Sources">
              <h3>Sources</h3>
              <ul>{response.sources.map((source) => (
                <li key={source.source_id}>{source.title} <span>{source.locator}</span></li>
              ))}</ul>
            </section>
          )}
          {response.memory_evidence.length > 0 && (
            <section aria-label="Memory references">
              <h3>Memory references</h3>
              <ul>{response.memory_evidence.map((item) => (
                <li key={item.evidence_id}>{item.summary}</li>
              ))}</ul>
            </section>
          )}
          {response.warnings.length > 0 && (
            <section aria-label="Warnings">
              <h3>Warnings</h3>
              <ul>{response.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
            </section>
          )}
          {response.follow_up_suggestions.length > 0 ? (
            <section aria-label="Follow-up suggestions">
              <h3>Suggested follow-ups</h3>
              <ul>{response.follow_up_suggestions.map((suggestion, index) => (
                <li key={index}>{suggestion}</li>
              ))}</ul>
            </section>
          ) : response.follow_up_needed && (
            <p className={styles.note}>A follow-up may be needed.</p>
          )}
          {response.action_proposals.length > 0 && (
            <section aria-label="Proposed actions">
              <h3>Proposed for review only</h3>
              <ul>{response.action_proposals.map((item) => (
                <li key={item.action_id}>{item.description}</li>
              ))}</ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
