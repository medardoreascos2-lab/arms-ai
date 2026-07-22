"use client";

import { useState } from "react";

import { BenchmarkComparisonChart } from "@/components/BenchmarkComparisonChart";
import { DrawdownChart } from "@/components/DrawdownChart";
import { EfficientFrontierChart } from "@/components/EfficientFrontierChart";
import { EquityCurveChart } from "@/components/EquityCurveChart";
import { PerformanceAttributionChart } from "@/components/PerformanceAttributionChart";
import { PortfolioBarChart } from "@/components/PortfolioBarChart";
import { RiskContributionChart } from "@/components/RiskContributionChart";
import { RollingAnalyticsChart } from "@/components/RollingAnalyticsChart";
import { ScenarioImpactChart } from "@/components/ScenarioImpactChart";
import { StressImpactChart } from "@/components/StressImpactChart";
import {
  PortfolioFormValues,
  PortfolioInputs,
} from "@/components/PortfolioInputs";
import {
  analyzePortfolioFromMarket,
  analyzeTradingContext,
  askAiCopilot,
  backtestPortfolio,
  calculateBenchmarkAnalytics,
  calculateCapmAnalytics,
  calculateDrawdownAnalytics,
  calculateFamaFrenchAnalytics,
  calculatePerformanceAttribution,
  calculateRiskAnalyticsFromMarket,
  calculateRiskContribution,
  calculateRollingAnalytics,
  generateEfficientFrontier,
  getLatestMarketAnalysis,
  optimizePortfolio,
  rebalancePortfolio,
  runScenarioAnalysis,
  runStressTest,
  simulatePortfolio,
  type AiCopilotResult,
  type TradingContextResult,
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

type PerformanceAttributionResult = {
  portfolio_return: number;
  benchmark_return: number;
  active_return: number;
  allocation_effect: number;
  selection_effect: number;
  interaction_effect: number;
  allocation_by_asset: Record<string, number>;
  selection_by_asset: Record<string, number>;
  interaction_by_asset: Record<string, number>;
  asset_contributions: Record<string, number>;
  best_asset: string;
  worst_asset: string;
};

type RiskContributionResult = {
  portfolio_volatility: number;
  marginal_contributions: Record<string, number>;
  absolute_contributions: Record<string, number>;
  percentage_contributions: Record<string, number>;
  highest_risk_asset: string;
  lowest_risk_asset: string;
};

type ScenarioAnalysisResult = {
  scenario: string;
  initial_value: number;
  final_value: number;
  absolute_impact: number;
  percentage_impact: number;
  shocks: Record<string, number>;
  asset_impacts: Record<string, number>;
};

type StressTestingResult = {
  initial_value: number;
  final_value: number;
  absolute_loss: number;
  percentage_loss: number;
  asset_impacts: Record<string, number>;
  worst_asset: string;
  best_asset: string;
};

type FamaFrenchAnalyticsResult = {
  alpha: number;
  beta_market: number;
  beta_smb: number;
  beta_hml: number;
  r_squared: number;
  expected_return: number;
};

type CapmAnalyticsResult = {
  beta: number;
  jensens_alpha: number;
  capm_expected_return: number;
  market_risk_premium: number;
  treynor_ratio: number;
  modigliani_m2: number;
};

type RollingAnalyticsResult = {
  rolling_volatility: number[];
  rolling_sharpe: number[];
  rolling_drawdown: number[];
};

type DrawdownAnalyticsResult = {
  equity_curve: number[];
  drawdown_curve: number[];
  maximum_drawdown: number;
  maximum_drawdown_duration: number;
  peak_index: number;
  trough_index: number;
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
  | "copilot"
  | "trading-context"
  | "latest-analysis"
  | "optimize"
  | "rebalance"
  | "simulate"
  | "backtest"
  | "risk"
  | "benchmark"
  | "drawdown"
  | "rolling"
  | "capm"
  | "fama-french"
  | "stress"
  | "scenario"
  | "risk-contribution"
  | "attribution";

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

  const [drawdownAnalytics, setDrawdownAnalytics] =
    useState<DrawdownAnalyticsResult | null>(null);

  const [rollingAnalytics, setRollingAnalytics] =
    useState<RollingAnalyticsResult | null>(null);

  const [capmAnalytics, setCapmAnalytics] =
    useState<CapmAnalyticsResult | null>(null);

  const [famaFrenchAnalytics, setFamaFrenchAnalytics] =
    useState<FamaFrenchAnalyticsResult | null>(null);

  const [stressTesting, setStressTesting] =
    useState<StressTestingResult | null>(null);

  const [scenarioAnalysis, setScenarioAnalysis] =
    useState<ScenarioAnalysisResult | null>(null);

  const [riskContribution, setRiskContribution] =
    useState<RiskContributionResult | null>(null);

  const [performanceAttribution, setPerformanceAttribution] =
    useState<PerformanceAttributionResult | null>(null);

  const [copilotQuestion, setCopilotQuestion] =
    useState("");

  const [copilotResult, setCopilotResult] =
    useState<AiCopilotResult | null>(null);

  const [tradingContext, setTradingContext] =
    useState<TradingContextResult | null>(null);

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
    setDrawdownAnalytics(null);
    setRollingAnalytics(null);
    setCapmAnalytics(null);
    setFamaFrenchAnalytics(null);
    setStressTesting(null);
    setScenarioAnalysis(null);
    setRiskContribution(null);
    setPerformanceAttribution(null);
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

  async function handlePerformanceAttribution() {
    setLoading("attribution");
    setError("");
    clearResults();

    try {
      const symbols = parseSymbols(
        formValues.symbols
      );

      const portfolioWeights = parseNumbers(
        formValues.currentWeights
      );

      const benchmarkWeights = parseNumbers(
        formValues.currentWeights
      );

      const portfolioReturns = parseNumbers(
        formValues.expectedReturns
      );

      const benchmarkReturns = parseNumbers(
        formValues.volatilities
      );

      const lengths = [
        portfolioWeights.length,
        benchmarkWeights.length,
        portfolioReturns.length,
        benchmarkReturns.length,
      ];

      if (
        lengths.some(
          (length) => length !== symbols.length
        )
      ) {
        throw new Error(
          "Assets, weights y returns deben tener la misma cantidad de valores."
        );
      }

      const normalizedPortfolioWeights =
        portfolioWeights.map(
          (weight) => weight / 100
        );

      const normalizedBenchmarkWeights =
        benchmarkWeights.map(
          (weight) => weight / 100
        );

      const portfolioWeightSum =
        normalizedPortfolioWeights.reduce(
          (total, weight) =>
            total + weight,
          0
        );

      const benchmarkWeightSum =
        normalizedBenchmarkWeights.reduce(
          (total, weight) =>
            total + weight,
          0
        );

      if (
        Math.abs(
          portfolioWeightSum - 1
        ) > 0.000001
        || Math.abs(
          benchmarkWeightSum - 1
        ) > 0.000001
      ) {
        throw new Error(
          "Current weights y target weights deben sumar 100."
        );
      }

      const payload =
        await calculatePerformanceAttribution({
          portfolio_weights: toRecord(
            symbols,
            normalizedPortfolioWeights
          ),
          benchmark_weights: toRecord(
            symbols,
            normalizedBenchmarkWeights
          ),
          portfolio_returns: toRecord(
            symbols,
            portfolioReturns.map(
              (value) => value / 100
            )
          ),
          benchmark_returns: toRecord(
            symbols,
            benchmarkReturns.map(
              (value) => value / 100
            )
          ),
        });

      setPerformanceAttribution(
        payload
      );
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleRiskContribution() {
    setLoading("risk-contribution");
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
        await calculateRiskContribution({
          symbols,
          weights: toRecord(
            symbols,
            normalizedWeights
          ),
          period: "1y",
        });

      setRiskContribution(
        payload
      );
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleScenarioAnalysis() {
    setLoading("scenario");
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

      const selectedScenario =
        window.prompt(
          [
            "Selecciona un escenario:",
            "financial_crisis_2008",
            "covid_2020",
            "technology_shock",
            "rate_hike",
          ].join("\n"),
          "financial_crisis_2008"
        );

      if (selectedScenario === null) {
        return;
      }

      const payload =
        await runScenarioAnalysis({
          weights: toRecord(
            symbols,
            normalizedWeights
          ),
          scenario:
            selectedScenario.trim(),
          initial_value: 1000,
        });

      setScenarioAnalysis(
        payload
      );
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleStressTest() {
    setLoading("stress");
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

      const defaultShocks = symbols
        .map(
          (_, index) =>
            index === 0
              ? "-30"
              : index === 1
                ? "-20"
                : "-15"
        )
        .join(",");

      const shockInput = window.prompt(
        `Ingresa los shocks porcentuales para ${symbols.join(
          ", "
        )}`,
        defaultShocks
      );

      if (shockInput === null) {
        return;
      }

      const shockPercentages =
        parseNumbers(
          shockInput
        );

      if (
        symbols.length
        !== shockPercentages.length
      ) {
        throw new Error(
          "Debe existir un shock por cada activo."
        );
      }

      const shocks =
        shockPercentages.map(
          (shock) => shock / 100
        );

      const payload =
        await runStressTest({
          weights: toRecord(
            symbols,
            normalizedWeights
          ),
          shocks: toRecord(
            symbols,
            shocks
          ),
          initial_value: 1000,
        });

      setStressTesting(
        payload
      );
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleFamaFrenchAnalytics() {
    setLoading("fama-french");
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
        await calculateFamaFrenchAnalytics({
          symbols,
          weights: toRecord(
            symbols,
            normalizedWeights
          ),
          market: "SPY",
          small_cap: "IWM",
          value: "IWD",
          growth: "IWF",
          period: "1y",
          risk_free_rate:
            formValues.riskFreeRate,
        });

      setFamaFrenchAnalytics(
        payload
      );
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleCapmAnalytics() {
    setLoading("capm");
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
        await calculateCapmAnalytics({
          symbols,
          weights: toRecord(
            symbols,
            normalizedWeights
          ),
          market: "SPY",
          period: "1y",
          risk_free_rate:
            formValues.riskFreeRate,
        });

      setCapmAnalytics(
        payload
      );
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleRollingAnalytics() {
    setLoading("rolling");
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
        await calculateRollingAnalytics({
          symbols,
          weights: toRecord(
            symbols,
            normalizedWeights
          ),
          period: "1y",
          window: 30,
          risk_free_rate:
            formValues.riskFreeRate,
        });

      setRollingAnalytics(
        payload
      );
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }

  async function handleDrawdownAnalytics() {
    setLoading("drawdown");
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
        await calculateDrawdownAnalytics({
          symbols,
          weights: toRecord(
            symbols,
            normalizedWeights
          ),
          period: "1y",
        });

      setDrawdownAnalytics(
        payload
      );
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


  async function handleAskCopilot() {
    const normalizedQuestion =
      copilotQuestion.trim();

    if (!normalizedQuestion) {
      setError(
        "Escribe una pregunta para ARMS AI."
      );
      return;
    }

    setLoading("copilot");
    setError("");
    setCopilotResult(null);

    try {
      const symbols = parseSymbols(
        formValues.symbols
      );

      const currentWeights = parseNumbers(
        formValues.currentWeights
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

      if (
        symbols.length
        !== currentWeights.length
      ) {
        throw new Error(
          "Assets y current weights deben tener la misma cantidad de valores."
        );
      }

      const weights = toRecord(
        symbols,
        currentWeights.map(
          (weight) => weight / 100
        )
      );

      const averageVolatility =
        volatilities.reduce(
          (total, value) => total + value,
          0
        ) / volatilities.length;

      const averageExpectedReturn =
        expectedReturns.reduce(
          (total, value) => total + value,
          0
        ) / expectedReturns.length;

      const estimatedSharpe =
        averageVolatility > 0
          ? (
              averageExpectedReturn
              - formValues.riskFreeRate
            ) / averageVolatility
          : 0;

      const payload = await askAiCopilot({
        question: normalizedQuestion,
        weights,
        metrics: {
          volatility: averageVolatility,
          sharpe_ratio: estimatedSharpe,
          beta: 1,
          drawdown: -averageVolatility,
        },
      });

      setCopilotResult(payload);
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }


  function buildTradingCandles() {
    const total = 60;
    const startTime = Date.UTC(
      2026,
      6,
      22,
      9,
      30
    );

    return Array.from(
      { length: total },
      (_, index) => {
        const base =
          21600 + index * 1.5;

        return {
          symbol: "NQ",
          timeframe: "5m",
          open: base,
          high: base + 4,
          low: base - 2,
          close: base + 2.5,
          volume: 1000 + index * 10,
          timestamp: new Date(
            startTime
            + index * 5 * 60 * 1000
          ).toISOString(),
        };
      }
    );
  }

  async function handleAnalyzeTradingContext() {
    setLoading("trading-context");
    setError("");
    setTradingContext(null);

    try {
      const payload =
        await analyzeTradingContext({
          symbol: "NQ",
          timeframe: "5m",
          candles: buildTradingCandles(),
          account_balance: 17000,
          risk_percent: 0.5,
          point_value: 2,
          reward_risk_ratio: 2,
        });

      setTradingContext(payload);
    } catch (caughtError) {
      handleError(caughtError);
    } finally {
      setLoading(null);
    }
  }


  async function handleLoadLatestAnalysis() {
    setLoading("latest-analysis");
    setError("");

    try {
      const payload =
        await getLatestMarketAnalysis(
          "NQ",
          "5m"
        );

      setTradingContext(payload);
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

        <section className="mt-10 rounded-xl bg-slate-900 p-6 text-white shadow-xl md:p-8">
          <div className="flex flex-col gap-2">
            <p className="text-sm font-semibold uppercase tracking-widest text-cyan-400">
              Intelligent Assistant
            </p>

            <h2 className="text-3xl font-bold">
              ARMS AI Copilot
            </h2>

            <p className="max-w-3xl text-slate-300">
              Pregunta sobre el riesgo, la composición o el rendimiento estimado de tu portafolio.
            </p>
          </div>

          <div className="mt-6">
            <label
              htmlFor="copilot-question"
              className="text-sm font-medium text-slate-200"
            >
              Pregunta para ARMS AI
            </label>

            <textarea
              id="copilot-question"
              value={copilotQuestion}
              onChange={(event) =>
                setCopilotQuestion(
                  event.target.value
                )
              }
              placeholder="Ejemplo: ¿Cómo puedo reducir el riesgo de este portafolio?"
              rows={4}
              className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 p-4 text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20"
            />
          </div>

          <button
            type="button"
            onClick={handleAskCopilot}
            disabled={loading !== null}
            className="mt-4 rounded-lg bg-cyan-500 px-6 py-3 font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading === "copilot"
              ? "Analizando..."
              : "Preguntar a ARMS AI"}
          </button>

          {copilotResult && (
            <div className="mt-8 space-y-6">
              <div className="rounded-xl border border-slate-700 bg-slate-800 p-5">
                <p className="text-sm font-semibold uppercase tracking-wide text-cyan-400">
                  Respuesta
                </p>

                <p className="mt-3 whitespace-pre-wrap leading-7 text-slate-200">
                  {copilotResult.content}
                </p>

                <p className="mt-4 text-xs text-slate-500">
                  Proveedor: {copilotResult.provider}
                  {" · "}
                  Modelo: {copilotResult.model}
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-slate-700 bg-slate-800 p-5">
                  <p className="text-sm text-slate-400">
                    Portfolio Score
                  </p>

                  <p className="mt-2 text-4xl font-bold text-white">
                    {copilotResult.decision.score}
                    <span className="text-lg text-slate-400">
                      /100
                    </span>
                  </p>
                </div>

                <div className="rounded-xl border border-slate-700 bg-slate-800 p-5">
                  <p className="text-sm text-slate-400">
                    Nivel de riesgo
                  </p>

                  <p className="mt-2 text-2xl font-bold capitalize text-white">
                    {copilotResult.decision.risk_level}
                  </p>
                </div>
              </div>

              {copilotResult.decision.recommendations.length > 0 && (
                <div className="rounded-xl border border-emerald-900 bg-emerald-950/40 p-5">
                  <h3 className="text-lg font-semibold text-emerald-300">
                    Recomendaciones
                  </h3>

                  <ul className="mt-3 space-y-2 text-emerald-100">
                    {copilotResult.decision.recommendations.map(
                      (recommendation) => (
                        <li
                          key={recommendation}
                          className="flex gap-2"
                        >
                          <span aria-hidden="true">
                            ✓
                          </span>
                          <span>
                            {recommendation}
                          </span>
                        </li>
                      )
                    )}
                  </ul>
                </div>
              )}

              {copilotResult.decision.alerts.length > 0 && (
                <div className="rounded-xl border border-amber-900 bg-amber-950/40 p-5">
                  <h3 className="text-lg font-semibold text-amber-300">
                    Alertas
                  </h3>

                  <ul className="mt-3 space-y-2 text-amber-100">
                    {copilotResult.decision.alerts.map(
                      (alert) => (
                        <li
                          key={alert}
                          className="flex gap-2"
                        >
                          <span aria-hidden="true">
                            !
                          </span>
                          <span>
                            {alert}
                          </span>
                        </li>
                      )
                    )}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>

        <section className="mt-10 rounded-xl bg-white p-6 shadow-xl md:p-8">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-widest text-blue-600">
                Trading Intelligence
              </p>

              <h2 className="mt-2 text-3xl font-bold text-slate-900">
                ARMS AI Trading Dashboard
              </h2>

              <p className="mt-2 max-w-3xl text-slate-600">
                Ejecuta el pipeline completo de análisis técnico, Smart Money, probabilidad y riesgo.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleAnalyzeTradingContext}
                disabled={loading !== null}
                className="rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading === "trading-context"
                  ? "Analizando mercado..."
                  : "Analizar mercado"}
              </button>

              <button
                type="button"
                onClick={handleLoadLatestAnalysis}
                disabled={loading !== null}
                className="rounded-lg bg-slate-800 px-6 py-3 font-semibold text-white transition hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading === "latest-analysis"
                  ? "Cargando..."
                  : "Cargar último análisis"}
              </button>
            </div>
          </div>

          {!tradingContext && (
            <div className="mt-8 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
              <p className="font-medium text-slate-700">
                Todavía no se ha ejecutado el análisis de trading.
              </p>

              <p className="mt-2 text-sm text-slate-500">
                La primera prueba usa 60 velas simuladas del NQ en temporalidad de 5 minutos.
              </p>
            </div>
          )}

          {tradingContext && (
            <div className="mt-8 space-y-6">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <TradingMetricCard
                  label="Símbolo"
                  value={tradingContext.symbol}
                />

                <TradingMetricCard
                  label="Temporalidad"
                  value={tradingContext.timeframe}
                />

                <TradingMetricCard
                  label="Precio actual"
                  value={formatNumber(
                    tradingContext.current_price
                  )}
                />

                <TradingMetricCard
                  label="Tendencia"
                  value={tradingContext.trend}
                />
              </div>

              <div>
                <h3 className="text-xl font-semibold text-slate-900">
                  Indicadores
                </h3>

                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <TradingMetricCard
                    label={`EMA ${
                      tradingContext.indicators.ema_period
                      ?? ""
                    }`}
                    value={formatNumber(
                      tradingContext.indicators.ema
                    )}
                  />

                  <TradingMetricCard
                    label="RSI"
                    value={formatNumber(
                      tradingContext.indicators.rsi
                    )}
                    helper={
                      tradingContext.indicators.rsi_status
                    }
                  />

                  <TradingMetricCard
                    label="ATR"
                    value={formatNumber(
                      tradingContext.indicators.atr
                    )}
                    helper={
                      tradingContext.indicators.atr_status
                    }
                  />
                </div>
              </div>

              <div>
                <h3 className="text-xl font-semibold text-slate-900">
                  Estructura y Smart Money
                </h3>

                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <TradingMetricCard
                    label="Estructura"
                    value={
                      tradingContext.market_structure.direction
                    }
                    helper={`${
                      tradingContext.market_structure.high_type
                    } / ${
                      tradingContext.market_structure.low_type
                    }`}
                  />

                  <TradingMetricCard
                    label="BOS"
                    value={
                      tradingContext.smart_money.bos.detected
                        ? "Detectado"
                        : "No detectado"
                    }
                    helper={
                      tradingContext.smart_money.bos.direction
                    }
                  />

                  <TradingMetricCard
                    label="CHoCH"
                    value={
                      tradingContext.smart_money.choch.detected
                        ? "Detectado"
                        : "No detectado"
                    }
                    helper={
                      tradingContext.smart_money.choch.direction
                    }
                  />

                  <TradingMetricCard
                    label="Liquidez"
                    value={
                      tradingContext.smart_money.liquidity.detected
                        ? "Barrido detectado"
                        : "Sin barrido"
                    }
                    helper={
                      tradingContext.smart_money.liquidity.direction
                    }
                  />
                </div>
              </div>

              <div>
                <h3 className="text-xl font-semibold text-slate-900">
                  Decisión y probabilidad
                </h3>

                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <TradingMetricCard
                    label="Score"
                    value={`${formatNumber(
                      tradingContext.decision.score
                    )}/100`}
                  />

                  <TradingMetricCard
                    label="Calificación"
                    value={tradingContext.decision.grade}
                  />

                  <TradingMetricCard
                    label="Acción"
                    value={tradingContext.decision.action}
                  />

                  <TradingMetricCard
                    label="Probabilidad"
                    value={`${formatNumber(
                      tradingContext.probability.value
                    )}%`}
                    helper={
                      tradingContext.probability.confidence
                    }
                  />
                </div>
              </div>

              <div>
                <h3 className="text-xl font-semibold text-slate-900">
                  Riesgo y niveles
                </h3>

                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <TradingMetricCard
                    label="Estado del riesgo"
                    value={
                      tradingContext.risk.approved
                        ? "Aprobado"
                        : "Bloqueado"
                    }
                  />

                  <TradingMetricCard
                    label="Contratos"
                    value={String(
                      tradingContext.risk.contracts
                    )}
                  />

                  <TradingMetricCard
                    label="Riesgo máximo"
                    value={`$${formatNumber(
                      tradingContext.risk.risk_amount
                    )}`}
                  />

                  <TradingMetricCard
                    label="R:R"
                    value="1:2"
                  />
                </div>

                <div className="mt-4 grid gap-4 sm:grid-cols-3">
                  <TradingMetricCard
                    label="Entrada"
                    value={formatNumber(
                      tradingContext.trade.entry_price
                    )}
                  />

                  <TradingMetricCard
                    label="Stop Loss"
                    value={formatNumber(
                      tradingContext.trade.stop_loss
                    )}
                  />

                  <TradingMetricCard
                    label="Take Profit"
                    value={formatNumber(
                      tradingContext.trade.take_profit
                    )}
                  />
                </div>
              </div>

              {tradingContext.decision.confirmations.length > 0 && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
                  <h3 className="font-semibold text-emerald-900">
                    Confirmaciones
                  </h3>

                  <ul className="mt-3 space-y-2 text-sm text-emerald-800">
                    {tradingContext.decision.confirmations.map(
                      (confirmation) => (
                        <li key={confirmation}>
                          ✓ {confirmation}
                        </li>
                      )
                    )}
                  </ul>
                </div>
              )}

              {tradingContext.decision.warnings.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
                  <h3 className="font-semibold text-amber-900">
                    Advertencias
                  </h3>

                  <ul className="mt-3 space-y-2 text-sm text-amber-800">
                    {tradingContext.decision.warnings.map(
                      (warning) => (
                        <li key={warning}>
                          ! {warning}
                        </li>
                      )
                    )}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>

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

            <ActionButton
              label="Drawdown"
              loadingLabel="Calculating..."
              active={loading === "drawdown"}
              disabled={loading !== null}
              className="bg-red-600 hover:bg-red-700"
              onClick={handleDrawdownAnalytics}
            />

            <ActionButton
              label="Rolling"
              loadingLabel="Calculating..."
              active={loading === "rolling"}
              disabled={loading !== null}
              className="bg-indigo-600 hover:bg-indigo-700"
              onClick={handleRollingAnalytics}
            />

            <ActionButton
              label="CAPM"
              loadingLabel="Calculating..."
              active={loading === "capm"}
              disabled={loading !== null}
              className="bg-teal-600 hover:bg-teal-700"
              onClick={handleCapmAnalytics}
            />

            <ActionButton
              label="Fama-French"
              loadingLabel="Calculating..."
              active={loading === "fama-french"}
              disabled={loading !== null}
              className="bg-amber-600 hover:bg-amber-700"
              onClick={handleFamaFrenchAnalytics}
            />

            <ActionButton
              label="Stress Test"
              loadingLabel="Testing..."
              active={loading === "stress"}
              disabled={loading !== null}
              className="bg-orange-700 hover:bg-orange-800"
              onClick={handleStressTest}
            />

            <ActionButton
              label="Scenario"
              loadingLabel="Applying..."
              active={loading === "scenario"}
              disabled={loading !== null}
              className="bg-fuchsia-700 hover:bg-fuchsia-800"
              onClick={handleScenarioAnalysis}
            />

            <ActionButton
              label="Risk Contribution"
              loadingLabel="Calculating..."
              active={
                loading === "risk-contribution"
              }
              disabled={loading !== null}
              className="bg-violet-700 hover:bg-violet-800"
              onClick={handleRiskContribution}
            />

            <ActionButton
              label="Attribution"
              loadingLabel="Calculating..."
              active={loading === "attribution"}
              disabled={loading !== null}
              className="bg-sky-700 hover:bg-sky-800"
              onClick={handlePerformanceAttribution}
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

          {performanceAttribution && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Performance Attribution
              </h3>

              <p className="mt-3 text-slate-600">
                Explicación del active return por asignación,
                selección e interacción.
              </p>

              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Portfolio return"
                  value={`${(
                    performanceAttribution.portfolio_return
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Benchmark return"
                  value={`${(
                    performanceAttribution.benchmark_return
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Active return"
                  value={`${(
                    performanceAttribution.active_return
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Allocation effect"
                  value={`${(
                    performanceAttribution.allocation_effect
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Selection effect"
                  value={`${(
                    performanceAttribution.selection_effect
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Interaction effect"
                  value={`${(
                    performanceAttribution.interaction_effect
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Best asset"
                  value={
                    performanceAttribution.best_asset
                  }
                />

                <MetricCard
                  label="Worst asset"
                  value={
                    performanceAttribution.worst_asset
                  }
                />
              </div>

              <div className="mt-6">
                <PerformanceAttributionChart
                  allocation={
                    performanceAttribution.allocation_by_asset
                  }
                  selection={
                    performanceAttribution.selection_by_asset
                  }
                  interaction={
                    performanceAttribution.interaction_by_asset
                  }
                />
              </div>

              <div className="mt-6 overflow-x-auto rounded-xl border border-slate-200 bg-white">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-100 text-slate-700">
                    <tr>
                      <th className="px-4 py-3 text-left">
                        Asset
                      </th>
                      <th className="px-4 py-3 text-right">
                        Allocation
                      </th>
                      <th className="px-4 py-3 text-right">
                        Selection
                      </th>
                      <th className="px-4 py-3 text-right">
                        Interaction
                      </th>
                      <th className="px-4 py-3 text-right">
                        Total
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {Object.keys(
                      performanceAttribution.asset_contributions
                    ).map((asset) => (
                      <tr
                        key={asset}
                        className="border-t border-slate-200"
                      >
                        <td className="px-4 py-3 font-medium">
                          {asset}
                        </td>

                        <td className="px-4 py-3 text-right">
                          {(
                            performanceAttribution.allocation_by_asset[
                              asset
                            ] * 100
                          ).toFixed(2)}
                          %
                        </td>

                        <td className="px-4 py-3 text-right">
                          {(
                            performanceAttribution.selection_by_asset[
                              asset
                            ] * 100
                          ).toFixed(2)}
                          %
                        </td>

                        <td className="px-4 py-3 text-right">
                          {(
                            performanceAttribution.interaction_by_asset[
                              asset
                            ] * 100
                          ).toFixed(2)}
                          %
                        </td>

                        <td className="px-4 py-3 text-right font-semibold">
                          {(
                            performanceAttribution.asset_contributions[
                              asset
                            ] * 100
                          ).toFixed(2)}
                          %
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {riskContribution && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Risk Contribution
              </h3>

              <p className="mt-3 text-slate-600">
                Distribución del riesgo total entre los activos.
              </p>

              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <MetricCard
                  label="Portfolio volatility"
                  value={`${(
                    riskContribution.portfolio_volatility
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Highest risk asset"
                  value={
                    riskContribution.highest_risk_asset
                  }
                />

                <MetricCard
                  label="Lowest risk asset"
                  value={
                    riskContribution.lowest_risk_asset
                  }
                />
              </div>

              <div className="mt-6">
                <RiskContributionChart
                  contributions={
                    riskContribution.percentage_contributions
                  }
                />
              </div>

              <div className="mt-6 overflow-x-auto rounded-xl border border-slate-200 bg-white">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-100 text-slate-700">
                    <tr>
                      <th className="px-4 py-3 text-left">
                        Asset
                      </th>
                      <th className="px-4 py-3 text-right">
                        Marginal
                      </th>
                      <th className="px-4 py-3 text-right">
                        Absolute
                      </th>
                      <th className="px-4 py-3 text-right">
                        Percentage
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {Object.keys(
                      riskContribution.percentage_contributions
                    ).map((asset) => (
                      <tr
                        key={asset}
                        className="border-t border-slate-200"
                      >
                        <td className="px-4 py-3 font-medium">
                          {asset}
                        </td>

                        <td className="px-4 py-3 text-right">
                          {riskContribution.marginal_contributions[
                            asset
                          ].toFixed(4)}
                        </td>

                        <td className="px-4 py-3 text-right">
                          {riskContribution.absolute_contributions[
                            asset
                          ].toFixed(4)}
                        </td>

                        <td className="px-4 py-3 text-right">
                          {(
                            riskContribution.percentage_contributions[
                              asset
                            ] * 100
                          ).toFixed(2)}
                          %
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {scenarioAnalysis && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Scenario Analysis
              </h3>

              <p className="mt-3 text-slate-600">
                Resultado del escenario {
                  scenarioAnalysis.scenario
                }.
              </p>

              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Initial value"
                  value={`$${scenarioAnalysis.initial_value.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="Final value"
                  value={`$${scenarioAnalysis.final_value.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="Absolute impact"
                  value={`$${scenarioAnalysis.absolute_impact.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="Percentage impact"
                  value={`${(
                    scenarioAnalysis.percentage_impact
                    * 100
                  ).toFixed(2)}%`}
                />
              </div>

              <div className="mt-6">
                <ScenarioImpactChart
                  impacts={
                    scenarioAnalysis.asset_impacts
                  }
                />
              </div>
            </section>
          )}

          {stressTesting && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Portfolio Stress Test
              </h3>

              <p className="mt-3 text-slate-600">
                Impacto del escenario personalizado sobre el portafolio.
              </p>

              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Initial value"
                  value={`$${stressTesting.initial_value.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="Final value"
                  value={`$${stressTesting.final_value.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="Absolute impact"
                  value={`$${stressTesting.absolute_loss.toFixed(
                    2
                  )}`}
                />

                <MetricCard
                  label="Percentage impact"
                  value={`${(
                    stressTesting.percentage_loss
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Worst asset"
                  value={stressTesting.worst_asset}
                />

                <MetricCard
                  label="Best asset"
                  value={stressTesting.best_asset}
                />
              </div>

              <div className="mt-6">
                <StressImpactChart
                  impacts={
                    stressTesting.asset_impacts
                  }
                />
              </div>
            </section>
          )}

          {famaFrenchAnalytics && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Fama-French Analytics
              </h3>

              <p className="mt-3 text-slate-600">
                Exposición del portafolio a mercado, tamaño y valor.
              </p>

              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <MetricCard
                  label="Alpha"
                  value={`${(
                    famaFrenchAnalytics.alpha
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Beta market"
                  value={famaFrenchAnalytics.beta_market.toFixed(
                    2
                  )}
                />

                <MetricCard
                  label="Beta SMB"
                  value={famaFrenchAnalytics.beta_smb.toFixed(
                    2
                  )}
                />

                <MetricCard
                  label="Beta HML"
                  value={famaFrenchAnalytics.beta_hml.toFixed(
                    2
                  )}
                />

                <MetricCard
                  label="R²"
                  value={`${(
                    famaFrenchAnalytics.r_squared
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Expected return"
                  value={`${(
                    famaFrenchAnalytics.expected_return
                    * 100
                  ).toFixed(2)}%`}
                />
              </div>
            </section>
          )}

          {capmAnalytics && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                CAPM Analytics
              </h3>

              <p className="mt-3 text-slate-600">
                Métricas del portafolio frente al mercado SPY.
              </p>

              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <MetricCard
                  label="Beta"
                  value={capmAnalytics.beta.toFixed(
                    2
                  )}
                />

                <MetricCard
                  label="Jensen's alpha"
                  value={`${(
                    capmAnalytics.jensens_alpha
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="CAPM expected return"
                  value={`${(
                    capmAnalytics.capm_expected_return
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Market risk premium"
                  value={`${(
                    capmAnalytics.market_risk_premium
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Treynor ratio"
                  value={capmAnalytics.treynor_ratio.toFixed(
                    2
                  )}
                />

                <MetricCard
                  label="Modigliani M²"
                  value={`${(
                    capmAnalytics.modigliani_m2
                    * 100
                  ).toFixed(2)}%`}
                />
              </div>
            </section>
          )}

          {rollingAnalytics && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Rolling Analytics
              </h3>

              <p className="mt-3 text-slate-600">
                Métricas móviles calculadas con una ventana de 30 períodos.
              </p>

              <div className="mt-6">
                <RollingAnalyticsChart
                  rollingVolatility={
                    rollingAnalytics.rolling_volatility
                  }
                  rollingSharpe={
                    rollingAnalytics.rolling_sharpe
                  }
                  rollingDrawdown={
                    rollingAnalytics.rolling_drawdown
                  }
                />
              </div>
            </section>
          )}

          {drawdownAnalytics && (
            <section className="mt-8 rounded-xl bg-slate-50 p-6">
              <h3 className="text-xl font-semibold">
                Drawdown Analytics
              </h3>

              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  label="Maximum drawdown"
                  value={`${(
                    drawdownAnalytics.maximum_drawdown
                    * 100
                  ).toFixed(2)}%`}
                />

                <MetricCard
                  label="Maximum duration"
                  value={`${drawdownAnalytics.maximum_drawdown_duration} periods`}
                />

                <MetricCard
                  label="Peak index"
                  value={
                    drawdownAnalytics.peak_index
                  }
                />

                <MetricCard
                  label="Trough index"
                  value={
                    drawdownAnalytics.trough_index
                  }
                />
              </div>

              <div className="mt-6">
                <DrawdownChart
                  values={
                    drawdownAnalytics.drawdown_curve
                  }
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

function formatNumber(
  value: number,
): string {
  return new Intl.NumberFormat(
    "en-US",
    {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }
  ).format(value);
}


function TradingMetricCard({
  label,
  value,
  helper,
}: {
  label: string;
  value: string;
  helper?: string | null;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
      <p className="text-sm font-medium text-slate-500">
        {label}
      </p>

      <p className="mt-2 text-2xl font-bold text-slate-900">
        {value}
      </p>

      {helper && (
        <p className="mt-2 text-sm text-slate-500">
          {helper}
        </p>
      )}
    </div>
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
