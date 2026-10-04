"use client";

import { useEffect, useState } from "react";
import styles from "./ImageInteraction.module.css";

type ImageState = "EMPTY" | "READY" | "INTEGRATION_PENDING";
export function ImageInteraction() {
  const [preview, setPreview] = useState<string | null>(null);
  const [name, setName] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [state, setState] = useState<ImageState>("EMPTY");
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  function select(file: File | null) {
    if (preview) URL.revokeObjectURL(preview);
    if (!file) { setPreview(null); setName(null); setState("EMPTY"); return; }
    setPreview(URL.createObjectURL(file)); setName(file.name); setState("READY");
  }
  function remove() {
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null); setName(null); setConsent(false); setState("EMPTY");
  }
  function analyze() { if (preview && consent) setState("INTEGRATION_PENDING"); }
  return <section className={styles.panel} aria-labelledby="image-title" aria-describedby="image-accessibility-note">
    <h2 id="image-title">Image interaction</h2>
    <p id="image-accessibility-note">Choose a JPEG, PNG, or WEBP image. The preview remains in this browser and is not uploaded by this foundation. Results must include a text description.</p>
    <label className={styles.picker} htmlFor="medar-image-input">Choose image</label>
    <input id="medar-image-input" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => select(event.target.files?.[0] ?? null)} />
    {preview && <figure>
      {/* A browser-local object URL is intentionally rendered without Next image optimization. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={preview} alt={`Local preview of selected image${name ? `: ${name}` : ""}`} />
      <figcaption>{name}</figcaption>
    </figure>}
    <label><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /> I consent to processing this selected image for this session.</label>
    <div className={styles.controls} role="group" aria-label="Image controls"><button type="button" onClick={analyze} disabled={!preview || !consent}>Analyze</button><button type="button" onClick={remove} disabled={!preview}>Remove</button></div>
    <dl aria-label="Image processing result"><div><dt>Processing</dt><dd role="status" aria-live="polite" aria-atomic="true">{state.replaceAll("_", " ")}</dd></div><div><dt>Text result</dt><dd>{state === "INTEGRATION_PENDING" ? "No vision provider is configured." : "No result."}</dd></div><div><dt>Provenance</dt><dd>{state === "INTEGRATION_PENDING" ? "INTEGRATION_PENDING" : "No provider invocation."}</dd></div></dl>
  </section>;
}