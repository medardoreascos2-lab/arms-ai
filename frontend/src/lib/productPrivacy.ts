export type PrivacyCenterItem = Readonly<{
  id: string;
  title: string;
  description: string;
  status: "UNKNOWN" | "INTEGRATION_PENDING";
}>;

export const privacyCenterItems: readonly PrivacyCenterItem[] = [
  { id: "MEMORY", title: "Memory categories", description: "Review categories and provenance when a trusted memory source is connected.", status: "UNKNOWN" },
  { id: "RETENTION", title: "Retention choices", description: "No retention preference has been configured in this local preview.", status: "UNKNOWN" },
  { id: "EXPORT", title: "Data export", description: "A provider-neutral export request seam is defined.", status: "INTEGRATION_PENDING" },
  { id: "REMOVAL", title: "Removal requests", description: "Requests require review; this screen performs no direct deletion.", status: "INTEGRATION_PENDING" },
  { id: "SERVICES", title: "Connected services", description: "No verified connected-service source is available.", status: "UNKNOWN" },
  { id: "ACTIVITY", title: "Activity history", description: "Activity-history visibility is unavailable without a trusted source.", status: "UNKNOWN" },
  { id: "MICROPHONE", title: "Microphone permission", description: "Off by default; access is explicit, session-scoped, visible, and revocable.", status: "UNKNOWN" },
  { id: "CAMERA", title: "Camera permission", description: "Off by default; no background or always-on capture.", status: "UNKNOWN" },
  { id: "VOICE", title: "Voice preferences", description: "Review language, speaking rate, auto-speak, quiet hours, and private mode.", status: "UNKNOWN" },
  { id: "IMAGE_RETENTION", title: "Image retention", description: "No image retention provider is connected.", status: "INTEGRATION_PENDING" },
  { id: "CAMERA_RETENTION", title: "Camera retention", description: "Camera frames default to no storage or session-only retention.", status: "INTEGRATION_PENDING" },
  { id: "PRESENCE", title: "Presence", description: "Presence is unknown until explicitly enabled for a session.", status: "UNKNOWN" },
  { id: "WEARABLES", title: "Wearable data", description: "Separate health-data consent is required; no provider is connected.", status: "INTEGRATION_PENDING" },
  { id: "HOME_INTEGRATIONS", title: "Home integrations", description: "Device actions remain proposed only with no control authority.", status: "INTEGRATION_PENDING" },
  { id: "AVATAR_ACTIVITY", title: "Avatar activity", description: "Presentation activity is unavailable without an active scoped session.", status: "UNKNOWN" },
];
