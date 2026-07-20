"use client";

import { useState } from "react";

import { BenchmarkComparisonChart } from "@/components/BenchmarkComparisonChart";
import { EfficientFrontierChart } from "@/components/EfficientFrontierChart";
import { EquityCurveChart } from "@/components/EquityCurveChart";
import { PortfolioBarChart } from "@/components/PortfolioBarChart";
import {
  PortfolioFormValues,
  PortfolioInputs,
} from "@/components/PortfolioInputs";
import {
  analyzePortfolioFromMarket,
  backtestPortfolio,
  calculateBenchmarkAnalytics,
  calculateRiskAnalyticsFromMarket,
  generateEfficientFrontier,
  optimizePortfolio,
  rebalancePortfolio,
  simulatePortfolio,
} from "@/lib/api";

type AnalysisResult = {
  strategy: string;
  risk_level: string;
  target_weights: Record<string, number>;
  explanation: string;
};

type OptimizationResult = {
  selected_strategy: string;
  minimum_variance: {
    weights: Record<string, number>;
    portfolio_volatility: number;
  };
  maximum_sharpe: {
    weights: Record<string, number>;
    sharpe_ratio: number;
  };
  risk_parity: {
    weights: Record<string, number>;
    risk_contributions: Record<string, number>;
  };
};

type FrontierPoint = {
  expected_return: number;
  volatility: number;
  weights: Record<string, number>;
};

type RebalancingResult = {
  assets: string[];
  trades: Record<string, number>;
  turnover: number;
  overweight_assets: string[];
  underweight_assets: string[];
};

type BenchmarkAnalyticsResult = {
  beta: number;
  alpha: number;
  tracking_error: number;
  information_ratio: number;
  portfolio_curve: number[];
  benchmark_curve: number[];
};

type RiskAnalyticsResult = {
  annualized_return: number;
  annualized_volatility: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  maximum_drawdown: number;
  calmar_ratio: number;
  value_at_risk_95: number;
  conditional_value_at_risk_95: number;
};

type BacktestResult = {
  initial_value: number;
  final_value: number;
  equity_curve: number[];
  total_return: number;
  annualized_return: number;
  annualized_volatility: number;
  sharpe_ratio: number;
  maximum_drawdown: number;
};

type SimulationResult = {
  initial_value: number;
  periods: number;
  simulations: number;
  mean_final_value: number;
  median_final_value: number;
  minimum_final_value: number;
  maximum_final_value: number;
  percentile_5: number;
  percentile_95: number;
  probability_of_loss: number;
};

type Action =
  | "analyze"
  | "optimize"
  | "rebalance"
  | "simulate"
  | "backtest"
  | "risk"
  | "benchmark";

const initialFormValues: PortfolioFormValues = {
  symbols: "AAPL, MSFT, NVDA",
  volatilities: "0.20, 0.18, 0.35",
  expectedReturns: "0.12, 0.10, 0.18",
  currentWeights: "40, 35, 25",
  riskFreeRate: 0.02,
};

