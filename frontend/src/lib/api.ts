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

export function calculatePerformanceAttribution(
  payload: unknown
) {
  return postJson(
    "/portfolio/performance-attribution",
    payload
  );
}


export type AiCopilotPayload = {
  question: string;
  weights: Record<string, number>;
  metrics: Record<string, number>;
};

export type AiCopilotDecision = {
  score: number;
  risk_level: string;
  recommendations: string[];
  alerts: string[];
  summary?: string;
};

export type AiCopilotResult = {
  provider: string;
  model: string;
  content: string;
  decision: AiCopilotDecision;
};

export function askAiCopilot(
  payload: AiCopilotPayload
): Promise<AiCopilotResult> {
  return postJson(
    "/ai/copilot",
    payload
  );
}


export type TradingCandlePayload = {
  symbol: string;
  timeframe: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  timestamp: string;
};

export type TradingContextPayload = {
  symbol: string;
  timeframe: string;
  candles: TradingCandlePayload[];
  account_balance: number;
  risk_percent: number;
  point_value: number;
  reward_risk_ratio: number;
};

export type TradingContextResult = {
  symbol: string;
  timeframe: string;
  current_price: number;
  trend: string;

  indicators: {
    ema: number;
    ema_period: number | null;
    rsi: number;
    rsi_status: string | null;
    atr: number;
    atr_status: string | null;
  };

  market_structure: {
    direction: string;
    high_type: string;
    low_type: string;
  };

  smart_money: {
    bos: {
      detected: boolean;
      direction: string;
    };
    choch: {
      detected: boolean;
      direction: string;
    };
    liquidity: {
      detected: boolean;
      direction: string;
      level: number | null;
      equal_highs: boolean;
      equal_lows: boolean;
    };
  };

  decision: {
    score: number;
    grade: string;
    action: string;
    direction: string;
    approved: boolean;
    confirmations: string[];
    warnings: string[];
  };

  probability: {
    value: number;
    confidence: string;
    approved: boolean;
    recommendation: string;
    positive_factors: string[];
    negative_factors: string[];
  };

  risk: {
    approved: boolean;
    risk_amount: number;
    stop_distance: number;
    take_profit_distance: number;
    contracts: number;
  };

  trade: {
    entry_price: number;
    stop_loss: number;
    take_profit: number;
  };
};

export function analyzeTradingContext(
  payload: TradingContextPayload
): Promise<TradingContextResult> {
  return postJson(
    "/ai/trading-context",
    payload
  );
}


export function getLatestMarketAnalysis(
  symbol: string,
  timeframe: string
): Promise<TradingContextResult> {
  const params = new URLSearchParams({
    symbol,
    timeframe,
  });

  return fetch(
    `${API_URL}/market/latest-analysis?${params.toString()}`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    }
  ).then(async (response) => {
    if (!response.ok) {
      const errorPayload =
        await response.json().catch(() => null);

      const detail =
        errorPayload?.detail
        ?? "No fue posible obtener el último análisis.";

      throw new Error(detail);
    }

    return response.json();
  });
}
