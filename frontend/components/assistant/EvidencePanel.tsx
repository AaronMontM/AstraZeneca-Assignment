import { useState } from "react";
import {
  ChevronDown,
  Database,
  FileText,
  Wrench,
} from "lucide-react";

import type { EvidenceItem } from "@/types";

interface EvidencePanelProps {
  evidence: EvidenceItem[];
  route?: string;
  decisionSummary?: string;
}

type InvoiceRecord = Record<string, unknown>;

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-IE", {
    style: "currency",
    currency: "EUR",
  }).format(value);
}

function formatToolName(name: string): string {
  return name.replace(/_/g, " ");
}

function formatDate(value: unknown): string {
  if (typeof value !== "string") return "—";

  const parts = value.split("-");
  return parts.length === 3
    ? `${parts[2]}/${parts[1]}/${parts[0]}`
    : value;
}

function SpendSummary({ result }: { result: Record<string, unknown> }) {
  const breakdown = Array.isArray(result.breakdown)
    ? (result.breakdown as Record<string, unknown>[])
    : [];

  const groupedBy =
    typeof result.grouped_by === "string" ? result.grouped_by : "unknown";

  const groupField =
    groupedBy === "vendor"
      ? "vendor_name"
      : groupedBy === "currency"
        ? "currency"
        : groupedBy;

  const groupLabel =
    groupedBy === "vendor"
      ? "Vendor"
      : groupedBy === "currency"
        ? "Currency"
        : groupedBy === "unknown"
          ? "Category"
          : groupedBy.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-xs text-gray-500">Total net spend</p>
          <p className="mt-1 text-lg font-semibold text-gray-900">
            {typeof result.total_eur_spend === "number"
              ? formatCurrency(result.total_eur_spend)
              : "—"}
          </p>
        </div>

        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-xs text-gray-500">Total invoices</p>
          <p className="mt-1 text-lg font-semibold text-gray-900">
            {typeof result.invoice_count === "number"
              ? result.invoice_count.toLocaleString()
              : "—"}
          </p>
        </div>
      </div>

      {breakdown.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Breakdown by {groupLabel.toLowerCase()}
          </h4>

          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-az-50 text-az-800">
                <tr>
                  <th className="px-3 py-2 font-medium">{groupLabel}</th>
                  <th className="px-3 py-2 text-right font-medium">
                    Invoices
                  </th>
                  <th className="px-3 py-2 text-right font-medium">
                    Net spend (EUR)
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-gray-100">
                {breakdown.map((item, index) => {
                  const groupValue = item[groupField];

                  return (
                    <tr
                      key={`${String(groupValue ?? index)}-${index}`}
                      className="even:bg-gray-50/70"
                    >
                      <td className="px-3 py-2 font-medium text-gray-700">
                        {groupValue !== undefined && groupValue !== null
                          ? String(groupValue)
                          : "Not available"}
                      </td>

                      <td className="px-3 py-2 text-right text-gray-600">
                        {typeof item.invoice_count === "number"
                          ? item.invoice_count.toLocaleString()
                          : "—"}
                      </td>

                      <td className="whitespace-nowrap px-3 py-2 text-right font-medium text-gray-700">
                        {typeof item.total_eur_spend === "number"
                          ? formatCurrency(item.total_eur_spend)
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function InvoiceResults({ result }: { result: Record<string, unknown> }) {
  const invoices = Array.isArray(result.invoices)
    ? (result.invoices as InvoiceRecord[])
    : [];

  const totalMatches =
    typeof result.total_matches === "number"
      ? result.total_matches
      : invoices.length;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500">
        <span>
          {totalMatches.toLocaleString()} matching invoices
        </span>
        <span>
          Showing {invoices.length} of {totalMatches}
        </span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full min-w-[680px] text-left text-xs">
          <thead className="bg-az-50 text-az-800">
            <tr>
              <th className="px-3 py-2 font-medium">Invoice</th>
              <th className="px-3 py-2 font-medium">Vendor</th>
              <th className="px-3 py-2 font-medium">Date</th>
              <th className="px-3 py-2 text-right font-medium">
                Amount (EUR)
              </th>
              <th className="px-3 py-2 font-medium">PO</th>
              <th className="px-3 py-2 font-medium">Vendor status</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-gray-100">
            {invoices.map((invoice, index) => (
              <tr
                key={String(invoice.invoice_number ?? index)}
                className="even:bg-gray-50/70"
              >
                <td className="whitespace-nowrap px-3 py-2 font-medium text-gray-800">
                  {String(invoice.invoice_number ?? "—")}
                </td>

                <td className="px-3 py-2 text-gray-700">
                  {String(invoice.vendor_name ?? "—")}
                </td>

                <td className="whitespace-nowrap px-3 py-2 text-gray-600">
                  {formatDate(invoice.invoice_date)}
                </td>

                <td className="whitespace-nowrap px-3 py-2 text-right font-medium text-gray-700">
                  {typeof invoice.EUR_amount === "number"
                    ? formatCurrency(invoice.EUR_amount)
                    : "—"}
                </td>

                <td className="px-3 py-2">
                  {invoice.po_number === null ||
                  invoice.po_number === undefined ? (
                    <span className="rounded-full bg-red-50 px-2 py-1 text-[10px] font-medium text-red-700">
                      Missing
                    </span>
                  ) : (
                    <span className="text-gray-700">
                      {String(invoice.po_number)}
                    </span>
                  )}
                </td>

                <td className="px-3 py-2">
                  <span className="text-gray-600">
                    {String(invoice.vendor_status ?? "—")}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function EvidencePanel({
  evidence,
  route,
  decisionSummary,
}: EvidencePanelProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (evidence.length === 0 && !decisionSummary) {
    return null;
  }

  return (
    <div className="mt-3 w-full max-w-3xl overflow-hidden rounded-xl border border-gray-200 bg-white">
      <button
        type="button"
        onClick={() => setIsOpen((previous) => !previous)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-gray-50"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          <Database size={16} className="text-az-600" />

          <span className="text-xs font-semibold text-gray-700">
            Supporting evidence
          </span>

          <span className="rounded-full bg-az-50 px-2 py-0.5 text-[10px] font-medium text-az-700">
            {evidence.length} {evidence.length === 1 ? "source" : "sources"}
          </span>
        </div>

        <ChevronDown
          size={17}
          className={`text-gray-400 transition-transform ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {isOpen && (
        <div className="space-y-4 border-t border-gray-100 p-4">
          {route && (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Wrench size={14} />
              <span>Execution route:</span>
              <span className="rounded bg-gray-100 px-2 py-1 font-medium text-gray-700">
                {route}
              </span>
            </div>
          )}

          {decisionSummary && (
            <div className="rounded-lg bg-az-50/70 p-3">
              <div className="mb-1 flex items-center gap-2">
                <FileText size={14} className="text-az-600" />
                <span className="text-xs font-semibold text-az-800">
                  Decision summary
                </span>
              </div>

              <p className="text-xs leading-5 text-gray-600">
                {decisionSummary}
              </p>
            </div>
          )}

          {evidence.map((item, index) => (
            <div
              key={`${item.tool}-${index}`}
              className="rounded-lg border border-gray-200 p-3"
            >
              <div className="mb-3 flex items-center gap-2">
                <Database size={14} className="text-gray-400" />

                <span className="text-xs font-semibold capitalize text-gray-700">
                  {formatToolName(item.tool)}
                </span>
              </div>

              {item.tool === "get_spend_summary" ? (
                <SpendSummary result={item.result} />
              ) : Array.isArray(item.result.invoices) ? (
                <InvoiceResults result={item.result} />
              ) : (
                <pre className="max-h-80 overflow-auto rounded-lg bg-gray-50 p-3 text-xs leading-5 text-gray-600">
                  {JSON.stringify(item.result, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}