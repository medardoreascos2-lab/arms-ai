export type MedarStatus =
  | "SUCCESS" | "PARTIAL" | "BLOCKED" | "FAILED" | "NEEDS_CONFIRMATION"
  | "MEDAR_UNAVAILABLE" | "MODEL_UNAVAILABLE" | "MEMORY_UNAVAILABLE"
  | "PERMISSION_DENIED" | "ENTITLEMENT_REQUIRED" | "RATE_LIMITED"
  | "INVALID_REQUEST" | "SESSION_INVALID" | "LOCAL_TEST_DISABLED";

export type EvidenceReference = Readonly<{
  evidence_id: string;
  summary: string;
  digest: string;
}>;

export type SourceReference = Readonly<{
  source_id: string;
  title: string;
  locator: string;
}>;

export type MemoryContextItem = Readonly<{
  evidence_id: string;
  category: "PREFERENCE" | "GOAL" | "DECISION" | "PROJECT";
  summary: string;
  provenance: string;
  sensitivity: "STANDARD" | "SENSITIVE" | "UNKNOWN";
}>;

export type ActionProposal = Readonly<{
  action_id: string;
  description: string;
  requires_confirmation: boolean;
  state: "PROPOSED_ONLY";
  execution_authorized: false;
}>;

export type ProductMedarResponse = Readonly<{
  response_id: string | null;
  request_id: string;
  status: MedarStatus;
  answer: string | null;
  confidence: number | null;
  reasoning_summary: string | null;
  why_not: readonly string[];
  risks: readonly string[];
  data_used: readonly string[];
  what_would_change_the_view: readonly string[];
  sources: readonly SourceReference[];
  tool_evidence: readonly EvidenceReference[];
  memory_evidence: readonly EvidenceReference[];
  memory_context: readonly MemoryContextItem[];
  warnings: readonly string[];
  follow_up_needed: boolean;
  follow_up_suggestions: readonly string[];
  action_proposals: readonly ActionProposal[];
}>;

const statuses = new Set<MedarStatus>([
  "SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "NEEDS_CONFIRMATION",
  "MEDAR_UNAVAILABLE", "MODEL_UNAVAILABLE", "MEMORY_UNAVAILABLE",
  "PERMISSION_DENIED", "ENTITLEMENT_REQUIRED", "RATE_LIMITED",
  "INVALID_REQUEST", "SESSION_INVALID", "LOCAL_TEST_DISABLED",
]);

export function degradedResponse(requestId: string, status: MedarStatus): ProductMedarResponse {
  return {
    response_id: null, request_id: requestId, status, answer: null,
    confidence: null, reasoning_summary: null, why_not: [], risks: [],
    data_used: [], what_would_change_the_view: [], sources: [],
    tool_evidence: [], memory_evidence: [], memory_context: [], warnings: [],
    follow_up_needed: false, follow_up_suggestions: [], action_proposals: [],
  };
}

