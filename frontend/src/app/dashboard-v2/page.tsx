"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  getDashboardLive,
  getDashboardWebSocketUrl,
  getDashboardWidgets,
  getRiskDashboard,
  getAccountProfile,
  switchAccount,
  getStrategyRanking,
  getBacktestingDashboard,
  getTradeSetup,
  getExecutionApproval,
  getExecutionSimulator,
  getExecutionManager,
  getPerformanceIntelligence,
  getAILearning,
  getAIPattern,
  getTradingMemory,
  getAIDecisionMemory,
  getConfidenceFusion,
  getIntelligenceDecisionV3,
  getExecutionPipeline,

  getLearningSummary,
  getIntelligenceDecision,
  getAIDecision,
  type JsonObject,
  type JsonValue,
} from "@/lib/dashboardApi";


import StrategyIntelligenceCard from "@/components/dashboard-v2/StrategyIntelligenceCard";

import AccountOverviewCard from "@/components/dashboard-v2/AccountOverviewCard";
import RiskManagementCard from "@/components/dashboard-v2/RiskManagementCard";
import RiskProfileCard from "@/components/dashboard-v2/RiskProfileCard";
import AccountSelectorCard from "@/components/dashboard-v2/AccountSelectorCard";
import PerformanceAnalyticsCard from "@/components/dashboard-v2/PerformanceAnalyticsCard";
import BacktestingAnalyticsCard from "@/components/dashboard-v2/BacktestingAnalyticsCard";
import TradeSetupIntelligenceCard from "@/components/dashboard-v2/TradeSetupIntelligenceCard";

import ExecutionApprovalCard from "@/components/dashboard-v2/ExecutionApprovalCard";
import ExecutionSimulatorCard from "@/components/dashboard-v2/ExecutionSimulatorCard";
import ExecutionManagerCard from "@/components/dashboard-v2/ExecutionManagerCard";
import PerformanceIntelligenceCard from "@/components/dashboard-v2/PerformanceIntelligenceCard";
import AILearningIntelligenceCard from "@/components/dashboard-v2/AILearningIntelligenceCard";
import AIPatternIntelligenceCard from "@/components/dashboard-v2/AIPatternIntelligenceCard";
import AITradingMemoryIntelligenceCard from "@/components/dashboard-v2/AITradingMemoryIntelligenceCard";
import AIDecisionMemoryIntelligenceCard from "@/components/dashboard-v2/AIDecisionMemoryIntelligenceCard";
import ConfidenceFusionIntelligenceCard from "@/components/dashboard-v2/ConfidenceFusionIntelligenceCard";
import AIDecisionEngineV3Card from "@/components/dashboard-v2/AIDecisionEngineV3Card";

import TradeExecutionPlanCard from "@/components/dashboard-v2/TradeExecutionPlanCard";

import ExecutionPipelineCard from "@/components/dashboard-v2/ExecutionPipelineCard";
import AIDecisionEngineCard from "@/components/dashboard-v2/AIDecisionEngineCard";
import TradeJournalCard from "@/components/dashboard-v2/TradeJournalCard";
import StrategyRankingCard from "@/components/dashboard-v2/StrategyRankingCard";


type ConnectionStatus =
  | "CONNECTING"
  | "CONNECTED"
  | "DISCONNECTED"
  | "ERROR";


type MetricItem = {
  label: string;
  value: string;
};


function isObject(
  value: JsonValue | undefined
): value is JsonObject {
  return (
    typeof value === "object"
    && value !== null
    && !Array.isArray(value)
  );
}


function formatLabel(
  value: string
): string {
  return value
    .replace(
      /_/g,
      " "
    )
    .replace(
      /\b\w/g,
      (character) =>
        character.toUpperCase()
    );
}


function formatValue(
  value: JsonValue
): string {
  if (value === null) {
    return "—";
  }

  if (
    typeof value === "number"
  ) {
    return new Intl.NumberFormat(
      "es-EC",
      {
        maximumFractionDigits: 2,
      }
    ).format(value);
  }

  if (
    typeof value === "boolean"
  ) {
    return value
      ? "Sí"
      : "No";
  }

  if (
    typeof value === "string"
  ) {
    return value;
  }

  if (
    Array.isArray(value)
  ) {
    return `${value.length} elementos`;
  }

  return `${Object.keys(value).length} campos`;
}


function extractMetrics(
  source: JsonObject | null,
  limit = 12
): MetricItem[] {
  if (!source) {
    return [];
  }

  const metrics: MetricItem[] = [];

  for (
    const [key, value]
    of Object.entries(source)
  ) {
    if (
      typeof value === "object"
      && value !== null
    ) {
      continue;
    }

    metrics.push(
      {
        label: formatLabel(key),
        value: formatValue(value),
      }
    );

    if (
      metrics.length >= limit
    ) {
      break;
    }
  }

  return metrics;
}