export default function Home() {
  const [formValues, setFormValues] =
    useState<PortfolioFormValues>(
      initialFormValues
    );

  const [analysis, setAnalysis] =
    useState<AnalysisResult | null>(null);

  const [optimization, setOptimization] =
    useState<OptimizationResult | null>(null);

  const [frontier, setFrontier] =
    useState<FrontierPoint[]>([]);

  const [rebalancing, setRebalancing] =
    useState<RebalancingResult | null>(null);

  const [simulation, setSimulation] =
    useState<SimulationResult | null>(null);

  const [backtest, setBacktest] =
    useState<BacktestResult | null>(null);

  const [riskAnalytics, setRiskAnalytics] =
    useState<RiskAnalyticsResult | null>(null);

  const [benchmarkAnalytics, setBenchmarkAnalytics] =
    useState<BenchmarkAnalyticsResult | null>(null);

  const [loading, setLoading] =
    useState<Action | null>(null);

  const [error, setError] =
    useState("");

  function clearResults() {
    setAnalysis(null);
    setOptimization(null);
    setFrontier([]);
    setRebalancing(null);
    setSimulation(null);
    setBacktest(null);
    setRiskAnalytics(null);
    setBenchmarkAnalytics(null);
  }

  function handleError(
    caughtError: unknown
  ) {
    setError(
      caughtError instanceof Error
        ? caughtError.message
        : "No fue posible completar la operación."
    );
  }

  function buildPortfolioPayload() {
    const symbols = parseSymbols(
      formValues.symbols
    );

    const volatilities = parseNumbers(
      formValues.volatilities
    );

    const expectedReturns = parseNumbers(
      formValues.expectedReturns
    );

    validateLengths(
      symbols,
      volatilities,
      expectedReturns
    );

    return {
      returns: buildReturnSeries(symbols),
      volatilities: toRecord(
        symbols,
        volatilities
      ),
      expected_returns: toRecord(
        symbols,
        expectedReturns
      ),
      risk_free_rate:
        formValues.riskFreeRate,
    };
  }

  function buildRebalancingPayload() {
    const symbols = parseSymbols(
      formValues.symbols
    );

    const currentWeights = parseNumbers(
      formValues.currentWeights
    );

    if (
      symbols.length
      !== currentWeights.length
    ) {
      throw new Error(
        "Assets y current weights deben tener la misma cantidad de valores."
      );
    }

    const equalWeight =
      100 / symbols.length;

    const targetWeights =
      Object.fromEntries(
        symbols.map(
          (symbol) => [
            symbol,
            Number(
              equalWeight.toFixed(6)
            ),
          ]
        )
      );

    return {
      current_weights: toRecord(
        symbols,
        currentWeights
      ),
      target_weights: targetWeights,
      tolerance: 0,
    };
  }

  async function handleAnalyze() {
    setLoading("analyze");
    setError("");
    clearResults();

    try {
      const symbols = parseSymbols(
        formValues.symbols
      );

      const payload =
        await analyzePortfolioFromMarket({
          symbols,
          period: "1y",
          risk_free_rate:
            formValues.riskFreeRate,
        });

      setAnalysis(payload);
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleOptimize() {
    setLoading("optimize");
    setError("");
    clearResults();

    try {
      const portfolioPayload =
        buildPortfolioPayload();

      const [
        optimizationPayload,
        frontierPayload,
      ] = await Promise.all([
        optimizePortfolio(
          portfolioPayload
        ),
        generateEfficientFrontier(
          portfolioPayload
        ),
      ]);

      setOptimization(
        optimizationPayload
      );
      setFrontier(
        frontierPayload
      );
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleRebalance() {
    setLoading("rebalance");
    setError("");
    clearResults();

    try {
      const payload =
        await rebalancePortfolio(
          buildRebalancingPayload()
        );

      setRebalancing(payload);
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleSimulate() {
    setLoading("simulate");
    setError("");
    clearResults();

    try {
      const payload =
        await simulatePortfolio({
          initial_value: 1000,
          mean_return: 0.01,
          volatility: 0.1,
          periods: 12,
          simulations: 500,
          seed: 42,
        });

      setSimulation(payload);
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleBacktest() {
    setLoading("backtest");
    setError("");
    clearResults();

    try {
      const symbols = parseSymbols(
        formValues.symbols
      );

      const weights = parseNumbers(
        formValues.currentWeights
      );

      if (
        symbols.length !== weights.length
      ) {
        throw new Error(
          "Assets y current weights deben tener la misma cantidad de valores."
        );
      }

      const normalizedWeights =
        weights.map(
          (weight) => weight / 100
        );

      const payload =
        await backtestPortfolio({
          symbols,
          weights: toRecord(
            symbols,
            normalizedWeights
          ),
          period: "1y",
          initial_value: 1000,
          risk_free_rate:
            formValues.riskFreeRate,
        });

      setBacktest(payload);
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleBenchmarkAnalytics() {
    setLoading("benchmark");
    setError("");
    clearResults();

    try {
      const symbols = parseSymbols(
        formValues.symbols
      );

      const weights = parseNumbers(
        formValues.currentWeights
      );

      if (
        symbols.length !== weights.length
      ) {
        throw new Error(
          "Assets y current weights deben tener la misma cantidad de valores."
        );
      }

      const normalizedWeights =
        weights.map(
          (weight) => weight / 100
        );

      const weightSum =
        normalizedWeights.reduce(
          (total, weight) =>
            total + weight,
          0
        );

      if (
        Math.abs(
          weightSum - 1
        ) > 0.000001
      ) {
        throw new Error(
          "Current weights debe sumar 100."
        );
      }

      const payload =
        await calculateBenchmarkAnalytics({
          symbols,
          weights: toRecord(
            symbols,
            normalizedWeights
          ),
          benchmark: "SPY",
          period: "1y",
          risk_free_rate:
            formValues.riskFreeRate,
        });

      setBenchmarkAnalytics(
        payload
      );
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleRiskAnalytics() {
    setLoading("risk");
    setError("");
    clearResults();

    try {
      const symbols = parseSymbols(
        formValues.symbols
      );

      const weights = parseNumbers(
        formValues.currentWeights
      );

      if (
        symbols.length !== weights.length
      ) {
        throw new Error(
          "Assets y current weights deben tener la misma cantidad de valores."
        );
      }

      const normalizedWeights =
        weights.map(
          (weight) => weight / 100
        );

      const weightSum =
        normalizedWeights.reduce(
          (total, weight) =>
            total + weight,
          0
        );

      if (
        Math.abs(
          weightSum - 1
        ) > 0.000001
      ) {
        throw new Error(
          "Current weights debe sumar 100."
        );
      }

      const payload =
        await calculateRiskAnalyticsFromMarket({
          symbols,
          weights: toRecord(
            symbols,
            normalizedWeights
          ),
          period: "1y",
          risk_free_rate:
            formValues.riskFreeRate,
        });

      setRiskAnalytics(payload);
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }


  return (
    <main className="min-h-screen bg-slate-100">
      <div className="mx-auto max-w-7xl p-6 md:p-10">
        <h1 className="text-5xl font-bold text-slate-900">
          ARMS AI
        </h1>

        <p className="mt-4 text-slate-600">
          Artificial Risk Management System
        </p>

        <section className="mt-10 rounded-xl bg-white p-6 shadow md:p-8">
          <h2 className="text-2xl font-semibold text-slate-900">
            Portfolio Dashboard
          </h2>

          <p className="mt-3 text-slate-600">
            Configura el portafolio y ejecuta el análisis.
          </p>

          <PortfolioInputs
            values={formValues}
            onChange={setFormValues}
          />

          <div className="mt-8 flex flex-wrap gap-4">
            <ActionButton
              label="Analyze"
              loadingLabel="Analyzing..."
              active={loading === "analyze"}
              disabled={loading !== null}
              className="bg-blue-600 hover:bg-blue-700"
              onClick={handleAnalyze}
            />

            <ActionButton
              label="Optimize"
              loadingLabel="Optimizing..."
              active={loading === "optimize"}
              disabled={loading !== null}
              className="bg-green-600 hover:bg-green-700"
              onClick={handleOptimize}
            />

            <ActionButton
              label="Rebalance"
              loadingLabel="Rebalancing..."
              active={loading === "rebalance"}
              disabled={loading !== null}
              className="bg-amber-500 hover:bg-amber-600"
              onClick={handleRebalance}
            />

            <ActionButton
              label="Simulate"
              loadingLabel="Simulating..."
              active={loading === "simulate"}
              disabled={loading !== null}
              className="bg-purple-600 hover:bg-purple-700"
              onClick={handleSimulate}
            />

            <ActionButton
              label="Backtest"
              loadingLabel="Backtesting..."
              active={loading === "backtest"}
              disabled={loading !== null}
              className="bg-slate-800 hover:bg-slate-900"
              onClick={handleBacktest}
            />

            <ActionButton
              label="Risk Analytics"
              loadingLabel="Calculating..."
              active={loading === "risk"}
              disabled={loading !== null}
              className="bg-rose-600 hover:bg-rose-700"
              onClick={handleRiskAnalytics}
            />

            <ActionButton
              label="Benchmark"
              loadingLabel="Comparing..."
              active={loading === "benchmark"}
              disabled={loading !== null}
              className="bg-cyan-600 hover:bg-cyan-700"
              onClick={handleBenchmarkAnalytics}
            />
          </div>

          {error && (
            <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
              {error}
            </div>
          )}

          {analysis && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Analysis Result
              </h3>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <MetricCard
                  label="Strategy"
                  value={analysis.strategy}
                />

                <MetricCard
                  label="Risk level"
                  value={analysis.risk_level}
                />
              </div>

              <div className="mt-6">
                <PortfolioBarChart
                  title="Target Weights"
                  weights={
                    analysis.target_weights
                  }
                />
              </div>
            </section>
          )}

          {optimization && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Optimization Result
              </h3>

              <p className="mt-3 text-slate-700">
                Selected strategy:{" "}
                <strong>
                  {
                    optimization
                      .selected_strategy
                  }
                </strong>
              </p>

              <div className="mt-6 grid gap-6 xl:grid-cols-3">
                <PortfolioBarChart
                  title="Minimum Variance"
                  weights={
                    optimization
                      .minimum_variance
                      .weights
                  }
                />

                <PortfolioBarChart
                  title="Maximum Sharpe"
                  weights={
                    optimization
                      .maximum_sharpe
                      .weights
                  }
                />

                <PortfolioBarChart
                  title="Risk Parity"
                  weights={
                    optimization
                      .risk_parity
                      .weights
                  }
                />
              </div>

              {frontier.length > 0 && (
                <div className="mt-6">
                  <EfficientFrontierChart
                    points={frontier}
                  />
                </div>
              )}
            </section>
          )}

          {rebalancing && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Rebalancing Result
              </h3>

              <div className="mt-5 grid gap-4 md:grid-cols-3">
                <MetricCard
                  label="Turnover"
                  value={`${rebalancing.turnover.toFixed(
                    2
                  )}%`}
                />

                <MetricCard
                  label="Overweight"
                  value={
                    rebalancing
                      .overweight_assets
                      .join(", ") || "None"
                  }
                />

                <MetricCard
                  label="Underweight"
                  value={
                    rebalancing
                      .underweight_assets
                      .join(", ") || "None"
                  }
                />
              </div>

              <div className="mt-6">
                <PortfolioBarChart
                  title="Required Trades"
                  weights={rebalancing.trades}
                />
              </div>
            </section>
          )}

          {benchmarkAnalytics && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Portfolio vs Benchmark
              </h3>

              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Beta"
                  value={benchmarkAnalytics.beta.toFixed(
                    2
                  )}
                />

                <MetricCard
                  label="Alpha"
                  value={`${(
                    benchmarkAnalytics.alpha
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Tracking error"
                  value={`${(
                    benchmarkAnalytics.tracking_error
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Information ratio"
                  value={benchmarkAnalytics.information_ratio.toFixed(
                    2
                  )}
                />
              </div>

              <div className="mt-6">
                <BenchmarkComparisonChart
                  portfolioCurve={
                    benchmarkAnalytics.portfolio_curve
                  }
                  benchmarkCurve={
                    benchmarkAnalytics.benchmark_curve
                  }
                  benchmarkLabel="SPY"
                />
              </div>
            </section>
          )}

          {riskAnalytics && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Risk Analytics
              </h3>

              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Annualized return"
                  value={`${(
                    riskAnalytics.annualized_return
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Annualized volatility"
                  value={`${(
                    riskAnalytics.annualized_volatility
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Sharpe ratio"
                  value={riskAnalytics.sharpe_ratio.toFixed(
                    2
                  )}
                />

                <MetricCard
                  label="Sortino ratio"
                  value={riskAnalytics.sortino_ratio.toFixed(
                    2
                  )}
                />

                <MetricCard
                  label="Calmar ratio"
                  value={riskAnalytics.calmar_ratio.toFixed(
                    2
                  )}
                />

                <MetricCard
                  label="Maximum drawdown"
                  value={`${(
                    riskAnalytics.maximum_drawdown
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="VaR 95%"
                  value={`${(
                    riskAnalytics.value_at_risk_95
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="CVaR 95%"
                  value={`${(
                    riskAnalytics
                      .conditional_value_at_risk_95
                    * 100
                  ).toFixed(2)}%`}
                />
              </div>
            </section>
          )}

          {backtest && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Portfolio Backtest
              </h3>

              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Initial value"
                  value={`$${backtest.initial_value.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="Final value"
                  value={`$${backtest.final_value.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="Total return"
                  value={`${(
                    backtest.total_return * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Annualized return"
                  value={`${(
                    backtest.annualized_return
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Annualized volatility"
                  value={`${(
                    backtest.annualized_volatility
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Sharpe ratio"
                  value={backtest.sharpe_ratio.toFixed(
                    2
                  )}
                />

                <MetricCard
                  label="Maximum drawdown"
                  value={`${(
                    backtest.maximum_drawdown
                    * 100
                  ).toFixed(2)}%`}
                />
              </div>

              <div className="mt-6">
                <EquityCurveChart
                  values={
                    backtest.equity_curve
                  }
                />
              </div>
            </section>
          )}

          {simulation && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Monte Carlo Simulation
              </h3>

              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Mean final value"
                  value={`$${simulation.mean_final_value.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="Median final value"
                  value={`$${simulation.median_final_value.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="5th percentile"
                  value={`$${simulation.percentile_5.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="95th percentile"
                  value={`$${simulation.percentile_95.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="Probability of loss"
                  value={`${simulation.probability_of_loss.toFixed(
                    2
                  )}%`}
                />

                <MetricCard
                  label="Simulations"
                  value={simulation.simulations}
                />
              </div>
            </section>
          )}
        </section>
      </div>
    </main>
  );
}

function parseSymbols(
  value: string
) {
  const symbols = value
    .split(",")
    .map(
      (symbol) =>
        symbol.trim().toUpperCase()
    )
    .filter(Boolean);

  if (!symbols.length) {
    throw new Error(
      "Debes introducir al menos un activo."
    );
  }

  return symbols;
}

function parseNumbers(
  value: string
) {
  const numbers = value
    .split(",")
    .map(
      (item) =>
        Number(item.trim())
    );

  if (
    numbers.some(
      (number) =>
        !Number.isFinite(number)
    )
  ) {
    throw new Error(
      "Los valores numéricos contienen datos inválidos."
    );
  }

  return numbers;
}

function validateLengths(
  symbols: string[],
  volatilities: number[],
  expectedReturns: number[]
) {
  if (
    symbols.length
      !== volatilities.length
    || symbols.length
      !== expectedReturns.length
  ) {
    throw new Error(
      "Assets, volatilities y expected returns deben tener la misma cantidad de valores."
    );
  }
}

function toRecord(
  symbols: string[],
  values: number[]
) {
  return Object.fromEntries(
    symbols.map(
      (symbol, index) => [
        symbol,
        values[index],
      ]
    )
  );
}

function buildReturnSeries(
  symbols: string[]
) {
  const patterns = [
    [0.01, 0.02, 0.03, 0.04],
    [0.02, 0.01, 0.03, 0.05],
    [0.03, 0.01, 0.02, 0.04],
  ];

  return Object.fromEntries(
    symbols.map(
      (symbol, index) => [
        symbol,
        patterns[
          index % patterns.length
        ],
      ]
    )
  );
}

function ActionButton({
  label,
  loadingLabel,
  active,
  disabled,
  className,
  onClick,
}: {
  label: string;
  loadingLabel: string;
  active: boolean;
  disabled: boolean;
  className: string;
  onClick: () => void;
}) {
  return (
    <button
      className={`rounded px-5 py-3 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
      disabled={disabled}
      onClick={onClick}
    >
      {active ? loadingLabel : label}
    </button>
  );
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-sm text-slate-500">
        {label}
      </p>

      <p className="mt-2 text-lg font-semibold text-slate-900">
        {value}
      </p>
    </div>
  );
}
