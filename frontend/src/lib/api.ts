const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

async function postJson(
  path: string,
  payload: unknown
) {
  const response = await fetch(
    `${API_URL}${path}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    const errorPayload =
      await response.json().catch(() => null);

    const message =
      errorPayload?.error?.message ??
      `API Error: ${response.status}`;

    throw new Error(message);
  }

  return response.json();
}

export function analyzePortfolio(
  payload: unknown
) {
  return postJson(
    "/portfolio/analyze",
    payload
  );
}

export function optimizePortfolio(
  payload: unknown
) {
  return postJson(
    "/portfolio/optimize",
    payload
  );
}

export function rebalancePortfolio(
  payload: unknown
) {
  return postJson(
    "/portfolio/rebalance",
    payload
  );
}

export function simulatePortfolio(
  payload: unknown
) {
  return postJson(
    "/portfolio/simulate",
    payload
  );
}

export function analyzePortfolioFromMarket(
  payload: unknown
) {
  return postJson(
    "/portfolio/from-market",
    payload
  );
}

export function generateEfficientFrontier(
  payload: unknown
) {
  return postJson(
    "/portfolio/efficient-frontier",
    payload
  );
}

export function backtestPortfolio(
  payload: unknown
) {
  return postJson(
    "/portfolio/backtest",
    payload
  );
}

export function calculateRiskAnalytics(
  payload: unknown
) {
  return postJson(
    "/portfolio/risk-analytics",
    payload
  );
}


export function calculateRiskAnalyticsFromMarket(
  payload: {
    symbols: string[];
    weights: Record<string, number>;
    period?: string;
    risk_free_rate?: number;
  }
) {
  return postJson(
    "/portfolio/risk-analytics-from-market",
    payload
  );
}

export function calculateBenchmarkAnalytics(
  payload: unknown
) {
  return postJson(
    "/portfolio/benchmark-analytics",
    payload
  );
}

export function calculateDrawdownAnalytics(
  payload: unknown
) {
  return postJson(
    "/portfolio/drawdown-analytics",
    payload
  );
}

export function calculateRollingAnalytics(
  payload: unknown
) {
  return postJson(
    "/portfolio/rolling-analytics",
    payload
  );
}

export function calculateCapmAnalytics(
  payload: unknown
) {
  return postJson(
    "/portfolio/capm-analytics",
    payload
  );
}

export function calculateFamaFrenchAnalytics(
  payload: unknown
) {
  return postJson(
    "/portfolio/fama-french-analytics",
    payload
  );
}

export function runStressTest(
  payload: unknown
) {
  return postJson(
    "/portfolio/stress-test",
    payload
  );
}

export function runScenarioAnalysis(
  payload: unknown
) {
  return postJson(
    "/portfolio/scenario-analysis",
    payload
  );
}

export function calculateRiskContribution(
  payload: unknown
) {
  return postJson(
    "/portfolio/risk-contribution",
    payload
  );
}
