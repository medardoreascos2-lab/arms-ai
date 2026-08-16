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
  "http://localhost:8000";

const WEBSOCKET_URL =
  "ws://localhost:8000";

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


async function postJson(
  path: string,
  body: JsonObject
): Promise<JsonObject> {

  const response = await fetch(
    `${API_URL}${path}`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },

      body: JSON.stringify(
        body
      ),

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



export function switchAccount(
  account_name: string
):
Promise<JsonObject> {

  return postJson(
    "/api/v2/dashboard/account/switch",
    {
      account_name,
    }
  );

}


export function getDashboardWebSocketUrl():
string {
  return (
    `${WEBSOCKET_URL}` +
    "/api/v2/dashboard/ws"
  );
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



export function getAIDecision():
Promise<JsonObject> {

  return postJson(
    "/ai/decision",
    {
      weights: {
        trend: 0.3,
        risk: 0.3,
        performance: 0.4
      },

      metrics: {
        beta: 1.1,
        sharpe_ratio: 1.8,
        volatility: 0.15,
        drawdown: 0.05
      }
    }
  );

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

