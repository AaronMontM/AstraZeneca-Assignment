"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, FileText, Wallet } from "lucide-react";

import { getDashboard } from "@/lib/api";
import type { DashboardData } from "@/types";
import KPICard from "./KPICard";
import AlertsChart from "./AlertsChart";
import ApproverRolesChart from "./ApproverRolesChart";
import MonthlyExpensesChart from "./MonthlyExpensesChart";
import ExpenseDonutChart from "./ExpenseDonutChart";

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-GB").format(value);
}

export default function DashboardContent() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDashboard() {
      try {
        setLoading(true);
        setError(null);

        const result = await getDashboard();
        setData(result);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load dashboard data."
        );
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[300px] items-center justify-center">
        <p className="text-sm text-gray-500">Loading dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-5">
        <p className="font-medium text-red-800">
          Could not load dashboard
        </p>
        <p className="mt-1 text-sm text-red-600">{error}</p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="min-h-screen space-y-6 px-8 py-8 lg:px-10 lg:py-10">
      <section>
        <h2 className="text-lg font-semibold text-gray-900">
          Financial overview
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Overview of invoice activity and procurement alerts.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <KPICard
            title="Total spend"
            value={formatCurrency(data.kpis.total_net_spend_eur)}
            description="Net spend, including credit notes"
            icon={Wallet}
          />

          <KPICard
            title="Total invoices"
            value={formatNumber(data.kpis.invoice_count)}
            description="Invoices in the dataset"
            icon={FileText}
          />

          <KPICard
            title="Invoices with alerts"
            value={formatNumber(data.kpis.invoices_with_alerts)}
            description="Invoices with at least one flagged condition"
            icon={AlertTriangle}
            iconColor="amber"
          />
        </div>
      </section>

      <section>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <AlertsChart
            items={data.alerts.items}
            description={data.alerts.description}
            />

            <ApproverRolesChart
            roles={data.approver_roles.roles}
            rows={data.approver_roles.rows}
            description={data.approver_roles.description}
            />
        </div>
      </section>

      <section>
        <MonthlyExpensesChart data={data.monthly_expenses.items} />
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <ExpenseDonutChart
            title="Expenses by vendor"
            description="Net spend distribution across vendors."
            data={data.expenses_by.vendors}
        />

        <ExpenseDonutChart
            title="Expenses by country"
            description="Net spend distribution across countries."
            data={data.expenses_by.countries}
        />

        <ExpenseDonutChart
            title="Expenses by category"
            description="Net spend distribution across vendor categories."
            data={data.expenses_by.categories}
        />
      </section>
    </div>
  );
}