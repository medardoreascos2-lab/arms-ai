"use client";

import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type FrontierPoint = {
  expected_return: number;
  volatility: number;
  weights: Record<string, number>;
};

type EfficientFrontierChartProps = {
  points: FrontierPoint[];
};

export function EfficientFrontierChart({
  points,
}: EfficientFrontierChartProps) {
  const data = points.map(
    (point) => ({
      volatility:
        point.volatility * 100,
      expectedReturn:
        point.expected_return * 100,
    })
  );

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900">
        Efficient Frontier
      </h3>

      <p className="mt-2 text-sm text-slate-600">
        Expected return versus portfolio volatility.
      </p>

      <div className="mt-5 h-96 w-full">
        <ResponsiveContainer
          width="100%"
          height="100%"
        >
          <ScatterChart
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
              type="number"
              dataKey="volatility"
              name="Volatility"
              unit="%"
            />

            <YAxis
              type="number"
              dataKey="expectedReturn"
              name="Expected return"
              unit="%"
            />

            <Tooltip
              cursor={{
                strokeDasharray: "3 3",
              }}
              formatter={(
                value
              ) => `${Number(value).toFixed(2)}%`}
            />

            <Scatter
              data={data}
              fill="#2563eb"
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
