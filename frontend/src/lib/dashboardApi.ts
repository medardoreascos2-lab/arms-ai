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

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

const WEBSOCKET_URL =
  process.env.NEXT_PUBLIC_WEBSOCKET_URL ??
  API_URL.replace(
    /^http/,
    "ws"
  );

async function getJson(
  path: string
): Promise<JsonObject> {
  const response = await fetch(
    `${API_URL}${path}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
    }
  );

  if (!response.ok) {
    let detail = "";

    try {
      const payload =
        (await response.json()) as JsonObject;

      detail = String(
        payload.detail ??
          payload.error ??
          ""
      );
    } catch {
      detail = "";
    }

    throw new Error(
      detail ||
        `API Error: ${response.status}`
    );
  }

  return response.json();
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

export function getDashboardWebSocketUrl():
string {
  return (
    `${WEBSOCKET_URL}` +
    "/api/v2/dashboard/ws"
  );
}
