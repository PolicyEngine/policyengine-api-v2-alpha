"use client";

import { useState, useRef, useEffect } from "react";
import { useApi } from "./api-context";

interface Message {
  role: "user" | "assistant";
  content: string;
  status?: "pending" | "running" | "completed" | "failed";
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

  const pollForResult = async (jobId: string) => {
    const maxAttempts = 120; // 10 minutes max
    let attempts = 0;

    while (attempts < maxAttempts) {
      try {
        const res = await fetch(`${baseUrl}/demo/status/${jobId}`);
        const data = await res.json();

        if (data.status === "completed") {
          setMessages((prev) => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (newMessages[lastIndex]?.role === "assistant") {
              newMessages[lastIndex] = {
                role: "assistant",
                content: data.report || "Analysis complete.",
                status: "completed",
              };
            }
            return newMessages;
          });
          setIsLoading(false);
          return;
        } else if (data.status === "failed") {
          setMessages((prev) => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (newMessages[lastIndex]?.role === "assistant") {
              newMessages[lastIndex] = {
                role: "assistant",
                content: `Error: ${data.error || "Analysis failed"}`,
                status: "failed",
              };
            }
            return newMessages;
          });
          setIsLoading(false);
          return;
        }

        // Update status message
        setMessages((prev) => {
          const newMessages = [...prev];
          const lastIndex = newMessages.length - 1;
          if (newMessages[lastIndex]?.role === "assistant") {
            newMessages[lastIndex] = {
              role: "assistant",
              content: `Analysing... (${data.status})`,
              status: data.status,
            };
          }
          return newMessages;
        });

        await new Promise((resolve) => setTimeout(resolve, 2000));
        attempts++;
      } catch (err) {
        console.error("Poll error:", err);
        await new Promise((resolve) => setTimeout(resolve, 2000));
        attempts++;
      }
    }

    setMessages((prev) => {
      const newMessages = [...prev];
      const lastIndex = newMessages.length - 1;
      if (newMessages[lastIndex]?.role === "assistant") {
        newMessages[lastIndex] = {
          role: "assistant",
          content: "Analysis timed out. Please try again.",
          status: "failed",
        };
      }
      return newMessages;
    });
    setIsLoading(false);
  };

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
      { role: "assistant", content: "Starting analysis...", status: "pending" },
    ]);

    try {
      const res = await fetch(`${baseUrl}/demo/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userMessage }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      pollForResult(data.job_id);
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
              {message.role === "assistant" && message.status && message.status !== "completed" ? (
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 border-2 border-[var(--color-pe-green)] border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm">{message.content}</span>
                </div>
              ) : (
                <div className="prose prose-sm max-w-none">
                  {message.content.split("\n").map((line, j) => (
                    <p key={j} className="mb-2 last:mb-0 text-sm whitespace-pre-wrap">
                      {line}
                    </p>
                  ))}
                </div>
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
