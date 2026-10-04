"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./PushToTalk.module.css";

type VoiceUiState = "IDLE" | "REQUESTING_PERMISSION" | "RECORDING" | "STOPPED" | "CANCELLED" | "MIC_PERMISSION_DENIED" | "MIC_UNAVAILABLE";

export function PushToTalk() {
  const [state, setState] = useState<VoiceUiState>("IDLE");
  const streamRef = useRef<MediaStream | null>(null);
  function stopTracks() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }
  useEffect(() => () => stopTracks(), []);

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia) { setState("MIC_UNAVAILABLE"); return; }
    setState("REQUESTING_PERMISSION");
    try {
      streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      setState("RECORDING");
    } catch { setState("MIC_PERMISSION_DENIED"); }
  }
  function stop() { stopTracks(); setState("STOPPED"); }
  function cancel() { stopTracks(); setState("CANCELLED"); }

  const active = state === "RECORDING";
  return (
    <section className={styles.panel} aria-labelledby="voice-input-title">
      <div className={styles.header}>
        <div><h2 id="voice-input-title">Push to talk</h2><p>Microphone access starts only after you press Start and ends when you stop, cancel, leave, or revoke access.</p></div>
        <span className={active ? styles.active : styles.inactive} role="status" aria-live="polite">{active ? "Recording indicator: active" : state.replaceAll("_", " ")}</span>
      </div>
      <div className={styles.controls}>
        <button type="button" onClick={start} disabled={active || state === "REQUESTING_PERMISSION"}>Start microphone</button>
        <button type="button" onClick={stop} disabled={!active}>Stop</button>
        <button type="button" onClick={cancel} disabled={!active}>Cancel</button>
      </div>
      <dl className={styles.results}>
        <div><dt>Transcription</dt><dd>{state === "STOPPED" ? "STT provider integration pending." : "No transcription."}</dd></div>
        <div><dt>MEDAR response</dt><dd>No voice request is sent by this interface foundation.</dd></div>
        <div><dt>Playback</dt><dd><button type="button" disabled aria-label="Play synthesized MEDAR response">Play unavailable</button></dd></div>
      </dl>
      <p className={styles.privacy}>No background microphone, upload, audio storage, or biometric voice profile.</p>
    </section>
  );
}
