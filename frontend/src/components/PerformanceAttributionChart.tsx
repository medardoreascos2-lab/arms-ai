"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type PerformanceAttributionChartProps = {
  allocation: Record<string, number>;
  selection: Record<string, number>;
  interaction: Record<string, number>;
};

export function PerformanceAttributionChart({
  allocation,
  selection,
  interaction,
}: PerformanceAttributionChartProps) {
  const assets = Array.from(
    new Set([
      ...Object.keys(allocation),
      ...Object.keys(selection),
      ...Object.keys(interaction),
    ])
  );

  const data = assets.map((asset) => ({
    asset,
    allocation:
      (allocation[asset] ?? 0) * 100,
    selection:
      (selection[asset] ?? 0) * 100,
    interaction:
      (interaction[asset] ?? 0) * 100,
  }));

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900">
        Performance Attribution by Asset
      </h3>

      <p className="mt-2 text-sm text-slate-600">
        Allocation, selection e interaction effect por activo.
      </p>

      <div className="mt-5 h-80 w-full">
        <ResponsiveContainer
          width="100%"
          height="100%"
        >
          <BarChart
            data={data}
            margin={{
              top: 10,
              right: 20,
              bottom: 10,
              left: 20,
            }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
            />

            <XAxis
              dataKey="asset"
            />

            <YAxis
              tickFormatter={(value) =>
                `${Number(value).toFixed(1)}%`
              }
            />

            <Tooltip
              formatter={(value) =>
                `${Number(value).toFixed(2)}%`
              }
            />

            <Legend />

            <Bar
              dataKey="allocation"
              name="Allocation"
              fill="#2563eb"
            />

            <Bar
              dataKey="selection"
              name="Selection"
              fill="#16a34a"
            />

            <Bar
              dataKey="interaction"
              name="Interaction"
              fill="#f59e0b"
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
