export type BetaUser = {
  user_id: string;
  email: string;
  role: "admin" | "beta_user" | "disabled";
  status: "active" | "disabled";
  beta_start_at: string | null;
  beta_expires_at: string | null;
  created_at: string;
  last_login_at: string | null;
};

export type BetaSignal = {
  signal_id: string;
  created_at: string | null;
  updated_at: string | null;
  instrument: string;
  contract: string;
  direction: "BUY" | "SELL" | "NO_TRADE" | "WAITING";
  status: "WAITING" | "ACTIVE" | "TARGET_HIT" | "STOPPED" | "CANCELLED" | "EXPIRED";
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  reward_risk: number | null;
  confidence: number | null;
  confluence: number | null;
  paper_only: true;
  decision_summary: string;
};

export type BetaPaperPosition = {
  position_id: string;
  instrument: string;
  direction: string;
  quantity: number | null;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  unrealized_pnl: number | null;
  opened_at: string | null;
  status: string;
  paper_only: true;
};

export type BetaRuntimeObservation = {
  status: string;
  paper_api_status: string;
  analysis_status: string;
  ninjatrader_status: string;
  heartbeat_at: string | null;
  heartbeat_age_seconds: number | null;
  data_freshness: string;
  market_session_status: string;
  feed_freshness: string;
  paper_runtime_health: string;
  paper_execution_authority: string;
  live_execution_authority: "DISABLED";
  paper_ready: boolean;
  paper_authority_state: string;
  paper_execution_enabled: boolean;
  live_execution_allowed: false;
  analysis_only: boolean;
  order_submit_reachable: boolean;
  contract: string;
  session_state: string;
  realized_paper_pnl: number | null;
  current_position: BetaPaperPosition | null;
  read_only: true;
};
export type BetaHistoryRecord = {
  record_id: string;
  record_type: "PAPER_SIGNAL" | "PAPER_TRADE";
  instrument: string;
  direction: string;
  entry: number | null;
  stop: number | null;
  target: number | null;
  entry_time: string | null;
  exit_time: string | null;
  exit_price: number | null;
  result: string | null;
  points_or_ticks: number | null;
  points_or_ticks_unit: string | null;
  paper_pnl: number | null;
  status: string;
  paper_only: true;
};

export type BetaPerformance = {
  paper_only: true;
  as_of: string;
  today_pnl: number | null;
  cumulative_pnl: number | null;
  trades: number;
  wins: number | null;
  losses: number | null;
  win_rate: number | null;
  average_win: number | null;
  average_loss: number | null;
  profit_factor: number | null;
  maximum_drawdown: number | null;
  availability: Record<string, string>;
};

export type BetaDashboardBundle = {
  contract_version: "1.0";
  observed_at: string;
  paper_only: true;
  product_state: "BETA";
  disclaimer: string;
  live: {
    arms_status: string;
    market_status: string;
    instrument: string;
    contract: string;
    current_signal: string;
    signal: BetaSignal;
    position: BetaPaperPosition | null;
  };
  history: { status: string; records: BetaHistoryRecord[] };
  performance: BetaPerformance;
  runtime: BetaRuntimeObservation;
};

export type BetaUserList = {
  users: BetaUser[];
  counts: { total: number; active: number; expired: number; disabled: number };
};

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
let csrfToken = "";

export class BetaApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "BetaApiError";
  }
}

function apiOrigin(): string {
  const url = new URL(API_URL);
  if (
    url.username || url.password || url.search || url.hash || url.pathname !== "/" ||
    !(url.protocol === "https:" || (url.protocol === "http:" &&
      ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)))
  ) {
    throw new Error("Beta API requires HTTPS or a loopback origin.");
  }
  return url.origin;
}

async function betaRequest<T>(
  path: string,
  options: { method?: "GET" | "POST" | "PATCH"; body?: unknown; csrf?: boolean; signal?: AbortSignal } = {},
): Promise<T> {
  if (!path.startsWith("/api/v1/beta/") || path.startsWith("//")) {
    throw new Error("Invalid Beta API path.");
  }
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.csrf) {
    if (!csrfToken) throw new Error("Beta session verification is required.");
    headers["X-ARMS-BETA-CSRF"] = csrfToken;
  }
  const response = await fetch(`${apiOrigin()}${path}`, {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    credentials: "include",
    cache: "no-store",
    redirect: "error",
    signal: options.signal,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) csrfToken = "";
    throw new BetaApiError(
      String(payload.detail ?? `Beta API Error: ${response.status}`),
      response.status,
    );
  }
  return payload as T;
}

function acceptCsrf<T extends { csrf_token: string }>(payload: T): T {
  csrfToken = payload.csrf_token;
  return payload;
}

export async function loginBeta(email: string, password: string) {
  return acceptCsrf(await betaRequest<{ user: BetaUser; csrf_token: string }>(
    "/api/v1/beta/auth/login",
    { method: "POST", body: { email, password } },
  ));
}

export async function getBetaSession() {
  return acceptCsrf(await betaRequest<{ user: BetaUser; csrf_token: string }>(
    "/api/v1/beta/auth/me",
  ));
}

export async function logoutBeta() {
  const result = await betaRequest<{ logged_out: boolean }>(
    "/api/v1/beta/auth/logout",
    { method: "POST", csrf: true },
  );
  csrfToken = "";
  return result;
}

export function getBetaDashboard(signal?: AbortSignal): Promise<BetaDashboardBundle> {
  return betaRequest<BetaDashboardBundle>("/api/v1/beta/dashboard", { signal });
}

export function getBetaUsers(): Promise<BetaUserList> {
  return betaRequest<BetaUserList>("/api/v1/beta/admin/users");
}

export function createBetaUser(email: string, password: string, betaDays = 30) {
  return betaRequest<{ user: BetaUser }>("/api/v1/beta/admin/users", {
    method: "POST", csrf: true,
    body: { email, password, role: "beta_user", beta_days: betaDays },
  });
}

export function setBetaUserEnabled(userId: string, enabled: boolean) {
  return betaRequest<{ user: BetaUser }>(
    `/api/v1/beta/admin/users/${encodeURIComponent(userId)}/status`,
    { method: "PATCH", csrf: true, body: { enabled } },
  );
}

export function extendBetaUser(userId: string, days = 30) {
  return betaRequest<{ user: BetaUser }>(
    `/api/v1/beta/admin/users/${encodeURIComponent(userId)}/extend`,
    { method: "POST", csrf: true, body: { days } },
  );
}
