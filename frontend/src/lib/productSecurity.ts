export const securityCenterItems = [
  { id: "SESSIONS", title: "Local sessions", detail: "Trusted session metadata will appear when a scoped source is connected.", status: "UNKNOWN" },
  { id: "EVENTS", title: "Recent security events", detail: "No verified security-event source is connected.", status: "UNKNOWN" },
  { id: "MFA", title: "Multi-factor authentication", detail: "Future provider-neutral seam; no provisioning occurs here.", status: "INTEGRATION_PENDING" },
  { id: "PASSKEYS", title: "Passkeys", detail: "Future provider-neutral seam; no provisioning occurs here.", status: "INTEGRATION_PENDING" },
  { id: "PERMISSIONS", title: "Sensitive permissions", detail: "Broker, PAPER, LIVE, payments, and financial mutation remain unavailable.", status: "DENIED" },
] as const;
