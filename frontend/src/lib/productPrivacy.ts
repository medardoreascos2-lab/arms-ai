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
];
