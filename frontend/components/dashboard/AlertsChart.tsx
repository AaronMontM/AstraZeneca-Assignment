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

import type { AlertItem } from "@/types";
import { RDPU_PALETTE } from "./chartColors";

interface AlertsChartProps {
  items: AlertItem[];
  description: string;
}

export default function AlertsChart({
  items,
  description,
}: AlertsChartProps) {
  const sortedItems = [...items].sort(
    (a, b) => b.count - a.count
  );

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-5">
        <h3 className="text-base font-semibold text-gray-900">
          Procurement alerts
        </h3>
        <p className="mt-1 text-sm text-gray-500">{description}</p>
      </div>

      <div className="h-[300px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={sortedItems}
            layout="vertical"
            margin={{ top: 5, right: 20, bottom: 5, left: 10 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              horizontal={false}
              stroke="#e5e7eb"
            />

            <XAxis
              type="number"
              allowDecimals={false}
              tick={{ fontSize: 12, fill: "#6b7280" }}
              axisLine={false}
              tickLine={false}
            />

            <YAxis
              type="category"
              dataKey="label"
              width={155}
              tick={{ fontSize: 12, fill: "#4b5563", fontWeight: 600 }}
              axisLine={false}
              tickLine={false}
            />

            <Tooltip
              cursor={{ fill: "#f5f3ff" }}
              contentStyle={{
                borderRadius: "8px",
                border: "1px solid #e5e7eb",
                fontSize: "12px",
              }}
            />

            <Bar
              dataKey="count"
              name="Invoices"
              radius={[0, 5, 5, 0]}
              barSize={22}
            >
              {sortedItems.map((item, index) => (
                <Cell
                  key={item.key}
                  fill={RDPU_PALETTE[index % RDPU_PALETTE.length]}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}