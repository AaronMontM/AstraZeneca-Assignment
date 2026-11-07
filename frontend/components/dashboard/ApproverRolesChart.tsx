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

import type { ApproverRoleRow } from "@/types";
import { RDPU_PALETTE } from "./chartColors";

interface ApproverRolesChartProps {
  roles: string[];
  rows: ApproverRoleRow[];
  description: string;
}

export default function ApproverRolesChart({
  roles,
  rows,
  description,
}: ApproverRolesChartProps) {
  const sortedRows = [...rows].sort((a, b) => {
    const totalA = Object.values(a.counts).reduce(
      (sum, count) => sum + count,
      0
    );
    const totalB = Object.values(b.counts).reduce(
      (sum, count) => sum + count,
      0
    );

    return totalB - totalA;
  });

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-5">
        <h3 className="text-base font-semibold text-gray-900">
          Approver roles
        </h3>
        <p className="mt-1 text-sm text-gray-500">{description}</p>
      </div>

      <div className="h-[300px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={sortedRows}
            margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="#e5e7eb"
            />

            <XAxis
              dataKey="approved_by"
              tick={{ fontSize: 12, fill: "#4b5563", fontWeight: 600 }}
              axisLine={false}
              tickLine={false}
            />

            <YAxis
              allowDecimals={false}
              tick={{ fontSize: 12, fill: "#6b7280" }}
              axisLine={false}
              tickLine={false}
            />

            <Tooltip
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

            <Legend
              formatter={(value) => (
                <span className="text-gray-900">{value}</span>
              )}
              wrapperStyle={{ fontSize: "12px", paddingTop: "12px" }}
            />

            {roles.map((role, index) => (
              <Bar
                key={role}
                dataKey={`counts.${role}`}
                name={role}
                stackId="approvers"
                fill={RDPU_PALETTE[index % RDPU_PALETTE.length]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}