export function decodeMedarResponse(value: unknown, requestId: string): ProductMedarResponse {
  if (!value || typeof value !== "object") {
    return degradedResponse(requestId, "MEDAR_UNAVAILABLE");
  }
  const item = value as Record<string, unknown>;
  if (item.request_id !== requestId || !statuses.has(item.status as MedarStatus)) {
    return degradedResponse(requestId, "MEDAR_UNAVAILABLE");
  }
  const status = item.status as MedarStatus;
  const success = new Set<MedarStatus>(["SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "NEEDS_CONFIRMATION"]);
  if (success.has(status)) {
    if (typeof item.response_id !== "string" || typeof item.answer !== "string"
        || typeof item.confidence !== "number" || !Number.isFinite(item.confidence)
        || item.confidence < 0 || item.confidence > 1) {
      return degradedResponse(requestId, "MEDAR_UNAVAILABLE");
    }
  } else if (item.answer != null || item.confidence != null || (
    (Array.isArray(item.action_proposals) && item.action_proposals.length > 0)
    || (Array.isArray(item.follow_up_suggestions) && item.follow_up_suggestions.length > 0)
    || item.reasoning_summary != null
    || ["sources", "tool_evidence", "memory_evidence", "memory_context"].some(
      (key) => Array.isArray(item[key]) && item[key].length > 0)
    || ["why_not", "risks", "data_used", "what_would_change_the_view"].some(
      (key) => Array.isArray(item[key]) && item[key].length > 0)
  )) {
    return degradedResponse(requestId, "MEDAR_UNAVAILABLE");
  }
  return {
    response_id: typeof item.response_id === "string" ? item.response_id : null,
    request_id: requestId,
    status,
    answer: typeof item.answer === "string" ? item.answer : null,
    confidence: typeof item.confidence === "number" ? item.confidence : null,
    reasoning_summary: typeof item.reasoning_summary === "string" ? item.reasoning_summary : null,
    why_not: strings(item.why_not),
    risks: strings(item.risks),
    data_used: strings(item.data_used),
    what_would_change_the_view: strings(item.what_would_change_the_view),
    sources: Array.isArray(item.sources) ? item.sources.filter(isSourceReference) : [],
    tool_evidence: Array.isArray(item.tool_evidence) ? item.tool_evidence.filter(isEvidenceReference) : [],
    memory_evidence: Array.isArray(item.memory_evidence) ? item.memory_evidence.filter(isEvidenceReference) : [],
    memory_context: Array.isArray(item.memory_context) ? item.memory_context.filter(isMemoryContextItem) : [],
    warnings: strings(item.warnings),
    follow_up_needed: item.follow_up_needed === true,
    follow_up_suggestions: strings(item.follow_up_suggestions),
    action_proposals: Array.isArray(item.action_proposals)
      ? item.action_proposals.filter((part): part is ActionProposal =>
          part && typeof part === "object" && part.state === "PROPOSED_ONLY"
          && part.execution_authorized === false)
      : [],
  };
}

export const degradedMessages: Record<MedarStatus, string> = {
  SUCCESS: "Response ready.",
  PARTIAL: "A partial response is available.",
  BLOCKED: "MEDAR blocked this request.",
  FAILED: "MEDAR could not complete this request.",
  NEEDS_CONFIRMATION: "Review is needed before any further step.",
  MEDAR_UNAVAILABLE: "MEDAR is unavailable in this local test.",
  MODEL_UNAVAILABLE: "The local model is unavailable.",
  MEMORY_UNAVAILABLE: "Memory context is unavailable.",
  PERMISSION_DENIED: "This request is not permitted.",
  ENTITLEMENT_REQUIRED: "An active membership with MEDAR access is required.",
  RATE_LIMITED: "The local test usage limit has been reached.",
  INVALID_REQUEST: "The request could not be accepted.",
  SESSION_INVALID: "The local test session is invalid or expired.",
  LOCAL_TEST_DISABLED: "Product MEDAR local testing is disabled.",
};

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((part): part is string => typeof part === "string") : [];
}

function isSourceReference(value: unknown): value is SourceReference {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.source_id === "string" && typeof item.title === "string"
    && typeof item.locator === "string";
}

function isEvidenceReference(value: unknown): value is EvidenceReference {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.evidence_id === "string" && typeof item.summary === "string"
    && typeof item.digest === "string";
}

function isMemoryContextItem(value: unknown): value is MemoryContextItem {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.evidence_id === "string" && item.evidence_id.length > 0
    && ["PREFERENCE", "GOAL", "DECISION", "PROJECT"].includes(item.category as string)
    && typeof item.summary === "string" && item.summary.length > 0
    && typeof item.provenance === "string" && item.provenance.length > 0
    && ["STANDARD", "SENSITIVE", "UNKNOWN"].includes(item.sensitivity as string);
}
