// ---------------------------------------------------------
// AI Assistant
// ---------------------------------------------------------

export interface AskRequest {
  question: string;
  conversation_id: string | null;
}

export interface EvidenceItem {
  tool: string;
  result: Record<string, unknown>;
}

export interface AskResponse {
  answer: string;
  route: string;
  decision_summary: string;
  evidence: EvidenceItem[];
  tools_used: string[];
  conversation_id: string | null;
}

// ---------------------------------------------------------
// Chat interface
// ---------------------------------------------------------

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  evidence?: EvidenceItem[];
  toolsUsed?: string[];
  route?: string;
  decisionSummary?: string;
}

// ---------------------------------------------------------
// Conversation history
// ---------------------------------------------------------

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface StoredMessage {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
  route: string | null;
  evidence: EvidenceItem[] | null;
  tools_used: string[] | null;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: StoredMessage[];
}

export interface DeleteConversationResponse {
  message: string;
}

// ---------------------------------------------------------
// Financial summary
// ---------------------------------------------------------

export interface CurrencyBreakdown {
  currency: string;
  total_spend: number;
  invoice_count: number;
}

export interface StatusBreakdown {
  vendor_status: string;
  total_spend: number;
  invoice_count: number;
}

export interface SpendSummary {
  total_net_spend_eur: number;
  invoice_count: number;
  by_currency: Record<string, unknown>[];
  by_vendor_status: Record<string, unknown>[];
}

// ---------------------------------------------------------
// Dashboard
// ---------------------------------------------------------

export interface AlertItem {
  key: string;
  label: string;
  count: number;
}

export interface ApproverRoleRow {
  approved_by: string;
  counts: Record<string, number>;
}

export interface MonthlyExpense {
  month: string;
  net_spend_eur: number;
  invoice_count: number;
  share_percent: number;
}

export interface ExpenseBreakdown {
  name: string;
  net_spend_eur: number;
  invoice_count: number;
}

export interface DashboardData {
  kpis: {
    total_net_spend_eur: number;
    invoice_count: number;
    invoices_with_alerts: number;
  };

  alerts: {
    description: string;
    items: AlertItem[];
  };

  approver_roles: {
    description: string;
    roles: string[];
    rows: ApproverRoleRow[];
  };

  monthly_expenses: {
    basis: string;
    measure: string;
    total_net_spend_eur: number;
    items: MonthlyExpense[];
  };

  expenses_by: {
    vendors: ExpenseBreakdown[];
    countries: ExpenseBreakdown[];
    categories: ExpenseBreakdown[];
  };
}

// ---------------------------------------------------------
// Invoice data explorer
// ---------------------------------------------------------

export interface InvoiceRecord {
  invoice_number: string;
  invoice_date: string;
  invoice_quarter: string;
  invoice_week: string;
  invoice_month: string;
  invoice_day_of_month: number;
  invoice_day_of_week: string;
  invoice_on_weekend: boolean;

  vendor_id: string;
  vendor_name: string;
  vendor_country: string;
  vendor_category: string;
  vendor_status: string;

  description: string;

  amount: number;
  currency: string;
  EUR_amount: number;

  credit_note: boolean;

  cost_center: string;
  po_number: string | null;
  approved_by: string | null;
  missing_approver: boolean;
  required_approver: string | null;

  requires_po: boolean;
  missing_po: boolean;
  maverick_spend: boolean;
  requires_PE_escalation: boolean;
}

export interface InvoiceFilterOptions {
  vendor_statuses: string[];
  countries: string[];
  categories: string[];
  currencies: string[];
  cost_centers: string[];
}

export interface InvoiceFilters {
  page?: number;
  page_size?: number;
  search?: string;
  search_by?:
    | "invoice_number"
    | "vendor_name"
    | "vendor_id"
    | "cost_center"
    | "vendor_country"
    | "po_number"
    | "approved_by";
  vendor_status?: string;
  vendor_country?: string;
  vendor_category?: string;
  currency?: string;
  cost_center?: string;
  missing_po?: boolean;
  missing_approver?: boolean;
  maverick_spend?: boolean;
  requires_pe_escalation?: boolean;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

export interface InvoiceResponse {
  items: InvoiceRecord[];
  pagination: {
    page: number;
    page_size: number;
    total_records: number;
    total_pages: number;
  };
  filters: InvoiceFilters;
}