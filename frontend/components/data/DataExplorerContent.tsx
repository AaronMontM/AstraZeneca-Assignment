"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  Search,
  SlidersHorizontal,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
} from "lucide-react";

import { getInvoices, getInvoiceFilterOptions, ApiError } from "@/lib/api";
import type { InvoiceFilters, InvoiceFilterOptions, InvoiceRecord } from "@/types";

// ---------------------------------------------------------
// Configuration
// ---------------------------------------------------------

const PAGE_SIZE = 10;

type BooleanFilter = "" | "true" | "false";

interface FilterState {
  vendor_status: string;
  vendor_country: string;
  vendor_category: string;
  currency: string;
  cost_center: string;
  missing_po: BooleanFilter;
  missing_approver: BooleanFilter;
  maverick_spend: BooleanFilter;
  requires_pe_escalation: BooleanFilter;
}

const INITIAL_FILTERS: FilterState = {
  vendor_status: "",
  vendor_country: "",
  vendor_category: "",
  currency: "",
  cost_center: "",
  missing_po: "",
  missing_approver: "",
  maverick_spend: "",
  requires_pe_escalation: "",
};

const euroFormatter = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 2,
});

const numberFormatter = new Intl.NumberFormat("en-GB");

// ---------------------------------------------------------
// Helpers
// ---------------------------------------------------------

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatStatus(value: string): string {
  return value.replaceAll("_", " ");
}

function getInvoiceAlerts(invoice: InvoiceRecord): string[] {
  const alerts: string[] = [];

  if (invoice.missing_po) alerts.push("Missing PO");
  if (invoice.missing_approver) alerts.push("Missing approver");
  if (invoice.maverick_spend) alerts.push("Maverick spend");
  if (invoice.requires_PE_escalation) alerts.push("PE escalation");
  if (invoice.invoice_on_weekend) alerts.push("Weekend");
  if (invoice.credit_note) alerts.push("Credit note");

  return alerts;
}

// ---------------------------------------------------------
// Component
// ---------------------------------------------------------

