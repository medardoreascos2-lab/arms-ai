import styles from "./AvatarSurface.module.css";

export function AvatarSurface() {
  return <section className={styles.surface} aria-labelledby="avatar-title" aria-describedby="avatar-accessibility-note">
    <header><div><p className={styles.eyebrow}>Presentation foundation</p><h1 id="avatar-title">MEDAR avatar</h1></div><span className={styles.status} role="status" aria-live="polite" aria-atomic="true">OFFLINE</span></header>
    <div className={styles.placeholder} role="img" aria-label="Avatar presentation placeholder, offline"><span aria-hidden="true">M</span></div>
    <p id="avatar-accessibility-note" className={styles.alternative}>Avatar state, speech, and motion always have text alternatives. Motion respects reduced-motion preferences.</p>
    <dl><div><dt>Transcript</dt><dd>No active MEDAR response.</dd></div><div><dt>Voice</dt><dd>Synthetic reference only. No production TTS.</dd></div><div><dt>Visual state</dt><dd>Offline placeholder. No animation is active.</dd></div><div><dt>Privacy</dt><dd>Microphone off. Camera off. No background capture.</dd></div><div><dt>Authority</dt><dd>Presentation only. No tools, devices, broker, PAPER, or LIVE authority.</dd></div></dl>
  </section>;
}