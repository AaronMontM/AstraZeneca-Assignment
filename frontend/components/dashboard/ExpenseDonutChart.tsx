"use client";

import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import type { ExpenseBreakdown } from "@/types";
import { DONUT_PALETTE } from "./chartColors";

interface ExpenseDonutChartProps {
  title: string;
  description: string;
  data: ExpenseBreakdown[];
}

const euroFormatter = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

const numberFormatter = new Intl.NumberFormat("en-GB");

export default function ExpenseDonutChart({
  title,
  description,
  data,
}: ExpenseDonutChartProps) {
  const totalSpend = data.reduce(
    (sum, item) => sum + item.net_spend_eur,
    0
  );

  const chartData = [...data].sort(
    (a, b) => b.net_spend_eur - a.net_spend_eur
  );

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-3">
        <h2 className="text-base font-semibold text-gray-900">{title}</h2>
        <p className="mt-1 text-sm text-gray-500">{description}</p>
      </div>

      {chartData.length === 0 ? (
        <div className="flex h-64 items-center justify-center text-sm text-gray-500">
          No expense data available.
        </div>
      ) : (
        <>
          <div className="relative h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  dataKey="net_spend_eur"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={68}
                  outerRadius={95}
                  paddingAngle={2}
                  stroke="#ffffff"
                  strokeWidth={2}
                >
                  {chartData.map((item, index) => (
                    <Cell
                      key={item.name}
                      fill={DONUT_PALETTE[index % DONUT_PALETTE.length]}
                    />
                  ))}
                </Pie>

                <Tooltip
                  formatter={(value, _name, item) => [
                    `${euroFormatter.format(Number(value))} · ${numberFormatter.format(item.payload.invoice_count)} invoices`,
                    item.payload.name,
                  ]}
                  contentStyle={{
                    backgroundColor: "#ffffff",
                    borderRadius: "8px",
                    border: "1px solid #e5e7eb",
                    fontSize: "12px",
                    color: "#000000",
                  }}
                  itemStyle={{
                    color: "#000000",
                  }}
                  labelStyle={{
                    color: "#000000",
                    fontWeight: 600,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>

            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-xs font-medium text-gray-500">
                Total spend
              </span>
              <span className="mt-1 text-lg font-semibold text-gray-900">
                {euroFormatter.format(totalSpend)}
              </span>
            </div>
          </div>

          <div className="mt-3 space-y-2">
            {chartData.map((item, index) => {
              const percentage =
                totalSpend !== 0
                  ? (item.net_spend_eur / totalSpend) * 100
                  : 0;

              return (
                <div
                  key={item.name}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <span
                      className="h-3 w-3 shrink-0 rounded-sm"
                      style={{
                        backgroundColor: DONUT_PALETTE[index % DONUT_PALETTE.length],
                      }}
                    />
                    <span className="truncate text-gray-700">
                      {item.name}
                    </span>
                  </div>

                  <span className="shrink-0 font-medium text-gray-900">
                    {percentage.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}