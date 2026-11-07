"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { MonthlyExpense } from "@/types";
import { RDPU_PALETTE } from "./chartColors";

interface MonthlyExpensesChartProps {
  data: MonthlyExpense[];
}

const euroFormatter = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

const monthOrder = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export default function MonthlyExpensesChart({
  data,
}: MonthlyExpensesChartProps) {

  const sortedData = [...data].sort(
    (a, b) => monthOrder.indexOf(a.month) - monthOrder.indexOf(b.month)
  );

  const sortedBySpend = [...sortedData].sort(
    (a, b) => a.net_spend_eur - b.net_spend_eur
  );

  const minPaletteIndex = 0;

  const maxPaletteIndex = 6;
  
  const colorByMonth = new Map(
    sortedBySpend.map((item, index) => {
      const paletteIndex =
        maxPaletteIndex -
        Math.round(
          (index / Math.max(sortedBySpend.length - 1, 1)) *
            (maxPaletteIndex - minPaletteIndex)
        );

      return [item.month, RDPU_PALETTE[paletteIndex]];
    })
  );

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-5">
        <h2 className="text-base font-semibold text-gray-900">
          Monthly expenses
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Net spend by invoice month, including credit notes.
        </p>
      </div>

      {sortedData.length === 0 ? (
        <div className="flex h-72 items-center justify-center text-sm text-gray-500">
          No monthly expense data available.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            data={sortedData}
            margin={{ top: 10, right: 12, left: 8, bottom: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="#e5e7eb"
            />

            <XAxis
              dataKey="month"
              tick={{ fontSize: 12, fill: "#4b5563", fontWeight: 600 }}
              axisLine={false}
              tickLine={false}
            />

            <YAxis
              tickFormatter={(value: number) =>
                new Intl.NumberFormat("en-GB", {
                  notation: "compact",
                  maximumFractionDigits: 1,
                }).format(value)
              }
              tick={{ fontSize: 11, fill: "#6b7280" }}
              axisLine={false}
              tickLine={false}
              width={55}
            />

            <Tooltip
              cursor={{ fill: "#f5f3ff" }}
              formatter={(value, _name, item) => [
                `${euroFormatter.format(Number(value))} (${item.payload.share_percent.toFixed(1)}%)`,
                "Net spend",
              ]}
              labelFormatter={(label) => String(label)}
              contentStyle={{
                borderRadius: "8px",
                border: "1px solid #e5e7eb",
                fontSize: "12px",
              }}
            />

            <Bar
              dataKey="net_spend_eur"
              name="Net spend"
              radius={[5, 5, 0, 0]}
              maxBarSize={42}
            >
              {sortedData.map((item) => (
                <Cell
                  key={item.month}
                  fill={colorByMonth.get(item.month) ?? RDPU_PALETTE[4]}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}