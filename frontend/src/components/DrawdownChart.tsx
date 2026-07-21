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

type DrawdownChartProps = {
  values: number[];
};

export function DrawdownChart({
  values,
}: DrawdownChartProps) {
  const data = values.map(
    (value, index) => ({
      period: index,
      drawdown: value * 100,
    })
  );

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900">
        Drawdown Curve
      </h3>

      <p className="mt-2 text-sm text-slate-600">
        Caída porcentual desde el máximo histórico.
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
                `${Number(value).toFixed(0)}%`
              }
            />

            <Tooltip
              formatter={(value) =>
                `${Number(value).toFixed(2)}%`
              }
            />

            <Line
              type="monotone"
              dataKey="drawdown"
              stroke="#dc2626"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
