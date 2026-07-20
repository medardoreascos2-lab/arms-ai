"use client";

import { useState } from "react";

import { PortfolioBarChart } from "@/components/PortfolioBarChart";
import {
  analyzePortfolio,
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

type RebalancingResult = {
  assets: string[];
  trades: Record<string, number>;
  turnover: number;
  overweight_assets: string[];
  underweight_assets: string[];
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
  | "simulate";

const samplePortfolio = {
  returns: {
    A: [0.01, 0.02, 0.03, 0.04],
    B: [0.02, 0.01, 0.03, 0.05],
    C: [0.03, 0.01, 0.02, 0.04],
  },
  volatilities: {
    A: 0.1,
    B: 0.2,
    C: 0.3,
  },
  expected_returns: {
    A: 0.08,
    B: 0.12,
    C: 0.18,
  },
  risk_free_rate: 0.02,
};

const sampleRebalancing = {
  current_weights: {
    A: 50,
    B: 30,
    C: 20,
  },
  target_weights: {
    A: 40,
    B: 40,
    C: 20,
  },
  tolerance: 0,
};

const sampleSimulation = {
  initial_value: 1000,
  mean_return: 0.01,
  volatility: 0.1,
  periods: 12,
  simulations: 500,
  seed: 42,
};

export default function Home() {
  const [analysis, setAnalysis] =
    useState<AnalysisResult | null>(null);

  const [optimization, setOptimization] =
    useState<OptimizationResult | null>(null);

  const [rebalancing, setRebalancing] =
    useState<RebalancingResult | null>(null);

  const [simulation, setSimulation] =
    useState<SimulationResult | null>(null);

  const [loading, setLoading] =
    useState<Action | null>(null);

  const [error, setError] =
    useState("");

  function clearResults() {
    setAnalysis(null);
    setOptimization(null);
    setRebalancing(null);
    setSimulation(null);
  }

  function handleError(caughtError: unknown) {
    setError(
      caughtError instanceof Error
        ? caughtError.message
        : "No fue posible conectar con la API."
    );
  }

  async function handleAnalyze() {
    setLoading("analyze");
    setError("");
    clearResults();

    try {
      const payload = await analyzePortfolio(
        samplePortfolio
      );

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
      const payload = await optimizePortfolio(
        samplePortfolio
      );

      setOptimization(payload);
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
      const payload = await rebalancePortfolio(
        sampleRebalancing
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
      const payload = await simulatePortfolio(
        sampleSimulation
      );

      setSimulation(payload);
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
            Frontend conectado a FastAPI.
          </p>

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
                  weights={analysis.target_weights}
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
                  {optimization.selected_strategy}
                </strong>
              </p>

              <div className="mt-6 grid gap-6 xl:grid-cols-3">
                <PortfolioBarChart
                  title="Minimum Variance"
                  weights={
                    optimization.minimum_variance
                      .weights
                  }
                />

                <PortfolioBarChart
                  title="Maximum Sharpe"
                  weights={
                    optimization.maximum_sharpe
                      .weights
                  }
                />

                <PortfolioBarChart
                  title="Risk Parity"
                  weights={
                    optimization.risk_parity
                      .weights
                  }
                />
              </div>
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
                    rebalancing.overweight_assets
                      .join(", ") || "None"
                  }
                />

                <MetricCard
                  label="Underweight"
                  value={
                    rebalancing.underweight_assets
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
                  label="Minimum"
                  value={`$${simulation.minimum_final_value.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="Maximum"
                  value={`$${simulation.maximum_final_value.toFixed(
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
