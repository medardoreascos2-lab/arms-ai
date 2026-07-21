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

type RollingAnalyticsChartProps = {
  rollingVolatility: number[];
  rollingSharpe: number[];
  rollingDrawdown: number[];
};

export function RollingAnalyticsChart({
  rollingVolatility,
  rollingSharpe,
  rollingDrawdown,
}: RollingAnalyticsChartProps) {
  const length = Math.max(
    rollingVolatility.length,
    rollingSharpe.length,
    rollingDrawdown.length
  );

  const data = Array.from(
    { length },
    (_, index) => ({
      period: index,
      volatility:
        (rollingVolatility[index] ?? 0) * 100,
      sharpe:
        rollingSharpe[index] ?? 0,
      drawdown:
        (rollingDrawdown[index] ?? 0) * 100,
    })
  );

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900">
        Rolling Analytics
      </h3>

      <p className="mt-2 text-sm text-slate-600">
        Evolución móvil de volatilidad, Sharpe y drawdown.
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

            <YAxis />

            <Tooltip
              formatter={(value, name) => {
                const numberValue =
                  Number(value);

                if (
                  name === "Volatility"
                  || name === "Drawdown"
                ) {
                  return `${numberValue.toFixed(
                    2
                  )}%`;
                }

                return numberValue.toFixed(2);
              }}
            />

            <Legend />

            <Line
              type="monotone"
              dataKey="volatility"
              name="Volatility"
              stroke="#2563eb"
              strokeWidth={2}
              dot={false}
            />

            <Line
              type="monotone"
              dataKey="sharpe"
              name="Sharpe"
              stroke="#16a34a"
              strokeWidth={2}
              dot={false}
            />

            <Line
              type="monotone"
              dataKey="drawdown"
              name="Drawdown"
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
