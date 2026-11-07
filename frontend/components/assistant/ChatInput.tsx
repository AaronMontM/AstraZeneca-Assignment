"use client";

import { useState } from "react";
import { Send, Database, LoaderCircle } from "lucide-react";

interface ChatInputProps {
  onSend: (question: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({
  onSend,
  disabled = false,
  placeholder = "Ask about company spending, invoices or procurement...",
}: ChatInputProps) {
  const [question, setQuestion] = useState("");

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || disabled) {
      return;
    }

    onSend(trimmedQuestion);
    setQuestion("");
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm transition-all focus-within:border-az-300 focus-within:ring-2 focus-within:ring-az-100">
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={2}
          className="w-full resize-none border-0 bg-transparent px-1 py-1 text-sm leading-6 text-gray-800 outline-none placeholder:text-gray-400 disabled:cursor-not-allowed"
          aria-label="Your question"
        />

        <div className="mt-2 flex items-center justify-between border-t border-gray-100 pt-2">
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <Database size={15} className="text-az-500" />
            <span>Finance data assistant</span>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden text-[11px] text-gray-400 sm:inline">
              Enter to send · Shift + Enter for a new line
            </span>

            <button
              type="submit"
              disabled={disabled || !question.trim()}
              className="flex h-9 w-9 items-center justify-center rounded-lg bg-az-600 text-white shadow-sm transition-all hover:bg-az-700 hover:shadow-md disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400 disabled:shadow-none"
              aria-label={disabled ? "Processing message" : "Send message"}
              title="Send message"
            >
              {disabled ? (
                <LoaderCircle size={18} className="animate-spin" />
              ) : (
                <Send size={17} />
              )}
            </button>
          </div>
        </div>
      </div>
    </form>
  );
}