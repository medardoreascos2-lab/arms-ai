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
  type JsonObject,
  type JsonValue,
} from "@/lib/dashboardApi";


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


  const loadDashboard =
    useCallback(
      async () => {
        try {
          setError("");

          const [
            liveResult,
            widgetResult,
          ] = await Promise.all(
            [
              getDashboardLive(),
              getDashboardWidgets(),
            ]
          );

          setLiveSnapshot(
            liveResult
          );

          setWidgets(
            widgetResult
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
