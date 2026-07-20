"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type BenchmarkComparisonChartProps = {
  portfolioCurve: number[];
  benchmarkCurve: number[];
  benchmarkLabel: string;
};

export function BenchmarkComparisonChart({
  portfolioCurve,
  benchmarkCurve,
  benchmarkLabel,
}: BenchmarkComparisonChartProps) {
  const data = portfolioCurve.map(
    (portfolioValue, index) => ({
      period: index,
      portfolio: portfolioValue * 100,
      benchmark:
        (benchmarkCurve[index] ?? 0) * 100,
    })
  );

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900">
        Portfolio vs {benchmarkLabel}
      </h3>

      <p className="mt-2 text-sm text-slate-600">
        Comparación del crecimiento acumulado.
      </p>

      <div className="mt-5 h-96 w-full">
        <ResponsiveContainer
          width="100%"
          height="100%"
        >
          <LineChart
            data={data}
            margin={{
              top: 10,
              right: 20,
              bottom: 20,
              left: 10,
            }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
            />

            <XAxis
              dataKey="period"
            />

            <YAxis
              tickFormatter={(value) =>
                `${Number(value).toFixed(0)}`
              }
            />

            <Tooltip
              formatter={(value) =>
                `${Number(value).toFixed(2)}`
              }
            />

            <Legend />

            <Line
              type="monotone"
              dataKey="portfolio"
              name="Portfolio"
              stroke="#2563eb"
              strokeWidth={2}
              dot={false}
            />

            <Line
              type="monotone"
              dataKey="benchmark"
              name={benchmarkLabel}
              stroke="#16a34a"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
