"use client";

import { useState, useRef, useEffect } from "react";
import { useApi } from "./api-context";

interface Message {
  role: "user" | "assistant";
  content: string;
  status?: "pending" | "streaming" | "completed" | "failed";
}

export function PolicyChat() {
  const { baseUrl } = useApi();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setIsLoading(true);

    // Add user message
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

    // Add pending assistant message
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", status: "pending" },
    ]);

    try {
      const res = await fetch(`${baseUrl}/demo/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userMessage }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let fullContent = "";

      // Update to streaming status
      setMessages((prev) => {
        const newMessages = [...prev];
        const lastIndex = newMessages.length - 1;
        if (newMessages[lastIndex]?.role === "assistant") {
          newMessages[lastIndex] = {
            ...newMessages[lastIndex],
            status: "streaming",
          };
        }
        return newMessages;
      });

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === "output") {
                fullContent += data.content;
                setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastIndex = newMessages.length - 1;
                  if (newMessages[lastIndex]?.role === "assistant") {
                    newMessages[lastIndex] = {
                      role: "assistant",
                      content: fullContent,
                      status: "streaming",
                    };
                  }
                  return newMessages;
                });
              } else if (data.type === "error") {
                setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastIndex = newMessages.length - 1;
                  if (newMessages[lastIndex]?.role === "assistant") {
                    newMessages[lastIndex] = {
                      role: "assistant",
                      content: `Error: ${data.content}`,
                      status: "failed",
                    };
                  }
                  return newMessages;
                });
              } else if (data.type === "done") {
                setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastIndex = newMessages.length - 1;
                  if (newMessages[lastIndex]?.role === "assistant") {
                    newMessages[lastIndex] = {
                      ...newMessages[lastIndex],
                      status: data.returncode === 0 ? "completed" : "failed",
                    };
                  }
                  return newMessages;
                });
              }
            } catch (parseErr) {
              // Ignore parse errors for incomplete chunks
            }
          }
        }
      }

      setIsLoading(false);
    } catch (err) {
      setMessages((prev) => {
        const newMessages = [...prev];
        const lastIndex = newMessages.length - 1;
        if (newMessages[lastIndex]?.role === "assistant") {
          newMessages[lastIndex] = {
            role: "assistant",
            content: `Error: ${err instanceof Error ? err.message : "Request failed"}`,
            status: "failed",
          };
        }
        return newMessages;
      });
      setIsLoading(false);
    }
  };

  const exampleQuestions = [
    "How much would it cost to set the UK basic income tax rate to 19p?",
    "What would happen if we doubled child benefit?",
    "How would a £15,000 personal allowance affect different income groups?",
  ];

  return (
    <div className="border border-[var(--color-border)] rounded-xl overflow-hidden bg-white flex flex-col h-[600px]">
      {/* Header */}
      <div className="p-4 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[var(--color-pe-green)] animate-pulse" />
          <span className="text-sm font-medium text-[var(--color-text-primary)]">
            Policy analyst
          </span>
          <span className="text-xs text-[var(--color-text-muted)] ml-auto">
            Powered by Claude Code
          </span>
        </div>
        <p className="text-xs text-[var(--color-text-muted)] mt-1">
          Ask natural language questions about UK or US tax and benefit policy
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-8">
            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              Try asking a question like:
            </p>
            <div className="space-y-2">
              {exampleQuestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => setInput(q)}
                  className="block w-full text-left p-3 rounded-lg bg-[var(--color-surface-sunken)] text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message, i) => (
          <div
            key={i}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-xl px-4 py-3 ${
                message.role === "user"
                  ? "bg-[var(--color-pe-green)] text-white"
                  : "bg-[var(--color-surface-sunken)] text-[var(--color-text-primary)]"
              }`}
            >
              {message.role === "assistant" && message.status === "pending" ? (
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 border-2 border-[var(--color-pe-green)] border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm">Starting Claude Code...</span>
                </div>
              ) : message.role === "assistant" && message.status === "streaming" ? (
                <div>
                  <pre className="text-sm whitespace-pre-wrap font-mono text-xs leading-relaxed">
                    {message.content || "Thinking..."}
                  </pre>
                  <div className="mt-2 flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
                    <div className="w-2 h-2 border border-[var(--color-pe-green)] border-t-transparent rounded-full animate-spin" />
                    Running...
                  </div>
                </div>
              ) : (
                <pre className="text-sm whitespace-pre-wrap font-mono text-xs leading-relaxed">
                  {message.content}
                </pre>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-[var(--color-border)]">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a policy question..."
            disabled={isLoading}
            className="flex-1 px-4 py-2 text-sm border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-pe-green)] disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-4 py-2 bg-[var(--color-pe-green)] text-white rounded-lg text-sm font-medium hover:bg-[var(--color-pe-green-dark)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? "..." : "Ask"}
          </button>
        </div>
      </form>
    </div>
  );
}
