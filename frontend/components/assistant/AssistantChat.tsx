"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  LoaderCircle,
  Sparkles,
  AlertCircle,
  TrendingUp,
  ShieldCheck,
  FileSearch,
  Plus,
  Wallet,
  Receipt,
  Coins,
  Building2,
} from "lucide-react";

import ChatInput from "./ChatInput";
import ChatMessage from "./ChatMessage";

import {
  askQuestion,
  getConversation,
  getSummary,
  ApiError,
} from "@/lib/api";

import type { SummaryData } from "@/lib/api";
import type { ChatMessage as ChatMessageType } from "@/types";

// ---------------------------------------------------------
// Suggested questions
// ---------------------------------------------------------

const suggestions = [
  {
    title: "Spend overview",
    description:
      "Explore total company spending, monthly trends and vendor distribution.",
    question: "What is our total net spend and how is it distributed?",
    icon: TrendingUp,
  },
  {
    title: "Compliance checks",
    description:
      "Identify invoices with potential procurement policy violations.",
    question: "Find invoices with missing purchase orders.",
    icon: ShieldCheck,
  },
  {
    title: "Vendor analysis",
    description:
      "Investigate suppliers and identify the highest spending vendors.",
    question: "Which vendors have the highest total net spend?",
    icon: FileSearch,
  },
];

// ---------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------

function formatEUR(value: number): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-GB").format(value);
}

