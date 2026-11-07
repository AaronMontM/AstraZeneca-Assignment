import type {
  AskRequest,
  AskResponse,
  ConversationSummary,
  ConversationDetail,
  DeleteConversationResponse,
  DashboardData,
  InvoiceRecord,
  InvoiceFilterOptions,
  InvoiceFilters,
  InvoiceResponse,
} from "@/types";

// ---------------------------------------------------------
// API configuration
// ---------------------------------------------------------

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

export interface SummaryData {
  total_net_spend_eur: number;
  invoice_count: number;
  by_currency: {
    currency: string;
    invoice_count: number;
    total_eur_spend: number;
  }[];
  by_vendor_status: {
    vendor_status: string;
    invoice_count: number;
    total_eur_spend: number;
  }[];
}

// ---------------------------------------------------------
// API error
// ---------------------------------------------------------

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ---------------------------------------------------------
// Generic HTTP request
// ---------------------------------------------------------

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "Unable to connect to the backend. Please check that the API is running.",
      0
    );
  }

  if (!response.ok) {
    let message = `API request failed (${response.status}).`;

    try {
      const errorData = await response.json();

      if (typeof errorData.detail === "string") {
        message = errorData.detail;
      } else if (errorData.detail) {
        message = JSON.stringify(errorData.detail);
      }
    } catch {
      // Keep the default error message.
    }

    throw new ApiError(message, response.status);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------
// AI Assistant
// ---------------------------------------------------------

export async function askQuestion(
  request: AskRequest
): Promise<AskResponse> {
  return apiRequest<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

// ---------------------------------------------------------
// Conversation history
// ---------------------------------------------------------

export async function getConversations(
  limit: number = 50
): Promise<ConversationSummary[]> {
  return apiRequest<ConversationSummary[]>(
    `/conversations?limit=${limit}`
  );
}

export async function getConversation(
  conversationId: string
): Promise<ConversationDetail> {
  return apiRequest<ConversationDetail>(
    `/conversations/${encodeURIComponent(conversationId)}`
  );
}

export async function deleteConversation(
  conversationId: string
): Promise<DeleteConversationResponse> {
  return apiRequest<DeleteConversationResponse>(
    `/conversations/${encodeURIComponent(conversationId)}`,
    {
      method: "DELETE",
    }
  );
}

// ---------------------------------------------------------
// Dashboard
// ---------------------------------------------------------

export async function getDashboard(): Promise<DashboardData> {
  return apiRequest<DashboardData>("/dashboard");
}

export async function getSummary(): Promise<SummaryData> {
  return apiRequest<SummaryData>("/summary");
}

// ---------------------------------------------------------
// Invoice data explorer
// ---------------------------------------------------------

export async function getInvoices(
  filters: InvoiceFilters = {}
): Promise<InvoiceResponse> {
  const params = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });

  const query = params.toString();

  return apiRequest<InvoiceResponse>(
    `/invoices${query ? `?${query}` : ""}`
  );
}

export async function getInvoiceFilterOptions(): Promise<InvoiceFilterOptions> {
  return apiRequest<InvoiceFilterOptions>("/invoice-filter-options");
}