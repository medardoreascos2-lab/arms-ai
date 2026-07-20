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