function formatStatus(status: string): string {
  return status
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

// ---------------------------------------------------------
// Summary panel
// ---------------------------------------------------------

function SummaryPanel({
  summary,
  isLoading,
}: {
  summary: SummaryData | null;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="shrink-0 border-b border-gray-200/80 bg-white px-5 py-4 sm:px-8">
        <div className="mx-auto grid w-full max-w-5xl grid-cols-2 gap-3 lg:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <div
              key={item}
              className="h-20 animate-pulse rounded-xl border border-gray-100 bg-gray-50"
            />
          ))}
        </div>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="shrink-0 border-b border-gray-200/80 bg-white px-5 py-4 sm:px-8">
      <div className="mx-auto w-full max-w-5xl">
        {/* Main indicators */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {/* Total spend */}
          <div className="rounded-xl border border-az-100 bg-az-50/60 p-3.5">
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white text-az-600">
                <Wallet size={15} />
              </div>

              <span className="text-[11px] font-medium text-gray-500">
                Total Net Spend
              </span>
            </div>

            <p className="text-lg font-semibold tracking-tight text-gray-900">
              {formatEUR(summary.total_net_spend_eur)}
            </p>
          </div>

          {/* Invoice count */}
          <div className="rounded-xl border border-gray-200 bg-white p-3.5">
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-az-50 text-az-600">
                <Receipt size={15} />
              </div>

              <span className="text-[11px] font-medium text-gray-500">
                Total Invoices
              </span>
            </div>

            <p className="text-lg font-semibold tracking-tight text-gray-900">
              {formatNumber(summary.invoice_count)}
            </p>
          </div>

          {/* Currency breakdown */}
          <div className="rounded-xl border border-gray-200 bg-white p-3.5">
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-az-50 text-az-600">
                <Coins size={15} />
              </div>

              <span className="text-[11px] font-medium text-gray-500">
                Spend by Currency
              </span>
            </div>

            <div className="space-y-1">
              {summary.by_currency.map((item) => (
                <div
                  key={item.currency}
                  className="flex items-center justify-between gap-2 text-xs"
                >
                  <span className="font-medium text-gray-600">
                    {item.currency}
                  </span>

                  <span className="font-semibold text-gray-800">
                    {formatEUR(item.total_eur_spend)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Vendor status breakdown */}
          <div className="rounded-xl border border-gray-200 bg-white p-3.5">
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-az-50 text-az-600">
                <Building2 size={15} />
              </div>

              <span className="text-[11px] font-medium text-gray-500">
                Spend by Vendor Status
              </span>
            </div>

            <div className="space-y-1">
              {summary.by_vendor_status.map((item) => (
                <div
                  key={item.vendor_status}
                  className="flex items-center justify-between gap-2 text-xs"
                >
                  <span className="font-medium text-gray-600">
                    {formatStatus(item.vendor_status)}
                  </span>

                  <span className="font-semibold text-gray-800">
                    {formatEUR(item.total_eur_spend)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------
// Assistant chat
// ---------------------------------------------------------

export default function AssistantChat() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedConversationId = searchParams.get("conversation");

  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [isSummaryLoading, setIsSummaryLoading] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // -------------------------------------------------------
  // Load financial summary
  // -------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function loadSummary() {
      try {
        const data = await getSummary();

        if (!cancelled) {
          setSummary(data);
        }
      } catch {
        if (!cancelled) {
          setSummary(null);
        }
      } finally {
        if (!cancelled) {
          setIsSummaryLoading(false);
        }
      }
    }

    void loadSummary();

    return () => {
      cancelled = true;
    };
  }, []);

  // -------------------------------------------------------
  // Restore conversation from URL
  // -------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function restoreConversation() {
      setError(null);
      setMessages([]);
      setConversationId(null);

      if (!requestedConversationId) {
        setIsRestoring(false);
        return;
      }

      setIsRestoring(true);

      try {
        const conversation = await getConversation(requestedConversationId);

        if (cancelled) return;

        const restoredMessages: ChatMessageType[] =
          conversation.messages
            .filter(
              (message) =>
                message.role === "user" || message.role === "assistant"
            )
            .map((message) => ({
              id: String(message.id),
              role: message.role as "user" | "assistant",
              content: message.content,
              timestamp: new Date(message.created_at),
              evidence: message.evidence ?? undefined,
              toolsUsed: message.tools_used ?? undefined,
              route: message.route ?? undefined,
            }));

        setConversationId(conversation.id);
        setMessages(restoredMessages);
      } catch (err) {
        if (cancelled) return;

        setError(
          err instanceof ApiError
            ? err.message
            : "Could not restore the selected conversation."
        );
      } finally {
        if (!cancelled) {
          setIsRestoring(false);
        }
      }
    }

    void restoreConversation();

    return () => {
      cancelled = true;
    };
  }, [requestedConversationId]);

  // -------------------------------------------------------
  // Scroll to latest message
  // -------------------------------------------------------

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, isLoading, isRestoring]);

  // -------------------------------------------------------
  // Send message
  // -------------------------------------------------------

  async function handleSend(question: string) {
    if (isLoading || isRestoring) return;

    setError(null);
    setIsLoading(true);

    const userMessage: ChatMessageType = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
      timestamp: new Date(),
    };

    setMessages((previous) => [...previous, userMessage]);

    try {
      const response = await askQuestion({
        question,
        conversation_id: conversationId,
      });

      if (response.conversation_id) {
        setConversationId(response.conversation_id);
      }

      const assistantMessage: ChatMessageType = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.answer,
        timestamp: new Date(),
        evidence: response.evidence,
        toolsUsed: response.tools_used,
        route: response.route,
        decisionSummary: response.decision_summary,
      };

      setMessages((previous) => [...previous, assistantMessage]);
    } catch (err) {
      const errorMessage =
        err instanceof ApiError
          ? err.message
          : "An unexpected error occurred while processing your question.";

      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }

  // -------------------------------------------------------
  // Start new conversation
  // -------------------------------------------------------

  function handleNewConversation() {
    if (isLoading || isRestoring) return;

    setMessages([]);
    setConversationId(null);
    setError(null);

    router.replace("/assistant");
  }

  // -------------------------------------------------------
  // Render
  // -------------------------------------------------------

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-background">
      {/* Conversation toolbar */}
      <div className="flex shrink-0 items-center justify-end border-b border-gray-200/80 bg-white px-6 py-3">
        <button
          type="button"
          onClick={handleNewConversation}
          disabled={isLoading || isRestoring}
          className="flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-xs font-medium text-gray-600 transition-colors hover:border-az-200 hover:bg-az-50 hover:text-az-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus size={14} />
          Nueva conversación
        </button>
      </div>

      {/* Financial summary */}
      <SummaryPanel
        summary={summary}
        isLoading={isSummaryLoading}
      />

      {/* Conversation area */}
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-8 sm:px-8">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-7">
          {isRestoring ? (
            <div className="flex items-center justify-center gap-3 py-16 text-sm text-gray-500">
              <LoaderCircle size={18} className="animate-spin text-az-600" />
              Loading conversation...
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center pt-8 sm:pt-12">
              {/* Welcome icon */}
              <div className="relative mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-az-50 text-az-600">
                <Sparkles size={30} strokeWidth={1.7} />

                <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full border-2 border-background bg-gold-400" />
              </div>

              {/* Welcome text */}
              <div className="max-w-2xl text-center">
                <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-az-600">
                  Finance Spend Intelligence
                </p>

                <h2 className="text-2xl font-semibold tracking-tight text-gray-900 sm:text-3xl">
                  Smarter insights.
                  <span className="text-az-600">
                    {" "}Better decisions.
                  </span>
                </h2>

                <p className="mx-auto mt-4 max-w-xl text-sm leading-6 text-gray-500">
                  Your AI-powered finance assistant. Explore company
                  spending, investigate invoices and identify potential
                  procurement compliance issues using your financial data.
                </p>
              </div>

              {/* Suggestions */}
              <div className="mt-10 w-full">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-800">
                    Explore what you can do
                  </h3>

                  <span className="text-xs text-gray-400">
                    Suggested questions
                  </span>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  {suggestions.map((suggestion) => {
                    const Icon = suggestion.icon;

                    return (
                      <button
                        key={suggestion.title}
                        type="button"
                        onClick={() => handleSend(suggestion.question)}
                        disabled={isLoading || isRestoring}
                        className="group rounded-xl border border-gray-200 bg-white p-5 text-left shadow-card transition-all duration-200 hover:-translate-y-1 hover:border-az-200 hover:shadow-elevated disabled:cursor-not-allowed"
                      >
                        <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-az-50 text-az-600 transition-colors group-hover:bg-az-600 group-hover:text-white">
                          <Icon size={20} strokeWidth={1.8} />
                        </div>

                        <h4 className="text-sm font-semibold text-gray-800 group-hover:text-az-700">
                          {suggestion.title}
                        </h4>

                        <p className="mt-2 min-h-[60px] text-xs leading-5 text-gray-500">
                          {suggestion.description}
                        </p>

                        <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-az-600">
                          Ask assistant
                          <span className="transition-transform group-hover:translate-x-1">
                            →
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Disclaimer */}
              <p className="mt-8 text-center text-xs text-gray-400">
                Responses are generated using available financial data and
                procurement policy evidence.
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))
          )}

          {/* Loading state */}
          {isLoading && (
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-az-50 text-az-600">
                <Sparkles size={18} />
              </div>

              <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-card">
                <LoaderCircle
                  size={16}
                  className="animate-spin text-az-600"
                />

                <span className="text-sm text-gray-500">
                  Analyzing financial data...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mx-auto mb-3 flex w-full max-w-4xl items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle size={17} className="mt-0.5 shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {/* Input area */}
      <div className="shrink-0 border-t border-gray-200/80 bg-white px-5 py-4 sm:px-8">
        <div className="mx-auto w-full max-w-4xl">
          <ChatInput
            onSend={handleSend}
            disabled={isLoading || isRestoring}
          />

          <p className="mt-3 text-center text-[10px] leading-4 text-gray-400">
            AI-generated responses may contain errors. Verify important
            financial decisions against supporting evidence.
          </p>
        </div>
      </div>
    </div>
  );
}