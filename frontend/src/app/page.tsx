"use client";

import { useState } from "react";

import { analyzePortfolio } from "@/lib/api";

type AnalysisResult = {
  strategy: string;
  risk_level: string;
  target_weights: Record<string, number>;
  explanation: string;
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
  const [result, setResult] =
    useState<AnalysisResult | null>(null);
  const [loading, setLoading] =
    useState(false);
  const [error, setError] =
    useState("");

  async function handleAnalyze() {
    setLoading(true);
    setError("");

    try {
      const payload = await analyzePortfolio(
        samplePortfolio
      );

      setResult(payload);
    } catch {
      setError(
        "No fue posible conectar con la API."
      );
    } finally {
      setLoading(false);
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

          <div className="mt-8 flex gap-4">
            <button
              className="rounded bg-blue-600 px-5 py-3 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              disabled={loading}
              onClick={handleAnalyze}
            >
              {loading ? "Analyzing..." : "Analyze"}
            </button>

            <button className="rounded bg-green-600 px-5 py-3 font-medium text-white">
              Optimize
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

          {result && (
            <div className="mt-8 rounded-lg bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Analysis Result
              </h3>

              <p className="mt-3">
                Strategy:{" "}
                <strong>{result.strategy}</strong>
              </p>

              <p className="mt-2">
                Risk level:{" "}
                <strong>{result.risk_level}</strong>
              </p>

              <pre className="mt-4 overflow-auto rounded bg-slate-900 p-4 text-sm text-white">
                {JSON.stringify(
                  result.target_weights,
                  null,
                  2
                )}
              </pre>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}