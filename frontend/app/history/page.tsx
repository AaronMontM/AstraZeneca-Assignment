"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  MessageSquare,
  Trash2,
  Clock,
  RefreshCw,
  Search,
  ArrowUpRight,
} from "lucide-react";

import { getConversations, deleteConversation, ApiError } from "@/lib/api";
import type { ConversationSummary } from "@/types";

export default function HistoryPage() {
  const router = useRouter();

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function loadConversations() {
    setIsLoading(true);
    setError(null);

    try {
      const data = await getConversations(50);
      setConversations(data);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not load conversation history."
      );
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadConversations();
  }, []);

  async function handleDelete(
    event: React.MouseEvent<HTMLButtonElement>,
    conversationId: string
  ) {
    event.stopPropagation();

    const confirmed = window.confirm(
      "Are you sure you want to delete this conversation?"
    );

    if (!confirmed) return;

    setDeletingId(conversationId);
    setError(null);

    try {
      await deleteConversation(conversationId);

      setConversations((current) =>
        current.filter((conversation) => conversation.id !== conversationId)
      );
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not delete the conversation."
      );
    } finally {
      setDeletingId(null);
    }
  }

  function handleOpenConversation(conversationId: string) {
    router.push(
      `/assistant?conversation=${encodeURIComponent(conversationId)}`
    );
  }

  const filteredConversations = conversations.filter((conversation) =>
    (conversation.title ?? "Untitled conversation")
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  function formatDate(dateString: string) {
    return new Date(dateString).toLocaleString(undefined, {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <div className="min-h-screen px-8 py-8">
      <div className="mx-auto w-full max-w-7xl space-y-6">
        <header>
          <h1 className="text-2xl font-semibold text-gray-900">
            Recent History
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Browse and manage your previous conversations.
          </p>
        </header>

        <section className="rounded-xl border border-gray-200 bg-white">
          <div className="flex flex-col gap-4 border-b border-gray-100 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold text-gray-900">
                Conversations
              </h2>
              <p className="mt-1 text-xs text-gray-500">
                {conversations.length}{" "}
                {conversations.length === 1
                  ? "conversation"
                  : "conversations"}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <div className="relative w-full sm:w-72">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search conversations..."
                  className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-3 text-sm outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                />
              </div>

              <button
                onClick={() => void loadConversations()}
                disabled={isLoading}
                title="Refresh history"
                className="rounded-lg border border-gray-200 p-2 text-gray-500 transition hover:bg-gray-50 disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
                />
              </button>
            </div>
          </div>

          {error && (
            <div className="m-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {isLoading ? (
            <div className="flex items-center justify-center gap-2 p-12 text-sm text-gray-500">
              <RefreshCw className="h-4 w-4 animate-spin" />
              Loading conversations...
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
              <div className="mb-3 rounded-full bg-gray-100 p-4">
                <MessageSquare className="h-6 w-6 text-gray-400" />
              </div>

              <h3 className="text-sm font-medium text-gray-900">
                {search
                  ? "No matching conversations"
                  : "No conversations yet"}
              </h3>

              <p className="mt-1 max-w-sm text-sm text-gray-500">
                {search
                  ? "Try another search term."
                  : "Your previous assistant conversations will appear here."}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {filteredConversations.map((conversation) => (
                <div
                  key={conversation.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleOpenConversation(conversation.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      handleOpenConversation(conversation.id);
                    }
                  }}
                  className="flex cursor-pointer items-center justify-between gap-4 px-5 py-4 transition hover:bg-gray-50"
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <div className="mt-1 rounded-lg bg-az-50 p-2">
                      <MessageSquare className="h-4 w-4 text-az-600" />
                  </div>

                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-medium text-gray-900">
                        {conversation.title || "Untitled conversation"}
                      </h3>

                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDate(conversation.updated_at)}
                        </span>

                        <span>
                          {conversation.message_count}{" "}
                          {conversation.message_count === 1
                            ? "message"
                            : "messages"}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      onClick={(event) =>
                        void handleDelete(event, conversation.id)
                      }
                      disabled={deletingId === conversation.id}
                      title="Delete conversation"
                      className="rounded-lg p-2 text-gray-400 transition hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>

                    <ArrowUpRight className="h-4 w-4 text-gray-400" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}