export default function DataExplorerContent() {
  const [invoices, setInvoices] = useState<InvoiceRecord[]>([]);
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: PAGE_SIZE,
    total_records: 0,
    total_pages: 0,
  });

  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [searchBy, setSearchBy] =
  useState<NonNullable<InvoiceFilters["search_by"]>>("invoice_number");

  const [filterOptions, setFilterOptions] =
  useState<InvoiceFilterOptions | null>(null);

  const [sortBy, setSortBy] =
    useState<InvoiceFilters["sort_by"]>("invoice_date");

  const [sortOrder, setSortOrder] =
    useState<"asc" | "desc">("desc");

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const requestId = useRef(0);

  const [filters, setFilters] = useState<FilterState>(INITIAL_FILTERS);

  const [showFilters, setShowFilters] = useState(true);

  // -------------------------------------------------------
  // Search debounce
  // -------------------------------------------------------

  useEffect(() => {
    const timeout = setTimeout(() => {
      setDebouncedSearch(search.trim());
    }, 300);

    return () => clearTimeout(timeout);
  }, [search]);

  // -------------------------------------------------------
  // Load invoices
  // -------------------------------------------------------

  useEffect(() => {
    const currentRequest = ++requestId.current;

    async function loadInvoices() {
      setIsLoading(true);
      setError(null);

      try {
        const queryFilters: InvoiceFilters = {
            page: pagination.page,
            page_size: PAGE_SIZE,
            search: debouncedSearch,
            search_by: searchBy,
            sort_by: sortBy,
            sort_order: sortOrder,

            vendor_status: filters.vendor_status || undefined,
            vendor_country: filters.vendor_country || undefined,
            vendor_category: filters.vendor_category || undefined,
            currency: filters.currency || undefined,
            cost_center: filters.cost_center || undefined,

            missing_po:
                filters.missing_po === ""
                ? undefined
                : filters.missing_po === "true",

            missing_approver:
                filters.missing_approver === ""
                ? undefined
                : filters.missing_approver === "true",

            maverick_spend:
                filters.maverick_spend === ""
                ? undefined
                : filters.maverick_spend === "true",

            requires_pe_escalation:
                filters.requires_pe_escalation === ""
                ? undefined
                : filters.requires_pe_escalation === "true",
        };

        const response = await getInvoices(queryFilters);

        if (currentRequest !== requestId.current) return;

        setInvoices(response.items);
        setPagination(response.pagination);
      } catch (err) {
        if (currentRequest !== requestId.current) return;

        setError(
          err instanceof ApiError
            ? err.message
            : "Could not load invoice records."
        );
      } finally {
        if (currentRequest === requestId.current) {
          setIsLoading(false);
        }
      }
    }

    void loadInvoices();
  }, [pagination.page, debouncedSearch, searchBy, sortBy, sortOrder, filters]);

  // -------------------------------------------------------
  // Filter
  // -------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function loadFilterOptions() {
        try {
        const options = await getInvoiceFilterOptions();

        if (!cancelled) {
            setFilterOptions(options);
        }
        } catch (err) {
        console.error("Failed to load invoice filter options:", err);
        }
    }

    loadFilterOptions();

    return () => {
        cancelled = true;
    };
    }, []);

  function updateFilter<K extends keyof FilterState>(
    key: K,
    value: FilterState[K]
  ) {
    setFilters((current) => ({
        ...current,
        [key]: value,
    }));

    setPagination((current) => ({
        ...current,
        page: 1,
    }));
  }

  // -------------------------------------------------------
  // Sorting
  // -------------------------------------------------------

  function handleSort(column: string) {
    if (sortBy === column) {
      setSortOrder((current) =>
        current === "asc" ? "desc" : "asc"
      );
    } else {
      setSortBy(column);
      setSortOrder("asc");
    }

    setPagination((current) => ({
      ...current,
      page: 1,
    }));
  }

  function renderSortIcon(column: string) {
    if (sortBy !== column) {
      return <ArrowUpDown className="h-3.5 w-3.5 text-gray-300" />;
    }

    return sortOrder === "asc" ? (
      <ArrowUp className="h-3.5 w-3.5 text-az-600" />
    ) : (
      <ArrowDown className="h-3.5 w-3.5 text-az-600" />
    );
  }

  // -------------------------------------------------------
  // Pagination
  // -------------------------------------------------------

  function changePage(page: number) {
    setPagination((current) => ({
      ...current,
      page,
    }));
  }

  const firstRecord =
    pagination.total_records === 0
      ? 0
      : (pagination.page - 1) * pagination.page_size + 1;

  const lastRecord = Math.min(
    pagination.page * pagination.page_size,
    pagination.total_records
  );

  // -------------------------------------------------------
  // Render
  // -------------------------------------------------------

  return (
    <div className="min-h-screen space-y-6 px-8 py-8 lg:px-10 lg:py-10">
      {/* Page header */}
      <header>
        <h1 className="text-2xl font-semibold text-gray-900">
          Data Explorer
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Explore, search and review invoice records.
        </p>
      </header>

      {/* Summary */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-gray-500">
            Total invoices
          </p>
          <p className="mt-2 text-2xl font-semibold text-gray-900">
            {numberFormatter.format(pagination.total_records)}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            Records available in the dataset
          </p>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-gray-500">
            Displayed records
          </p>
          <p className="mt-2 text-2xl font-semibold text-gray-900">
            {invoices.length}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            Current page
          </p>
        </div>
      </section>

      {/* Invoice table */}
      <section className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        {/* Toolbar */}
        <div className="space-y-5 border-b border-gray-100 p-5">
            {/* Header and search */}
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                <h2 className="text-base font-semibold text-gray-900">
                    Invoice records
                </h2>
                <p className="mt-1 text-xs text-gray-500">
                    Search and inspect financial transactions.
                </p>
                </div>

                <div className="flex flex-col gap-2 sm:flex-row">
                <select
                    value={searchBy}
                    onChange={(event) => {
                    setSearchBy(
                        event.target.value as NonNullable<
                        InvoiceFilters["search_by"]
                        >
                    );
                    setPagination((current) => ({
                        ...current,
                        page: 1,
                    }));
                    }}
                    className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-az-400 focus:ring-2 focus:ring-az-100"
                    aria-label="Search field"
                >
                    <option value="invoice_number">Invoice number</option>
                    <option value="vendor_name">Vendor name</option>
                    <option value="vendor_id">Vendor ID</option>
                    <option value="cost_center">Cost center</option>
                    <option value="vendor_country">Country</option>
                    <option value="po_number">PO number</option>
                    <option value="approved_by">Approver</option>
                </select>

                <div className="relative sm:w-64">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                    <input
                    type="text"
                    value={search}
                    onChange={(event) => {
                        setSearch(event.target.value);
                        setPagination((current) => ({
                        ...current,
                        page: 1,
                        }));
                    }}
                    placeholder="Search..."
                    className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-az-400 focus:ring-2 focus:ring-az-100"
                    />
                </div>
                </div>
            </div>

            {/* Filter section header */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-4">
                <button
                type="button"
                onClick={() => setShowFilters((current) => !current)}
                className="flex items-center gap-2 text-sm font-semibold text-gray-800 transition hover:text-az-700"
                >
                <SlidersHorizontal className="h-4 w-4 text-az-600" />
                Filters
                <ChevronDown
                    className={`h-4 w-4 text-gray-400 transition-transform ${
                    showFilters ? "rotate-180" : ""
                    }`}
                />
                </button>

                <button
                type="button"
                onClick={() => {
                    setFilters(INITIAL_FILTERS);
                    setSearch("");
                    setSearchBy("invoice_number");
                    setPagination((current) => ({
                    ...current,
                    page: 1,
                    }));
                }}
                disabled={
                    isLoading &&
                    search === "" &&
                    Object.values(filters).every((value) => value === "")
                }
                className="text-xs font-medium text-az-700 transition hover:text-az-900 disabled:cursor-not-allowed disabled:opacity-40"
                >
                Clear all filters
                </button>
            </div>

            {/* Filter controls */}
            {showFilters && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
                {/* Vendor status */}
                <div>
                    <label className="mb-1.5 block text-xs font-medium text-gray-600">
                    Vendor status
                    </label>
                    <select
                    value={filters.vendor_status}
                    onChange={(event) =>
                        updateFilter("vendor_status", event.target.value)
                    }
                    className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-az-400 focus:ring-2 focus:ring-az-100"
                    >
                    <option value="">All statuses</option>
                    {(filterOptions?.vendor_statuses ?? []).map((value) => (
                        <option key={value} value={value}>
                        {formatStatus(value)}
                        </option>
                    ))}
                    </select>
                </div>

                {/* Country */}
                <div>
                    <label className="mb-1.5 block text-xs font-medium text-gray-600">
                    Country
                    </label>
                    <select
                    value={filters.vendor_country}
                    onChange={(event) =>
                        updateFilter("vendor_country", event.target.value)
                    }
                    className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-az-400 focus:ring-2 focus:ring-az-100"
                    >
                    <option value="">All countries</option>
                    {(filterOptions?.countries ?? []).map((value) => (
                        <option key={value} value={value}>
                        {value}
                        </option>
                    ))}
                    </select>
                </div>

                {/* Vendor category */}
                <div>
                    <label className="mb-1.5 block text-xs font-medium text-gray-600">
                    Vendor category
                    </label>
                    <select
                    value={filters.vendor_category}
                    onChange={(event) =>
                        updateFilter("vendor_category", event.target.value)
                    }
                    className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-az-400 focus:ring-2 focus:ring-az-100"
                    >
                    <option value="">All categories</option>
                    {(filterOptions?.categories ?? []).map((value) => (
                        <option key={value} value={value}>
                        {value}
                        </option>
                    ))}
                    </select>
                </div>

                {/* Currency */}
                <div>
                    <label className="mb-1.5 block text-xs font-medium text-gray-600">
                    Currency
                    </label>
                    <select
                    value={filters.currency}
                    onChange={(event) =>
                        updateFilter("currency", event.target.value)
                    }
                    className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-az-400 focus:ring-2 focus:ring-az-100"
                    >
                    <option value="">All currencies</option>
                    {(filterOptions?.currencies ?? []).map((value) => (
                        <option key={value} value={value}>
                        {value}
                        </option>
                    ))}
                    </select>
                </div>

                {/* Cost center */}
                <div>
                    <label className="mb-1.5 block text-xs font-medium text-gray-600">
                    Cost center
                    </label>
                    <select
                    value={filters.cost_center}
                    onChange={(event) =>
                        updateFilter("cost_center", event.target.value)
                    }
                    className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-az-400 focus:ring-2 focus:ring-az-100"
                    >
                    <option value="">All cost centers</option>
                    {(filterOptions?.cost_centers ?? []).map((value) => (
                        <option key={value} value={value}>
                        {value}
                        </option>
                    ))}
                    </select>
                </div>

                {/* Boolean filters */}
                {(
                    [
                    ["missing_po", "Missing PO"],
                    ["missing_approver", "Missing approver"],
                    ["maverick_spend", "Maverick spend"],
                    ["requires_pe_escalation", "PE escalation"],
                    ] as const
                ).map(([key, label]) => (
                    <div key={key}>
                    <label className="mb-1.5 block text-xs font-medium text-gray-600">
                        {label}
                    </label>
                    <select
                        value={filters[key]}
                        onChange={(event) =>
                        updateFilter(key, event.target.value as BooleanFilter)
                        }
                        className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-az-400 focus:ring-2 focus:ring-az-100"
                    >
                        <option value="">All</option>
                        <option value="true">Yes</option>
                        <option value="false">No</option>
                    </select>
                    </div>
                ))}
                </div>
            )}
            </div>

        {/* Error */}
        {error && (
          <div className="m-5 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1100px] border-collapse text-left">
            <thead className="bg-gray-50">
              <tr>
                {[
                  { label: "Invoice", key: "invoice_number" },
                  { label: "Date", key: "invoice_date" },
                  { label: "Vendor", key: "vendor_name" },
                  { label: "Country", key: null },
                  { label: "Status", key: "vendor_status" },
                  { label: "Amount (EUR)", key: "EUR_amount" },
                  { label: "Cost center", key: "cost_center" },
                  { label: "PO", key: null },
                  { label: "Approver", key: "approved_by" },
                  { label: "Alerts", key: null },
                ].map((column) => (
                  <th
                    key={column.label}
                    className="whitespace-nowrap px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-500"
                  >
                    {column.key ? (
                      <button
                        onClick={() => handleSort(column.key!)}
                        className="flex items-center gap-1.5 transition hover:text-az-700"
                      >
                        {column.label}
                        {renderSortIcon(column.key)}
                      </button>
                    ) : (
                      column.label
                    )}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                <tr>
                  <td colSpan={10} className="p-12 text-center">
                    <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Loading invoices...
                    </div>
                  </td>
                </tr>
              ) : invoices.length === 0 ? (
                <tr>
                  <td
                    colSpan={10}
                    className="p-12 text-center text-sm text-gray-500"
                  >
                    No invoice records found.
                  </td>
                </tr>
              ) : (
                invoices.map((invoice) => {
                  const alerts = getInvoiceAlerts(invoice);

                  return (
                    <tr
                      key={invoice.invoice_number}
                      className="transition hover:bg-az-50/30"
                    >
                      <td className="whitespace-nowrap px-4 py-4 text-sm font-medium text-az-700">
                        {invoice.invoice_number}
                      </td>

                      <td className="whitespace-nowrap px-4 py-4 text-sm text-gray-600">
                        {formatDate(invoice.invoice_date)}
                      </td>

                      <td className="max-w-[200px] truncate px-4 py-4 text-sm font-medium text-gray-900">
                        {invoice.vendor_name}
                      </td>

                      <td className="whitespace-nowrap px-4 py-4 text-sm text-gray-600">
                        {invoice.vendor_country}
                      </td>

                      <td className="whitespace-nowrap px-4 py-4">
                        <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium capitalize text-gray-700">
                          {formatStatus(invoice.vendor_status)}
                        </span>
                      </td>

                      <td className="whitespace-nowrap px-4 py-4 text-sm font-medium text-gray-900">
                        {euroFormatter.format(invoice.EUR_amount)}
                      </td>

                      <td className="whitespace-nowrap px-4 py-4 text-sm text-gray-600">
                        {invoice.cost_center}
                      </td>

                      <td className="whitespace-nowrap px-4 py-4 text-sm text-gray-600">
                        {invoice.po_number || "—"}
                      </td>

                      <td className="whitespace-nowrap px-4 py-4 text-sm text-gray-600">
                        {invoice.approved_by || "—"}
                      </td>

                      <td className="px-4 py-4">
                        <div className="flex max-w-[220px] flex-wrap gap-1.5">
                          {alerts.length > 0 ? (
                            alerts.map((alert) => (
                              <span
                                key={alert}
                                className="whitespace-nowrap rounded-md bg-amber-50 px-2 py-1 text-[10px] font-medium text-amber-700"
                              >
                                {alert}
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-gray-400">
                              None
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex flex-col gap-3 border-t border-gray-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-gray-500">
            Showing{" "}
            <span className="font-medium text-gray-700">
              {firstRecord}–{lastRecord}
            </span>{" "}
            of{" "}
            <span className="font-medium text-gray-700">
              {numberFormatter.format(pagination.total_records)}
            </span>{" "}
            invoices
          </p>

          <div className="flex items-center gap-2">
            <button
              onClick={() => changePage(pagination.page - 1)}
              disabled={pagination.page <= 1 || isLoading}
              className="rounded-lg border border-gray-200 p-2 text-gray-600 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>

            <span className="px-2 text-xs font-medium text-gray-600">
              Page {pagination.page} of {pagination.total_pages}
            </span>

            <button
              onClick={() => changePage(pagination.page + 1)}
              disabled={
                pagination.page >= pagination.total_pages || isLoading
              }
              className="rounded-lg border border-gray-200 p-2 text-gray-600 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}