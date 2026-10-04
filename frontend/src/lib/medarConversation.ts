import { decodeMedarResponse, degradedResponse, type ProductMedarResponse } from "./medarProduct.ts";

export type ConversationTurn = Readonly<{ id: string; prompt: string; response: ProductMedarResponse | null }>;
type FetchResponse = Pick<Response, "ok" | "json">;
type Fetcher = (input: string, init: RequestInit) => Promise<FetchResponse>;

export function canSend(enabled: boolean, pending: boolean, draft: string): boolean {
  return enabled && !pending && draft.trim().length > 0;
}

export function pendingTurn(id: string, prompt: string): ConversationTurn {
  return { id, prompt, response: null };
}

export function completeTurn(turns: readonly ConversationTurn[], id: string, response: ProductMedarResponse): readonly ConversationTurn[] {
  return turns.map((turn) => turn.id === id ? { ...turn, response } : turn);
}

export async function requestMedarResponse(
  requestId: string, conversationId: string, message: string, fetcher: Fetcher = fetch,
): Promise<ProductMedarResponse> {
  try {
    const result = await fetcher("/api/product/medar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: requestId, conversation_id: conversationId, message }),
      cache: "no-store",
    });
    return result.ok ? decodeMedarResponse(await result.json(), requestId)
      : degradedResponse(requestId, "MEDAR_UNAVAILABLE");
  } catch {
    return degradedResponse(requestId, "MEDAR_UNAVAILABLE");
  }
}
