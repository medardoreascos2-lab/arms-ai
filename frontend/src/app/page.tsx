"use client";

import { useState } from "react";

import {
  analyzePortfolio,
  optimizePortfolio,
} from "@/lib/api";
import { PortfolioBarChart } from "@/components/PortfolioBarChart";

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

export default function Home() {
  const [analysis, setAnalysis] =
    useState<AnalysisResult | null>(null);
  const [optimization, setOptimization] =
    useState<OptimizationResult | null>(null);
  const [loading, setLoading] =
    useState<"analyze" | "optimize" | null>(null);
  const [error, setError] =
    useState("");

  async function handleAnalyze() {
    setLoading("analyze");
    setError("");
    setOptimization(null);

    try {
      const payload = await analyzePortfolio(
        samplePortfolio
      );

      setAnalysis(payload);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "No fue posible conectar con la API."
      );
    } finally {
      setLoading(null);
    }
  }

  async function handleOptimize() {
    setLoading("optimize");
    setError("");
    setAnalysis(null);

    try {
      const payload = await optimizePortfolio(
        samplePortfolio
      );

      setOptimization(payload);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "No fue posible conectar con la API."
      );
    } finally {
      setLoading(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-100">
      <div className="mx-auto max-w-6xl p-10">
        <h1 className="text-5xl font-bold text-slate-900">
          ARMS AI
        </h1>

        <p className="mt-4 text-slate-600">
          Artificial Risk Management System
        </p>

        <div className="mt-10 rounded-xl bg-white p-8 shadow">
          <h2 className="text-2xl font-semibold">
            Portfolio Dashboard
          </h2>

          <p className="mt-3 text-slate-600">
            Frontend conectado a FastAPI.
          </p>

          <div className="mt-8 flex flex-wrap gap-4">
            <button
              className="rounded bg-blue-600 px-5 py-3 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              disabled={loading !== null}
              onClick={handleAnalyze}
            >
              {loading === "analyze"
                ? "Analyzing..."
                : "Analyze"}
            </button>

            <button
              className="rounded bg-green-600 px-5 py-3 font-medium text-white hover:bg-green-700 disabled:opacity-50"
              disabled={loading !== null}
              onClick={handleOptimize}
            >
              {loading === "optimize"
                ? "Optimizing..."
                : "Optimize"}
            </button>

            <button className="rounded bg-amber-500 px-5 py-3 font-medium text-white">
              Rebalance
            </button>

            <button className="rounded bg-purple-600 px-5 py-3 font-medium text-white">
              Simulate
            </button>
          </div>

          {error && (
            <p className="mt-6 text-red-600">
              {error}
            </p>
          )}

          {analysis && (
            <div className="mt-8 rounded-lg bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Analysis Result
              </h3>

              <p className="mt-3">
                Strategy:{" "}
                <strong>{analysis.strategy}</strong>
              </p>

              <p className="mt-2">
                Risk level:{" "}
                <strong>{analysis.risk_level}</strong>
              </p>

              <pre className="mt-4 overflow-auto rounded bg-slate-900 p-4 text-sm text-white">
                {JSON.stringify(
                  analysis.target_weights,
                  null,
                  2
                )}
              </pre>
            </div>
          )}

          {optimization && (
            <div className="mt-8 rounded-lg bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Optimization Result
              </h3>

              <p className="mt-3">
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
                    optimization.risk_parity.weights
                  }
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
