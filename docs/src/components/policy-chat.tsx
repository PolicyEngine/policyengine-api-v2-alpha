"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import { useApi } from "./api-context";

interface Message {
  role: "user" | "assistant";
  content: string;
  status?: "pending" | "running" | "completed" | "failed";
}

interface LogEntry {
  timestamp: string;
  message: string;
}

export function PolicyChat() {
  const { baseUrl } = useApi();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [callId, setCallId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, logs]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const pollLogs = async (id: string) => {
    try {
      const res = await fetch(`${baseUrl}/agent/logs/${id}`);
      if (!res.ok) {
        console.error("Failed to fetch logs:", res.status);
        return;
      }

      const data = await res.json();
      setLogs(data.logs || []);

      // Check if completed or failed
      if (data.status === "completed" || data.status === "failed") {
        // Stop polling
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }

        setIsLoading(false);
        setCallId(null);

        // Extract final result from logs or result field
        let finalContent = "";
        if (data.result?.result) {
          finalContent = data.result.result;
        } else {
          // Try to extract from logs - look for [CLAUDE] lines with result
          const claudeLogs = data.logs
            .map((l: LogEntry) => l.message)
            .filter((m: string) => m.startsWith("[CLAUDE]"))
            .map((m: string) => m.replace("[CLAUDE] ", ""));

          // Try to parse the last few lines for result
          for (const log of claudeLogs.reverse()) {
            try {
              const event = JSON.parse(log);
              if (event.type === "result" && event.result) {
                finalContent = event.result;
                break;
              }
            } catch {
              // Not JSON, skip
            }
          }

          if (!finalContent) {
            finalContent =
              data.status === "completed"
                ? "Analysis completed. Check logs for details."
                : "Analysis failed. Check logs for errors.";
          }
        }

        // Update assistant message with final content
        setMessages((prev) => {
          const newMessages = [...prev];
          const lastIndex = newMessages.length - 1;
          if (newMessages[lastIndex]?.role === "assistant") {
            newMessages[lastIndex] = {
              ...newMessages[lastIndex],
              content: finalContent,
              status: data.status,
            };
          }
          return newMessages;
        });
      }
    } catch (err) {
      console.error("Error polling logs:", err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setIsLoading(true);
    setLogs([]);
    setCallId(null);

    // Stop any existing polling
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    // Add user message
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

    // Add pending assistant message
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", status: "pending" },
    ]);

    try {
      // Start the agent
      const res = await fetch(`${baseUrl}/agent/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userMessage }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      const newCallId = data.call_id;
      setCallId(newCallId);

      // Update to running status
      setMessages((prev) => {
        const newMessages = [...prev];
        const lastIndex = newMessages.length - 1;
        if (newMessages[lastIndex]?.role === "assistant") {
          newMessages[lastIndex] = {
            ...newMessages[lastIndex],
            status: "running",
          };
        }
        return newMessages;
      });

      // Start polling for logs
      pollIntervalRef.current = setInterval(() => {
        pollLogs(newCallId);
      }, 1000);

      // Initial poll
      pollLogs(newCallId);
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

  // Parse log message to extract useful info
  const parseLogMessage = (message: string): { type: string; content: string } => {
    if (message.startsWith("[AGENT]")) {
      return { type: "agent", content: message.replace("[AGENT] ", "") };
    }
    if (message.startsWith("[CLAUDE]")) {
      const claudeContent = message.replace("[CLAUDE] ", "");
      // Try to parse as JSON
      try {
        const event = JSON.parse(claudeContent);
        if (event.type === "assistant" && event.message?.content) {
          const textParts = event.message.content
            .filter((c: { type: string }) => c.type === "text")
            .map((c: { text: string }) => c.text)
            .join("");
          if (textParts) {
            return { type: "text", content: textParts };
          }
          const toolParts = event.message.content
            .filter((c: { type: string }) => c.type === "tool_use")
            .map((c: { name: string }) => c.name);
          if (toolParts.length > 0) {
            return { type: "tool", content: `Using: ${toolParts.join(", ")}` };
          }
        }
        if (event.type === "system" && event.subtype === "init") {
          const mcpStatus = event.mcp_servers?.find(
            (s: { name: string }) => s.name === "policyengine"
          );
          return {
            type: "system",
            content: mcpStatus?.status === "connected" ? "MCP connected" : "Starting...",
          };
        }
        if (event.type === "result") {
          return { type: "result", content: "Analysis complete" };
        }
        return { type: "claude", content: `[${event.type || "event"}]` };
      } catch {
        return { type: "claude", content: claudeContent.slice(0, 100) };
      }
    }
    return { type: "log", content: message.slice(0, 100) };
  };

  const exampleQuestions = [
    "How much would it cost to set the UK basic income tax rate to 19p?",
    "What would happen if we doubled child benefit?",
    "Calculate tax for a UK household earning 50,000",
    "What is the budgetary impact of abolishing the higher rate of income tax?",
    "What benefits would a single parent with two children receive in California?",
  ];

  return (
    <div className="border border-[var(--color-border)] rounded-xl overflow-hidden bg-white flex flex-col h-[600px]">
      {/* Header */}
      <div className="p-4 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              isLoading ? "bg-amber-400 animate-pulse" : "bg-gray-300"
            }`}
          />
          <span className="text-sm font-medium text-[var(--color-text-primary)] font-mono">
            Policy analyst
          </span>
          <span className="text-xs text-[var(--color-text-muted)] ml-auto font-mono">
            Powered by Claude Code + MCP
          </span>
        </div>
        <p className="text-xs text-[var(--color-text-muted)] mt-1 font-mono">
          Ask natural language questions about UK or US tax and benefit policy
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-8">
            <p className="text-sm text-[var(--color-text-muted)] mb-4 font-mono">
              Try asking a question like:
            </p>
            <div className="space-y-2">
              {exampleQuestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => setInput(q)}
                  className="block w-full text-left p-3 rounded-lg bg-[var(--color-surface-sunken)] text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] transition-colors font-mono"
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
              {message.role === "assistant" &&
              (message.status === "pending" || message.status === "running") ? (
                <div className="flex items-center gap-2 font-mono">
                  <div className="w-3 h-3 border-2 border-[var(--color-pe-green)] border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm">
                    {message.status === "pending" ? "Starting..." : "Analysing..."}
                  </span>
                </div>
              ) : message.status === "completed" || message.status === "failed" ? (
                <div className="font-mono prose prose-sm max-w-none text-sm [&>*]:text-[var(--color-text-primary)] [&_code]:bg-[var(--color-surface)] [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_strong]:font-semibold">
                  <ReactMarkdown remarkPlugins={[remarkBreaks]}>
                    {message.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <div className="text-sm whitespace-pre-wrap font-mono">{message.content}</div>
              )}
            </div>
          </div>
        ))}

        {/* Live logs */}
        {isLoading && logs.length > 0 && (
          <div className="bg-[var(--color-surface-sunken)] rounded-xl p-3 space-y-1 font-mono text-xs max-h-64 overflow-y-auto">
            <div className="text-xs font-medium text-[var(--color-text-muted)] mb-2 sticky top-0 bg-[var(--color-surface-sunken)]">
              Live output ({logs.length} entries)
            </div>
            {logs.slice(-30).map((log, i) => {
              const parsed = parseLogMessage(log.message);
              return (
                <div
                  key={i}
                  className={`flex items-start gap-2 ${
                    parsed.type === "tool"
                      ? "text-amber-600"
                      : parsed.type === "text"
                      ? "text-[var(--color-text-primary)]"
                      : parsed.type === "agent"
                      ? "text-blue-600"
                      : parsed.type === "system"
                      ? "text-green-600"
                      : "text-[var(--color-text-muted)]"
                  }`}
                >
                  <span className="text-[var(--color-text-muted)] select-none shrink-0">
                    {">"}
                  </span>
                  <span className="whitespace-pre-wrap break-words">{parsed.content}</span>
                </div>
              );
            })}
            <div className="flex items-center gap-2 text-[var(--color-text-muted)]">
              <span className="select-none">{">"}</span>
              <span className="inline-block w-2 h-3 bg-[var(--color-pe-green)] animate-pulse" />
            </div>
          </div>
        )}

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
            className="flex-1 px-4 py-2 text-sm border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-pe-green)] disabled:opacity-50 font-mono"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-4 py-2 bg-[var(--color-pe-green)] text-white rounded-lg text-sm font-medium hover:bg-[var(--color-pe-green-dark)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-mono"
          >
            {isLoading ? "..." : "Ask"}
          </button>
        </div>
      </form>
    </div>
  );
}
