import { Bot, User, Wrench } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import EvidencePanel from "./EvidencePanel";
import type { ChatMessage as ChatMessageType } from "@/types";

interface ChatMessageProps {
  message: ChatMessageType;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  const formattedTime = message.timestamp.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div
      className={`flex gap-3 ${
        isUser ? "flex-row-reverse" : "flex-row"
      }`}
    >
      {/* Avatar */}
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
          isUser
            ? "bg-gray-200 text-gray-600"
            : "bg-az-100 text-az-600"
        }`}
      >
        {isUser ? <User size={18} /> : <Bot size={19} />}
      </div>

      {/* Message content */}
      <div
        className={`flex max-w-[85%] min-w-0 flex-col ${
          isUser ? "items-end" : "items-start"
        }`}
      >
        <div className="mb-1 flex items-center gap-2">
          <span className="text-xs font-semibold text-gray-700">
            {isUser ? "You" : "Finance Assistant"}
          </span>

          <span className="text-[11px] text-gray-400">
            {formattedTime}
          </span>
        </div>

        {/* Message bubble */}
        <div
          className={`min-w-0 rounded-xl px-4 py-3 text-sm leading-6 ${
            isUser
              ? "rounded-tr-sm bg-az-600 text-white"
              : "rounded-tl-sm border border-gray-200 bg-white text-gray-700 shadow-card"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words">
              {message.content}
            </p>
          ) : (
            <div
              className="
                min-w-0 break-words
                [&_p]:mb-3
                [&_p:last-child]:mb-0
                [&_ul]:mb-3
                [&_ul]:list-disc
                [&_ul]:pl-5
                [&_ol]:mb-3
                [&_ol]:list-decimal
                [&_ol]:pl-5
                [&_li]:mb-1
                [&_strong]:font-semibold
                [&_h1]:mb-2
                [&_h1]:text-lg
                [&_h1]:font-semibold
                [&_h2]:mb-2
                [&_h2]:mt-4
                [&_h2]:text-base
                [&_h2]:font-semibold
                [&_h3]:mb-2
                [&_h3]:mt-3
                [&_h3]:font-semibold
                [&_code]:rounded
                [&_code]:bg-gray-100
                [&_code]:px-1
                [&_code]:py-0.5
                [&_code]:text-xs
                [&_pre]:my-3
                [&_pre]:overflow-x-auto
                [&_pre]:rounded-lg
                [&_pre]:bg-gray-100
                [&_pre]:p-3
                [&_pre_code]:bg-transparent
                [&_pre_code]:p-0
              "
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  table: ({ children }) => (
                    <div className="my-4 w-full overflow-x-auto rounded-lg border border-gray-200">
                      <table className="w-full border-collapse text-left text-xs">
                        {children}
                      </table>
                    </div>
                  ),
                  thead: ({ children }) => (
                    <thead className="bg-az-50 text-az-800">
                      {children}
                    </thead>
                  ),
                  th: ({ children }) => (
                    <th className="whitespace-nowrap border-b border-gray-200 px-3 py-2.5 font-semibold">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="whitespace-nowrap border-b border-gray-100 px-3 py-2.5 text-gray-600 last:border-b-0">
                      {children}
                    </td>
                  ),
                  tr: ({ children }) => (
                    <tr className="even:bg-gray-50/70">{children}</tr>
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Tools used */}
        {!isUser &&
          message.toolsUsed &&
          message.toolsUsed.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1 text-[11px] text-gray-400">
                <Wrench size={12} />
                <span>Tools used:</span>
              </div>

              {message.toolsUsed.map((tool) => (
                <span
                  key={tool}
                  className="rounded-md border border-gray-200 bg-white px-2 py-1 text-[10px] font-medium text-gray-600"
                >
                  {tool}
                </span>
              ))}
            </div>
          )}

        {/* Supporting evidence */}
        {!isUser && (
          <EvidencePanel
            evidence={message.evidence ?? []}
            route={message.route}
            decisionSummary={message.decisionSummary}
          />
        )}
      </div>
    </div>
  );
}