function MetricCard({
  label,
  value,
}: MetricItem) {
  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-lg shadow-black/10">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
        {label}
      </p>

      <p className="mt-3 break-words text-2xl font-semibold text-white">
        {value}
      </p>
    </article>
  );
}


function DataPanel({
  title,
  data,
}: {
  title: string;
  data: JsonObject | null;
}) {
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/70">
      <div className="border-b border-slate-800 px-5 py-4">
        <h2 className="font-semibold text-white">
          {title}
        </h2>
      </div>

      <div className="max-h-[440px] overflow-auto p-5">
        {data ? (
          <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-6 text-slate-300">
            {JSON.stringify(
              data,
              null,
              2
            )}
          </pre>
        ) : (
          <p className="text-sm text-slate-500">
            No hay información disponible.
          </p>
        )}
      </div>
    </article>
  );
}


export default function DashboardV2Page() {
  const [
    liveSnapshot,
    setLiveSnapshot,
  ] = useState<JsonObject | null>(
    null
  );

  const [
    widgets,
    setWidgets,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    strategyRanking,
    setStrategyRanking,
  ] = useState<JsonObject | null>(
    null
  );

  const [
    backtestingDashboard,
    setBacktestingDashboard,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    tradeSetup,
    setTradeSetup,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    riskProfileData,
    setRiskProfileData,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    accountData,
    setAccountData,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    executionApproval,
    setExecutionApproval,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    executionSimulation,
    setExecutionSimulation,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    executionPlan,
    setExecutionPlan,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    performanceData,
    setPerformanceData,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    aiPatternData,
    setAiPatternData,
  ] = useState<JsonObject | null>(
    null
  );



  const [
    aiLearningData,
    setAILearningData,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    tradingMemoryData,
    setTradingMemoryData,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    aiDecisionMemoryData,
    setAIDecisionMemoryData,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    confidenceFusionData,
    setConfidenceFusionData,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    intelligenceDecisionV3Data,
    setIntelligenceDecisionV3Data,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    intelligenceTradePlanData,
    setIntelligenceTradePlanData,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    executionPipelineData,
    setExecutionPipelineData,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    learningIntelligenceData,
    setLearningIntelligenceData,
  ] = useState<JsonObject | null>(
    null
  );


  const [
    intelligenceDecisionData,
    setIntelligenceDecisionData,
  ] = useState<JsonObject | null>(
    null
  );







  const [
    aiDecision,
    setAiDecision,
  ] = useState<JsonObject | null>(
    null
  );



  

  const [
    latestEvent,
    setLatestEvent,
  ] = useState<JsonObject | null>(
    null
  );

  const [
    connectionStatus,
    setConnectionStatus,
  ] = useState<ConnectionStatus>(
    "CONNECTING"
  );

  const [
    error,
    setError,
  ] = useState("");

  const [
    lastUpdated,
    setLastUpdated,
  ] = useState<Date | null>(
    null
  );

  const websocketRef =
    useRef<WebSocket | null>(
      null
    );

  const reconnectTimerRef =
    useRef<
      ReturnType<typeof setTimeout>
      | null
    >(null);


  const handleChangeAccount =
    useCallback(
      async (
        account: string
      ) => {

        try {

          await switchAccount(
            account
          );


          const updatedAccount =
            await getAccountProfile();


          setAccountData(
            updatedAccount
          );


          const updatedRisk =
            await getRiskDashboard();


          setRiskProfileData(
            updatedRisk
          );


        } catch (error) {

          console.error(
            "ACCOUNT SWITCH ERROR:",
            error
          );

        }

      },
      []
    );



  const loadDashboard =
    useCallback(
      async () => {
        try {
          setError("");

          const [
            liveResult,
            widgetResult,
            rankingResult,
            backtestingResult,
            tradeSetupResult,
            aiDecisionResult,
            executionApprovalResult,
            executionSimulationResult,
            executionPlanResult,
            performanceResult,
            aiPatternResult,
            aiLearningResult,
            tradingMemoryResult,
            aiDecisionMemoryResult,
            confidenceFusionResult,
            intelligenceDecisionV3Result,
            executionPipelineResult,
            learningIntelligenceResult,
            riskResult,
            accountResult,
          ] = await Promise.all(
            [
              getDashboardLive(),
              getDashboardWidgets(),
              getStrategyRanking(),
              getBacktestingDashboard(),
              getTradeSetup(),
              getAIDecision(),
              getExecutionApproval(),
              getExecutionSimulator(),
              getExecutionManager(),
              getPerformanceIntelligence(),
              getAIPattern(),
              getAILearning(),
              getTradingMemory(),
              getAIDecisionMemory(),
              getConfidenceFusion(),
              getIntelligenceDecisionV3(),
              getExecutionPipeline(),
              getLearningSummary(),
              getRiskDashboard(),
              getAccountProfile(),
            ]
          );

          setLiveSnapshot(
            liveResult
          );

          setWidgets(
            widgetResult
          );

          setStrategyRanking(
            rankingResult
          );

          setBacktestingDashboard(
            backtestingResult
          );


          setTradeSetup(
            tradeSetupResult
          );


          setRiskProfileData(
            riskResult
          );


          setAccountData(
            accountResult
          );


          console.log(
            "AI DECISION RESULT:",
            JSON.stringify(
              aiDecisionResult,
              null,
              2
            )
          );


          console.log(
            "EXECUTION APPROVAL RESULT:",
            JSON.stringify(
              executionApprovalResult,
              null,
              2
            )
          );


          console.log(
            "EXECUTION SIMULATION RESULT:",
            JSON.stringify(
              executionSimulationResult,
              null,
              2
            )
          );


          console.log(
            "EXECUTION PLAN RESULT:",
            JSON.stringify(
              {
                executionPlanResult,
                performanceResult,
            aiPatternResult,
            aiLearningResult,
              },
              null,
              2
            )
          );


          setAiDecision(
            aiDecisionResult
          );


          setExecutionApproval(
            executionApprovalResult
          );


          setExecutionSimulation(
            executionSimulationResult
          );


          setExecutionPlan(
            executionPlanResult
          );


          console.log(
            "PERFORMANCE RESULT:",
            performanceResult
          );


          setPerformanceData(
            performanceResult
          );


          setAILearningData(
            aiLearningResult
          );


          setAiPatternData(
            aiPatternResult
          );


          setTradingMemoryData(
            tradingMemoryResult
          );


          setAIDecisionMemoryData(
            aiDecisionMemoryResult
          );


          setConfidenceFusionData(
            confidenceFusionResult
          );


          setIntelligenceDecisionV3Data(
            intelligenceDecisionV3Result
          );


          setIntelligenceTradePlanData(
            intelligenceDecisionV3Result.trade_plan as JsonObject
          );


          setExecutionPipelineData(
            executionPipelineResult
          );


          setLearningIntelligenceData(
            learningIntelligenceResult
          );


          setIntelligenceDecisionV3Data(
            intelligenceDecisionV3Result
          );


          setLastUpdated(
            new Date()
          );
        } catch (
          caughtError
        ) {
          const message =
            caughtError
            instanceof Error
              ? caughtError.message
              : "No fue posible cargar el Dashboard.";

          setError(message);
        }
      },
      []
    );


  useEffect(
    () => {
      const initialLoadTimer =
        window.setTimeout(
          () => {
            void loadDashboard();
          },
          0
        );

      return () => {
        window.clearTimeout(
          initialLoadTimer
        );
      };
    },
    [loadDashboard]
  );


  useEffect(
    () => {
      let active = true;

      function connect() {
        if (!active) {
          return;
        }

        setConnectionStatus(
          "CONNECTING"
        );

        const websocket =
          new WebSocket(
            getDashboardWebSocketUrl()
          );

        websocketRef.current =
          websocket;

        websocket.onopen =
          () => {
            if (!active) {
              return;
            }

            setConnectionStatus(
              "CONNECTED"
            );
          };

        websocket.onmessage =
          (event) => {
            if (!active) {
              return;
            }

            try {
              const payload =
                JSON.parse(
                  String(event.data)
                ) as JsonObject;

              setLatestEvent(
                payload
              );

              const eventType =
                payload.event_type;

              if (
                eventType
                === "dashboard_snapshot"
                && isObject(
                  payload.data
                )
              ) {
                setLiveSnapshot(
                  payload.data
                );
              }

              if (
                eventType
                === "dashboard_updated"
              ) {
                if (
                  isObject(
                    payload.data
                  )
                ) {
                  setLiveSnapshot(
                    payload.data
                  );
                }

                void loadDashboard();
              }

              setLastUpdated(
                new Date()
              );
            } catch {
              setError(
                "El WebSocket envió un mensaje inválido."
              );
            }
          };

        websocket.onerror =
          () => {
            if (!active) {
              return;
            }

            setConnectionStatus(
              "ERROR"
            );
          };

        websocket.onclose =
          () => {
            if (!active) {
              return;
            }

            setConnectionStatus(
              "DISCONNECTED"
            );

            reconnectTimerRef.current =
              setTimeout(
                connect,
                3000
              );
          };
      }

      connect();

      return () => {
        active = false;

        if (
          reconnectTimerRef.current
        ) {
          clearTimeout(
            reconnectTimerRef.current
          );
        }

        websocketRef.current?.close();
      };
    },
    [loadDashboard]
  );


  const metrics =
    useMemo(
      () =>
        extractMetrics(
          liveSnapshot
        ),
      [liveSnapshot]
    );


  const connectionClasses =
    connectionStatus
    === "CONNECTED"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
      : connectionStatus
        === "CONNECTING"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
        : "border-rose-500/30 bg-rose-500/10 text-rose-300";


  return (
    <main className="min-h-screen bg-[#070b14] text-slate-100">
      <div className="mx-auto max-w-[1600px] px-5 py-6 lg:px-8">
        <header className="rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900 to-cyan-950/40 p-6 shadow-2xl shadow-black/20 lg:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.3em] text-cyan-400">
                ARMS AI
              </p>

              <h1 className="mt-3 text-3xl font-bold tracking-tight text-white md:text-5xl">
                Professional Dashboard
              </h1>

              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400 md:text-base">
                Centro de control del mercado,
                posiciones, riesgo, rendimiento
                y eventos en tiempo real.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <span
                className={`rounded-full border px-4 py-2 text-xs font-semibold ${connectionClasses}`}
              >
                WebSocket:{" "}
                {connectionStatus}
              </span>

              <button
                type="button"
                onClick={
                  () =>
                    void loadDashboard()
                }
                className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-5 py-2.5 text-sm font-semibold text-cyan-200 transition hover:bg-cyan-500/20"
              >
                Actualizar
              </button>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 border-t border-slate-800 pt-5 text-xs text-slate-500">
            <span>
              API: FastAPI V2
            </span>

            <span>
              Mercado: Tiempo real
            </span>

            <span>
              Última actualización:{" "}
              {lastUpdated
                ? lastUpdated
                    .toLocaleTimeString(
                      "es-EC"
                    )
                : "Pendiente"}
            </span>
          </div>
        </header>

        {error && (
          <div className="mt-6 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
            {error}
          </div>
        )}

        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
          {metrics.length > 0 ? (
            metrics.map(
              (metric) => (
                <MetricCard
                  key={metric.label}
                  {...metric}
                />
              )
            )
          ) : (
            <div className="col-span-full rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-10 text-center text-slate-500">
              Esperando métricas del backend.
            </div>
          )}
        </section>


        <section className="mt-6">
          <StrategyIntelligenceCard />
        </section>


        <section className="mt-6 grid gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2">
            <DataPanel
              title="Live Snapshot"
              data={liveSnapshot}
            />
          </div>

          <DataPanel
            title="Último evento WebSocket"
            data={latestEvent}
          />
        </section>

        <section className="mt-6">
          <AccountSelectorCard
            data={
              isObject(
                accountData
              )
                ? {
                    account:
                      String(
                        accountData.account
                      ),

                    balance:
                      Number(
                        accountData.balance
                      ),

                    risk_percent:
                      Number(
                        accountData.risk_percent
                      ),

                    daily_loss_limit:
                      Number(
                        accountData.daily_loss_limit
                      ),

                    max_drawdown:
                      Number(
                        accountData.max_drawdown
                      ),
                  }
                : null
            }

            onChangeAccount={
              handleChangeAccount
            }
          />
        </section>



        <section className="mt-6">
          <AccountOverviewCard
            data={
              isObject(
                liveSnapshot?.account_state
              )
                ? {
                    balance:
                      Number(
                        liveSnapshot.account_state.balance
                      ),

                    equity:
                      Number(
                        liveSnapshot.account_state.equity
                      ),

                    daily_pnl:
                      Number(
                        liveSnapshot.account_state.daily_pnl
                      ),

                    drawdown:
                      Number(
                        liveSnapshot.account_state.drawdown
                      ),

                    open_risk:
                      Number(
                        liveSnapshot.account_state.open_risk
                      ),
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <RiskManagementCard
            data={
              isObject(
                liveSnapshot?.account_state
              )
                ? {
                    trading_blocked:
                      Boolean(
                        liveSnapshot.account_state.trading_blocked
                      ),

                    blocking_reasons:
                      Array.isArray(
                        liveSnapshot.account_state.blocking_reasons
                      )
                        ? liveSnapshot.account_state.blocking_reasons.map(
                            String
                          )
                        : [],

                    drawdown:
                      Number(
                        liveSnapshot.account_state.drawdown
                      ),

                    open_risk:
                      Number(
                        liveSnapshot.account_state.open_risk
                      ),

                    daily_loss_used:
                      Number(
                        liveSnapshot.account_state.daily_loss_used
                      ),

                    remaining_daily_loss_capacity:
                      Number(
                        liveSnapshot.account_state.remaining_daily_loss_capacity
                      ),

                    remaining_drawdown_capacity:
                      Number(
                        liveSnapshot.account_state.remaining_drawdown_capacity
                      ),
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <RiskProfileCard
            data={
              isObject(
                riskProfileData
              )
                ? {
                    account:
                      String(
                        riskProfileData.account
                      ),

                    balance:
                      Number(
                        riskProfileData.balance
                      ),

                    risk_percent:
                      Number(
                        riskProfileData.risk_percent
                      ),

                    risk_per_trade:
                      Number(
                        riskProfileData.risk_per_trade
                      ),

                    daily_loss_limit:
                      Number(
                        riskProfileData.daily_loss_limit
                      ),

                    max_drawdown:
                      Number(
                        riskProfileData.max_drawdown
                      ),

                    status:
                      String(
                        riskProfileData.status
                      ),
                  }
                : null
            }
          />
        </section>



        <section className="mt-6">
          <PerformanceAnalyticsCard
            data={
              isObject(
                liveSnapshot?.analytics
              )
                ? {
                    total_trades:
                      Number(
                        liveSnapshot.analytics.total_trades
                      ),

                    winning_trades:
                      Number(
                        liveSnapshot.analytics.winning_trades
                      ),

                    losing_trades:
                      Number(
                        liveSnapshot.analytics.losing_trades
                      ),

                    win_rate:
                      Number(
                        liveSnapshot.analytics.win_rate
                      ),

                    profit_factor:
                      Number(
                        liveSnapshot.analytics.profit_factor
                      ),

                    expectancy:
                      Number(
                        liveSnapshot.analytics.expectancy
                      ),

                    net_profit:
                      Number(
                        liveSnapshot.analytics.net_profit
                      ),

                    average_win:
                      Number(
                        liveSnapshot.analytics.average_win
                      ),

                    average_loss:
                      Number(
                        liveSnapshot.analytics.average_loss
                      ),
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <TradeJournalCard
            data={
              isObject(
                liveSnapshot?.trade_journal_summary
              )
                ? {
                    open_trades:
                      Number(
                        liveSnapshot.trade_journal_summary.open_trades
                      ),

                    closed_trades:
                      Number(
                        liveSnapshot.trade_journal_summary.closed_trades
                      ),

                    winning_trades:
                      Number(
                        liveSnapshot.trade_journal_summary.winning_trades
                      ),

                    losing_trades:
                      Number(
                        liveSnapshot.trade_journal_summary.losing_trades
                      ),

                    total_realized_pnl:
                      Number(
                        liveSnapshot.trade_journal_summary.total_realized_pnl
                      ),

                    win_rate:
                      Number(
                        liveSnapshot.trade_journal_summary.win_rate
                      ),
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <StrategyRankingCard
            data={
              isObject(
                strategyRanking
              )
              ? {
                  ranking:
                    Array.isArray(
                      strategyRanking.ranking
                    )
                    ? strategyRanking.ranking.map(
                        (item) => ({
                          name:
                            String(
                              (item as JsonObject).name
                            ),

                          score:
                            Number(
                              (item as JsonObject).score
                            ),

                          confidence:
                            String(
                              (item as JsonObject).confidence
                            ),

                          status:
                            String(
                              (item as JsonObject).status
                            ),
                        })
                      )
                    : [],
                }
              : null
            }
          />
        </section>


        <section className="mt-6">
          <AIDecisionEngineCard
            data={
              aiDecision
                ? {
                    decision:
                      String(
                        aiDecision.summary ?? "ANALYZE"
                      ),

                    direction:
                      String(
                        aiDecision.risk_level ?? "NEUTRAL"
                      ).toUpperCase(),

                    strategy_id:
                      null,

                    confidence:
                      Number(
                        aiDecision.score ?? 0
                      ),

                    action:
                      String(
                        aiDecision.risk_level ?? "WAIT"
                      ).toUpperCase(),

                    reasons:
                      Array.isArray(
                        aiDecision.recommendations
                      )
                        ? aiDecision.recommendations.map(
                            String
                          )
                        : [],
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <BacktestingAnalyticsCard
            data={
              isObject(
                backtestingDashboard?.performance
              )
                ? {
                    total_runs:
                      Number(
                        backtestingDashboard.performance.total_trades
                      ),

                    total_strategies:
                      isObject(
                        backtestingDashboard.strategy_performance
                      )
                        && isObject(
                          backtestingDashboard.strategy_performance.strategies
                        )
                        ? Object.keys(
                            backtestingDashboard.strategy_performance.strategies
                          ).length
                        : 0,

                    best_strategy:
                      isObject(
                        backtestingDashboard.strategy_performance
                      )
                        && isObject(
                          backtestingDashboard.strategy_performance.best_strategy
                        )
                        ? String(
                            backtestingDashboard.strategy_performance.best_strategy.strategy_name
                          )
                        : "N/A",

                    worst_strategy:
                      "N/A",

                    win_rate:
                      Number(
                        backtestingDashboard.performance.win_rate
                      ),

                    profit_factor:
                      isObject(
                        backtestingDashboard.metrics
                      )
                        ? Number(
                            backtestingDashboard.metrics.profit_factor
                          )
                        : 0,

                    max_drawdown:
                      isObject(
                        backtestingDashboard.metrics
                      )
                        ? Number(
                            backtestingDashboard.metrics.max_drawdown
                          )
                        : 0,

                    recommendation:
                      isObject(
                        backtestingDashboard.performance_report
                      )
                        ? String(
                            backtestingDashboard.performance_report.rating
                          )
                        : "N/A",
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <ExecutionApprovalCard
            data={
              executionApproval
                ? {
                    status:
                      String(
                        executionApproval.status
                      ),

                    symbol:
                      String(
                        executionApproval.symbol
                      ),

                    direction:
                      String(
                        executionApproval.direction
                      ),

                    entry:
                      Number(
                        executionApproval.entry
                      ),

                    stop_loss:
                      Number(
                        executionApproval.stop_loss
                      ),

                    take_profit:
                      Number(
                        executionApproval.take_profit
                      ),

                    risk_amount:
                      Number(
                        executionApproval.risk_amount
                      ),

                    confidence:
                      Number(
                        executionApproval.confidence
                      ),

                    validation:
                      Array.isArray(
                        executionApproval.validation
                      )
                        ? executionApproval.validation.map(
                            String
                          )
                        : [],
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <ExecutionSimulatorCard
            data={
              executionSimulation
                ? {
                    status:
                      String(
                        executionSimulation.status
                      ),

                    symbol:
                      String(
                        executionSimulation.symbol
                      ),

                    direction:
                      String(
                        executionSimulation.direction
                      ),

                    entry:
                      Number(
                        executionSimulation.entry
                      ),

                    stop_loss:
                      Number(
                        executionSimulation.stop_loss
                      ),

                    take_profit:
                      Number(
                        executionSimulation.take_profit
                      ),

                    risk_points:
                      Number(
                        executionSimulation.risk_points
                      ),

                    reward_points:
                      Number(
                        executionSimulation.reward_points
                      ),

                    risk_reward:
                      Number(
                        executionSimulation.risk_reward
                      ),

                    contracts:
                      Number(
                        executionSimulation.contracts
                      ),

                    max_loss:
                      Number(
                        executionSimulation.max_loss
                      ),

                    expected_profit:
                      Number(
                        executionSimulation.expected_profit
                      ),
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <ExecutionManagerCard
            data={
              executionPlan
                ? {
                    status:
                      String(
                        executionPlan.status
                      ),

                    symbol:
                      String(
                        executionPlan.symbol
                      ),

                    direction:
                      String(
                        executionPlan.direction
                      ),

                    order_type:
                      String(
                        executionPlan.order_type
                      ),

                    contracts:
                      Number(
                        executionPlan.contracts
                      ),

                    entry:
                      Number(
                        executionPlan.entry
                      ),

                    stop_loss:
                      Number(
                        executionPlan.stop_loss
                      ),

                    take_profit:
                      Number(
                        executionPlan.take_profit
                      ),

                    risk_amount:
                      Number(
                        executionPlan.risk_amount
                      ),

                    validation:
                      Array.isArray(
                        executionPlan.validation
                      )
                        ? executionPlan.validation.map(String)
                        : [],
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <PerformanceIntelligenceCard
            data={
              performanceData
                ? {
                    total_trades:
                      Number(
                        performanceData.total_trades
                      ),

                    winning_trades:
                      Number(
                        performanceData.winning_trades
                      ),

                    losing_trades:
                      Number(
                        performanceData.losing_trades
                      ),

                    win_rate:
                      Number(
                        performanceData.win_rate
                      ),

                    total_profit:
                      Number(
                        performanceData.total_profit
                      ),

                    average_trade:
                      Number(
                        performanceData.average_trade
                      ),

                    best_trade:
                      Number(
                        performanceData.best_trade
                      ),

                    worst_trade:
                      Number(
                        performanceData.worst_trade
                      ),
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <AILearningIntelligenceCard
            data={
              aiLearningData
                ? {
                    trades_analyzed:
                      Number(
                        aiLearningData.trades_analyzed
                      ),

                    win_rate:
                      Number(
                        aiLearningData.win_rate
                      ),

                    total_profit:
                      Number(
                        aiLearningData.total_profit
                      ),

                    performance_level:
                      String(
                        aiLearningData.performance_level
                      ),

                    insights:
                      Array.isArray(
                        aiLearningData.insights
                      )
                        ? aiLearningData.insights.map(String)
                        : [],

                    recommendations:
                      Array.isArray(
                        aiLearningData.recommendations
                      )
                        ? aiLearningData.recommendations.map(String)
                        : [],
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <AIPatternIntelligenceCard
            data={
              aiPatternData
                ? {
                    trades_analyzed:
                      Number(
                        aiPatternData.trades_analyzed
                      ),

                    buy_trades:
                      Number(
                        aiPatternData.buy_trades
                      ),

                    sell_trades:
                      Number(
                        aiPatternData.sell_trades
                      ),

                    average_profit:
                      Number(
                        aiPatternData.average_profit
                      ),

                    average_loss:
                      Number(
                        aiPatternData.average_loss
                      ),

                    best_direction:
                      String(
                        aiPatternData.best_direction
                      ),

                    pattern_quality:
                      String(
                        aiPatternData.pattern_quality
                      ),

                    insights:
                      Array.isArray(
                        aiPatternData.insights
                      )
                        ? aiPatternData.insights.map(String)
                        : [],

                    recommendations:
                      Array.isArray(
                        aiPatternData.recommendations
                      )
                        ? aiPatternData.recommendations.map(String)
                        : [],
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <AITradingMemoryIntelligenceCard
            data={
              tradingMemoryData
                ? {
                    trades_analyzed:
                      Number(tradingMemoryData.trades_analyzed),

                    buy_count:
                      Number(tradingMemoryData.buy_count),

                    sell_count:
                      Number(tradingMemoryData.sell_count),

                    dominant_strategy:
                      String(tradingMemoryData.dominant_strategy),

                    memory_quality:
                      String(tradingMemoryData.memory_quality),

                    winning_patterns:
                      Array.isArray(tradingMemoryData.winning_patterns)
                        ? tradingMemoryData.winning_patterns.map(String)
                        : [],

                    losing_patterns:
                      Array.isArray(tradingMemoryData.losing_patterns)
                        ? tradingMemoryData.losing_patterns.map(String)
                        : [],

                    insights:
                      Array.isArray(tradingMemoryData.insights)
                        ? tradingMemoryData.insights.map(String)
                        : [],

                    recommendations:
                      Array.isArray(tradingMemoryData.recommendations)
                        ? tradingMemoryData.recommendations.map(String)
                        : [],
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <TradeSetupIntelligenceCard
            data={
              isObject(
                tradeSetup
              )
                ? {
                    symbol:
                      String(
                        tradeSetup.symbol
                      ),

                    direction:
                      String(
                        tradeSetup.direction
                      ),

                    entry:
                      Number(
                        tradeSetup.entry
                      ),

                    stop_loss:
                      Number(
                        tradeSetup.stop_loss
                      ),

                    take_profit:
                      Number(
                        tradeSetup.take_profit
                      ),

                    risk_reward:
                      String(
                        tradeSetup.risk_reward
                      ),

                    quality:
                      String(
                        tradeSetup.quality
                      ),

                    validation:
                      Array.isArray(
                        tradeSetup.validation
                      )
                        ? tradeSetup.validation.map(
                            String
                          )
                        : [],
                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <AIDecisionMemoryIntelligenceCard
            data={
              aiDecisionMemoryData
                ? {
                    technical_confidence:
                      Number(
                        aiDecisionMemoryData.technical_confidence
                      ),

                    memory_confidence:
                      Number(
                        aiDecisionMemoryData.memory_confidence
                      ),

                    memory_adjustment:
                      Number(
                        aiDecisionMemoryData.memory_adjustment
                      ),

                    final_confidence:
                      Number(
                        aiDecisionMemoryData.final_confidence
                      ),

                    memory_reliability:
                      String(
                        aiDecisionMemoryData.memory_reliability
                      ),

                    decision:
                      String(
                        aiDecisionMemoryData.decision
                      ),

                    explanation:
                      Array.isArray(
                        aiDecisionMemoryData.explanation
                      )
                        ? aiDecisionMemoryData.explanation.map(String)
                        : [],

                    recommendations:
                      Array.isArray(
                        aiDecisionMemoryData.recommendations
                      )
                        ? aiDecisionMemoryData.recommendations.map(String)
                        : [],

                  }
                : null
            }
          />
        </section>


        <section className="mt-6">
          <ConfidenceFusionIntelligenceCard
            data={
              confidenceFusionData
                ? {
                    technical_score:
                      Number(
                        confidenceFusionData.technical_score
                      ),

                    probability_score:
                      Number(
                        confidenceFusionData.probability_score
                      ),

                    structure_score:
                      Number(
                        confidenceFusionData.structure_score
                      ),

                    risk_score:
                      Number(
                        confidenceFusionData.risk_score
                      ),

                    memory_score:
                      Number(
                        confidenceFusionData.memory_score
                      ),

                    final_confidence:
                      Number(
                        confidenceFusionData.final_confidence
                      ),

                    quality:
                      String(
                        confidenceFusionData.quality
                      ),

                    decision:
                      String(
                        confidenceFusionData.decision
                      ),

                    explanation:
                      Array.isArray(
                        confidenceFusionData.explanation
                      )
                        ? confidenceFusionData.explanation.map(String)
                        : [],

                    recommendations:
                      Array.isArray(
                        confidenceFusionData.recommendations
                      )
                        ? confidenceFusionData.recommendations.map(String)
                        : [],

                  }
                : null
            }
          />
        </section>


        
        <section className="mt-6">

          <AIDecisionEngineV3Card

            data={

              intelligenceDecisionV3Data

                ? {

                    symbol:
                      String(
                        intelligenceDecisionV3Data.symbol
                      ),

                    direction:
                      String(
                        intelligenceDecisionV3Data.direction
                      ),

                    confidence:
                      Number(
                        intelligenceDecisionV3Data.confidence
                      ),

                    quality:
                      String(
                        intelligenceDecisionV3Data.quality
                      ),

                    decision:
                      String(
                        intelligenceDecisionV3Data.decision
                      ),

                    execution_status:
                      String(
                        intelligenceDecisionV3Data.execution_status
                      ),

                    risk_allowed:
                      Boolean(
                        intelligenceDecisionV3Data.risk_allowed
                      ),

                    risk_score:
                      Number(
                        intelligenceDecisionV3Data.risk_score
                      ),

                  }

                : null

            }

          />

        </section>


        <section className="mt-6">

          <TradeExecutionPlanCard

            data={

              intelligenceTradePlanData

                ? {

                    entry:
                      Number(
                        intelligenceTradePlanData.entry
                      ),

                    stop_loss:
                      Number(
                        intelligenceTradePlanData.stop_loss
                      ),

                    take_profit:
                      Number(
                        intelligenceTradePlanData.take_profit
                      ),

                    risk_amount:
                      Number(
                        intelligenceTradePlanData.risk_amount
                      ),

                    reward_amount:
                      Number(
                        intelligenceTradePlanData.reward_amount
                      ),

                    risk_reward_ratio:
                      Number(
                        intelligenceTradePlanData.risk_reward_ratio
                      ),

                    contracts:
                      Number(
                        intelligenceTradePlanData.contracts
                      ),

                    approved:
                      Boolean(
                        intelligenceTradePlanData.approved
                      ),

                  }

                : null

            }

          />

        </section>


        <section className="mt-6">

          <ExecutionPipelineCard

            data={

              executionPipelineData

                ? {

                    trade_id:
                      String(
                        executionPipelineData.trade_id
                      ),

                    symbol:
                      String(
                        executionPipelineData.symbol
                      ),

                    direction:
                      String(
                        executionPipelineData.direction
                      ),

                    execution_status:
                      String(
                        executionPipelineData.execution_status
                      ),

                    journal_status:
                      String(
                        executionPipelineData.journal_status
                      ),

                    message:
                      String(
                        executionPipelineData.message
                      ),

                  }

                : null

            }

          />

        </section>


        <section className="mt-6">
          <DataPanel
            title="Dashboard Widgets"
            data={widgets}
          />
        </section>

        <footer className="mt-8 border-t border-slate-800 py-6 text-center text-xs text-slate-600">
          ARMS AI Dashboard V2 ·
          Market Data · Risk · Performance ·
          Intelligence
        </footer>
      </div>
    </main>
  );
}
