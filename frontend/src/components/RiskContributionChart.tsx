"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type RiskContributionChartProps = {
  contributions: Record<string, number>;
};

export function RiskContributionChart({
  contributions,
}: RiskContributionChartProps) {
  const data = Object.entries(
    contributions
  ).map(([asset, contribution]) => ({
    asset,
    contribution:
      contribution * 100,
  }));

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900">
        Risk Contribution by Asset
      </h3>

      <p className="mt-2 text-sm text-slate-600">
        Porcentaje de riesgo total aportado por cada activo.
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
                `${Number(value).toFixed(0)}%`
              }
            />

            <Tooltip
              formatter={(value) =>
                `${Number(value).toFixed(2)}%`
              }
            />

            <Bar
              dataKey="contribution"
              name="Risk contribution"
              fill="#7c3aed"
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
