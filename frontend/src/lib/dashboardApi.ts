export type JsonPrimitive =
  | string
  | number
  | boolean
  | null;

export type JsonValue =
  | JsonPrimitive
  | JsonValue[]
  | {
      [key: string]: JsonValue;
    };

export type JsonObject = {
  [key: string]: JsonValue;
};

// Public build configuration contains an origin only, never a credential.
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
let adminToken = "";

export function configurePaperCredential(token: string): void {
  if (token && (!/^[\x21-\x7e]+$/.test(token) || token.length > 2048)) {
    throw new Error("La credencial PAPER debe ser ASCII sin espacios.");
  }
  adminToken = token;
}

function apiOrigin(): string {
  const url = new URL(API_URL);
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/" ||
      !(url.protocol === "https:" || (url.protocol === "http:" &&
        ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)))) {
    throw new Error("Usa un origen HTTPS o localhost para PAPER.");
  }
  return url.origin;
}

export async function requestJson(path: string, body?: JsonObject, protectedCall = false,
                                  missingIsEmpty = false, signal?: AbortSignal): Promise<JsonObject> {
  if (!path.startsWith("/") || path.startsWith("//")) throw new Error("Ruta API inválida.");
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (protectedCall) {
    if (!adminToken) throw new Error("Introduce la credencial administrativa PAPER.");
    headers["X-ARMS-ADMIN-TOKEN"] = adminToken;
  }
  const response = await fetch(`${apiOrigin()}${path}`, {
    method: body === undefined ? "GET" : "POST", headers,
    body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store",
    redirect: "error", credentials: "omit", ...(signal ? { signal } : {}),
  });
  if (missingIsEmpty && response.status === 404) return { status: "UNAVAILABLE", reason: "Sin análisis de mercado disponible." };
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(String(payload.detail ?? payload.error ?? `API Error: ${response.status}`));
  }
  return response.json();
}

const getJson = (path: string) => requestJson(path);
const postJson = (path: string, body: JsonObject) => requestJson(path, body, true);

export function openDashboardWebSocket(): WebSocket {
  if (!adminToken) throw new Error("Introduce la credencial administrativa PAPER.");
  const encoded = btoa(adminToken).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return new WebSocket(getDashboardWebSocketUrl(), ["arms-dashboard-v1", `arms-admin.${encoded}`]);
}

export function getDashboardLive():
Promise<JsonObject> {
  return getJson(
    "/api/v2/dashboard/live"
  );
}

export function getDashboardWidgets():
Promise<JsonObject> {
  return getJson(
    "/api/v2/dashboard/widgets"
  );
}


export function getRiskDashboard():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/risk"
  );

}



export function getAccountProfile():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/account"
  );

}



export async function switchAccount(
  profile_name: string,
  target_account_id?: string
): Promise<JsonObject> {
  const context = await getJson(
    "/api/v2/dashboard/account-manager/switch-context"
  );
  if (typeof context.account_id !== "string" || !context.account_id) {
    throw new Error("No se pudo verificar la cuenta activa.");
  }
  let account_id = target_account_id;
  if (!account_id && Array.isArray(context.accounts)) {
    const matches = context.accounts.filter(
      (row): row is JsonObject =>
        row !== null && typeof row === "object" && !Array.isArray(row) &&
        row.profile_name === profile_name
    );
    if (matches.length !== 1 || typeof matches[0].account_id !== "string") {
      throw new Error("Selecciona una identidad de cuenta inequívoca.");
    }
    account_id = matches[0].account_id as string;
  }
  // Containment-only servers can still acknowledge the current account.
  account_id ??= context.account_id;
  return postJson(
    "/api/v2/dashboard/account-manager/switch",
    {
      account_id,
      profile_name,
    }
  );
}


export function getDashboardWebSocketUrl(): string {
  return apiOrigin().replace(/^http/, "ws") + "/api/v2/dashboard/ws";
}

export function getStrategyRanking():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/strategy-ranking"
  );

}



export function getBacktestingDashboard():
Promise<JsonObject> {

  return getJson(
    "/api/v2/backtesting/dashboard"
  );

}



export function getTradeSetup():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/trade-setup"
  );

}



export function getAIDecision(): Promise<JsonObject> {
  return getIntelligenceDecision();
}

export function getExecutionApproval():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/execution-approval"
  );

}



export function getExecutionSimulator():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/execution-simulator"
  );

}



export function getExecutionManager():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/execution-manager"
  );

}



export function getPerformanceIntelligence():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/performance-intelligence"
  );

}



export function getAILearning():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/ai-learning"
  );

}



export function getAIPattern():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/ai-pattern"
  );

}



export function getTradingMemory():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/trading-memory"
  );

}



export function getAIDecisionMemory():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/ai-decision-memory"
  );

}



export function getConfidenceFusion():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/confidence-fusion"
  );

}



export function getIntelligenceDecision():
Promise<JsonObject> {

  return getJson(
    "/api/v2/dashboard/intelligence-decision"
  );

}



export function getIntelligenceDecisionV3():
Promise<JsonObject> {

  return getJson(
    "/api/v3/dashboard/intelligence-decision"
  );

}



export function getExecutionPipeline():
Promise<JsonObject> {

  return getJson(
    "/api/v3/dashboard/execution-pipeline"
  );

}




export function getLearningSummary():
Promise<JsonObject> {

  return getJson(
    "/api/v2/learning/summary"
  );

}


export function runtimeKey(value: JsonObject): string {
  if (typeof value.account_id !== "string" || typeof value.profile_name !== "string" ||
      typeof value.runtime_generation !== "number") throw new Error("Runtime PAPER no verificable.");
  return JSON.stringify([value.account_id, value.profile_name, value.runtime_generation]);
}

export async function getDashboardBundle(): Promise<JsonObject> {
  const context = await getJson("/api/v2/dashboard/account-manager/switch-context");
  const key = runtimeKey(context);
  // Legacy ranking/setup/approval/fusion routes evaluate demonstration inputs.
  // Keep their APIs for compatibility, but never present them as PAPER state.
  const readers = {
    live: getDashboardLive, widgets: getDashboardWidgets,
    backtesting: getBacktestingDashboard, plan: getExecutionManager,
    performance: getPerformanceIntelligence, pattern: getAIPattern, learning: getAILearning,
    memory: getTradingMemory, pipeline: getExecutionPipeline,
    risk: getRiskDashboard, account: getAccountProfile,
    strategy: () => getJson("/api/v2/strategy/intelligence"),
    market: () => requestJson("/market/latest-analysis?symbol=" +
      encodeURIComponent(process.env.NEXT_PUBLIC_PAPER_SYMBOL ?? "MNQ") + "&timeframe=" +
      encodeURIComponent(process.env.NEXT_PUBLIC_PAPER_TIMEFRAME ?? "5m"), undefined, false, true),
  };
  const entries = await Promise.all(Object.entries(readers).map(async ([name, read]) => [name, await read()]));
  const result: JsonObject = Object.fromEntries(entries);
  const after = await getJson("/api/v2/dashboard/account-manager/switch-context");
  const live = result.live as JsonObject;
  if (key !== runtimeKey(after) || key !== runtimeKey(live.runtime as JsonObject) || live.execution_mode !== "PAPER") {
    throw new Error("El runtime PAPER cambió; reconectando.");
  }
  return { ...result, context };
}
