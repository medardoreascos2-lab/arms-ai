"use client";

import {
  useMemo,
  useState,
} from "react";

import {
  askAiCopilot,
  type AiCopilotResult,
} from "@/lib/api";


function parseCsv(
  value: string
): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}


function parseNumericCsv(
  value: string
): number[] {
  return parseCsv(value).map(
    (item) => {
      const parsed = Number(item);

      if (!Number.isFinite(parsed)) {
        throw new Error(
          `Valor numérico inválido: ${item}`
        );
      }

      return parsed;
    }
  );
}


export default function AICopilotCard() {
  const [
    question,
    setQuestion,
  ] = useState("");

  const [
    symbols,
    setSymbols,
  ] = useState("NQ");

  const [
    weights,
    setWeights,
  ] = useState("100");

  const [
    volatility,
    setVolatility,
  ] = useState("0.20");

  const [
    sharpeRatio,
    setSharpeRatio,
  ] = useState("1.00");

  const [
    beta,
    setBeta,
  ] = useState("1.00");

  const [
    drawdown,
    setDrawdown,
  ] = useState("-0.10");

  const [
    result,
    setResult,
  ] = useState<AiCopilotResult | null>(
    null
  );

  const [
    error,
    setError,
  ] = useState("");

  const [
    loading,
    setLoading,
  ] = useState(false);


  const canSubmit = useMemo(
    () =>
      question.trim().length > 0
      && !loading,
    [
      question,
      loading,
    ]
  );


  async function handleAsk() {
    const normalizedQuestion =
      question.trim();

    if (!normalizedQuestion) {
      setError(
        "Escribe una pregunta para ARMS AI."
      );
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const parsedSymbols =
        parseCsv(symbols);

      const parsedWeights =
        parseNumericCsv(weights);

      if (parsedSymbols.length === 0) {
        throw new Error(
          "Debes indicar al menos un activo."
        );
      }

      if (
        parsedSymbols.length
        !== parsedWeights.length
      ) {
        throw new Error(
          "La cantidad de activos y pesos debe coincidir."
        );
      }

      const normalizedWeights =
        parsedWeights.map(
          (value) => value / 100
        );

      const totalWeight =
        normalizedWeights.reduce(
          (total, value) =>
            total + value,
          0
        );

      if (
        Math.abs(
          totalWeight - 1
        ) > 0.000001
      ) {
        throw new Error(
          "Los pesos deben sumar 100%."
        );
      }

      const weightRecord =
        Object.fromEntries(
          parsedSymbols.map(
            (symbol, index) => [
              symbol,
              normalizedWeights[index],
            ]
          )
        );

      const metricValues = {
        volatility:
          Number(volatility),
        sharpe_ratio:
          Number(sharpeRatio),
        beta:
          Number(beta),
        drawdown:
          Number(drawdown),
      };

      for (
        const [
          name,
          value,
        ]
        of Object.entries(
          metricValues
        )
      ) {
        if (!Number.isFinite(value)) {
          throw new Error(
            `Métrica inválida: ${name}`
          );
        }
      }

      const response =
        await askAiCopilot({
          question:
            normalizedQuestion,
          weights:
            weightRecord,
          metrics:
            metricValues,
        });

      setResult(response);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "No fue posible consultar ARMS AI."
      );
    } finally {
      setLoading(false);
    }
  }


  return (
    <section className="rounded-2xl border border-cyan-500/30 bg-slate-900/90 p-6 shadow-lg shadow-black/10">
      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-400">
            Intelligent Assistant
          </p>

          <h2 className="mt-1 text-xl font-bold text-white">
            🧠 ARMS AI Copilot
          </h2>

          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Consulta análisis de riesgo y contexto.
            Esta tarjeta no puede enviar ni ejecutar órdenes.
          </p>
        </div>

        <span className="rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-xs font-semibold text-slate-300">
          ANALYSIS ONLY
        </span>
      </div>


      <div className="mt-6">
        <label
          htmlFor="dashboard-copilot-question"
          className="text-sm font-medium text-slate-200"
        >
          Pregunta para ARMS AI
        </label>

        <textarea
          id="dashboard-copilot-question"
          value={question}
          onChange={(event) =>
            setQuestion(
              event.target.value
            )
          }
          placeholder="Ejemplo: ¿Cómo ves el riesgo de este escenario?"
          rows={4}
          className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950/70 p-4 text-white outline-none transition placeholder:text-slate-600 focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20"
        />
      </div>


      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <label className="text-sm text-slate-300">
          Activos
          <input
            value={symbols}
            onChange={(event) =>
              setSymbols(
                event.target.value
              )
            }
            placeholder="NQ"
            className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 p-3 text-white outline-none focus:border-cyan-400"
          />
          <span className="mt-1 block text-xs text-slate-500">
            Separados por coma.
          </span>
        </label>

        <label className="text-sm text-slate-300">
          Pesos (%)
          <input
            value={weights}
            onChange={(event) =>
              setWeights(
                event.target.value
              )
            }
            placeholder="100"
            className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 p-3 text-white outline-none focus:border-cyan-400"
          />
          <span className="mt-1 block text-xs text-slate-500">
            Deben sumar 100.
          </span>
        </label>
      </div>


      <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <label className="text-sm text-slate-300">
          Volatilidad
          <input
            type="number"
            step="any"
            value={volatility}
            onChange={(event) =>
              setVolatility(
                event.target.value
              )
            }
            className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 p-3 text-white outline-none focus:border-cyan-400"
          />
        </label>

        <label className="text-sm text-slate-300">
          Sharpe
          <input
            type="number"
            step="any"
            value={sharpeRatio}
            onChange={(event) =>
              setSharpeRatio(
                event.target.value
              )
            }
            className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 p-3 text-white outline-none focus:border-cyan-400"
          />
        </label>

        <label className="text-sm text-slate-300">
          Beta
          <input
            type="number"
            step="any"
            value={beta}
            onChange={(event) =>
              setBeta(
                event.target.value
              )
            }
            className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 p-3 text-white outline-none focus:border-cyan-400"
          />
        </label>

        <label className="text-sm text-slate-300">
          Drawdown
          <input
            type="number"
            step="any"
            value={drawdown}
            onChange={(event) =>
              setDrawdown(
                event.target.value
              )
            }
            className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 p-3 text-white outline-none focus:border-cyan-400"
          />
        </label>
      </div>


      <button
        type="button"
        onClick={handleAsk}
        disabled={!canSubmit}
        className="mt-6 rounded-lg bg-cyan-500 px-6 py-3 font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading
          ? "Analizando..."
          : "Preguntar a ARMS AI"}
      </button>


      {error && (
        <div
          role="alert"
          className="mt-5 rounded-xl border border-red-900 bg-red-950/40 p-4 text-sm text-red-200"
        >
          {error}
        </div>
      )}


      {result && (
        <div className="mt-7 space-y-5">
          <div className="rounded-xl border border-slate-700 bg-slate-800/70 p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-cyan-400">
              Respuesta
            </p>

            <p className="mt-3 whitespace-pre-wrap leading-7 text-slate-200">
              {result.content}
            </p>

            <p className="mt-4 text-xs text-slate-500">
              Proveedor: {result.provider}
              {" · "}
              Modelo: {result.model}
            </p>
          </div>


          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-slate-700 bg-slate-800/70 p-5">
              <p className="text-sm text-slate-400">
                Score
              </p>

              <p className="mt-2 text-4xl font-bold text-cyan-400">
                {result.decision.score}
                <span className="text-lg text-slate-500">
                  /100
                </span>
              </p>
            </div>

            <div className="rounded-xl border border-slate-700 bg-slate-800/70 p-5">
              <p className="text-sm text-slate-400">
                Nivel de riesgo
              </p>

              <p className="mt-2 text-2xl font-bold text-white">
                {result.decision.risk_level}
              </p>
            </div>
          </div>


          {result.decision.recommendations.length > 0 && (
            <div className="rounded-xl border border-emerald-900 bg-emerald-950/30 p-5">
              <h3 className="font-semibold text-emerald-300">
                Recomendaciones
              </h3>

              <ul className="mt-3 space-y-2 text-sm text-emerald-100">
                {result.decision.recommendations.map(
                  (recommendation) => (
                    <li
                      key={recommendation}
                      className="flex gap-2"
                    >
                      <span>
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


          {result.decision.alerts.length > 0 && (
            <div className="rounded-xl border border-amber-900 bg-amber-950/30 p-5">
              <h3 className="font-semibold text-amber-300">
                Alertas
              </h3>

              <ul className="mt-3 space-y-2 text-sm text-amber-100">
                {result.decision.alerts.map(
                  (alert) => (
                    <li
                      key={alert}
                      className="flex gap-2"
                    >
                      <span>
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
  );
}
