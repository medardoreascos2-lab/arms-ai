"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type EquityCurveChartProps = {
  values: number[];
};

export function EquityCurveChart({
  values,
}: EquityCurveChartProps) {
  const data = values.map(
    (value, index) => ({
      period: index,
      value,
    })
  );

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900">
        Equity Curve
      </h3>

      <p className="mt-2 text-sm text-slate-600">
        Evolución histórica del valor del portafolio.
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
              name="Period"
            />

            <YAxis
              tickFormatter={(value) =>
                `$${Number(value).toFixed(0)}`
              }
            />

            <Tooltip
              formatter={(value) =>
                `$${Number(value).toFixed(2)}`
              }
            />

            <Line
              type="monotone"
              dataKey="value"
              stroke="#2563eb"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
