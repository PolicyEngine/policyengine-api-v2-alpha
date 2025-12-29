"use client";

import { useState, useRef, useEffect, useMemo } from "react";
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

interface ParsedStep {
  type: "agent" | "tool_use" | "api_call" | "api_response" | "tool_result" | "assistant" | "unknown";
  title: string;
  content: string;
  method?: string;
  url?: string;
  statusCode?: number;
  toolName?: string;
  params?: Record<string, unknown>;
  isExpanded?: boolean;
}

function parseLogEntry(message: string): ParsedStep {
  // [AGENT] messages - filter out internal debug info
  if (message.startsWith("[AGENT]")) {
    const content = message.replace("[AGENT] ", "");
    // Skip internal debug messages
    if (content.startsWith("Stop reason:") ||
        content.startsWith("Turn ") ||
        content.startsWith("Loaded ") ||
        content.startsWith("Fetching ") ||
        content.startsWith("Completed")) {
      return { type: "unknown", title: "", content: "" };
    }
    return {
      type: "agent",
      title: "Agent",
      content: content,
    };
  }

  // [TOOL_USE] tool_name: {...}
  if (message.startsWith("[TOOL_USE]")) {
    const content = message.replace("[TOOL_USE] ", "");
    const colonIndex = content.indexOf(":");
    if (colonIndex > -1) {
      const toolName = content.slice(0, colonIndex).trim();
      const paramsStr = content.slice(colonIndex + 1).trim();
      let params: Record<string, unknown> = {};
      try {
        params = JSON.parse(paramsStr);
      } catch {
        // Not valid JSON
      }
      // Clean up tool name for display
      const displayName = toolName
        .replace(/_/g, " ")
        .replace(/parameters get$/, "")
        .replace(/parameters post$/, "")
        .replace(/household calculate post$/, "Calculate household")
        .replace(/list /g, "Search ");
      return {
        type: "tool_use",
        title: displayName,
        content: paramsStr,
        toolName,
        params,
      };
    }
  }

  // [API] GET/POST url
  if (message.startsWith("[API]")) {
    const content = message.replace("[API] ", "");

    // Check if it's a response
    if (content.startsWith("Response:")) {
      const statusCode = parseInt(content.replace("Response: ", ""), 10);
      return {
        type: "api_response",
        title: "Response",
        content: content,
        statusCode,
      };
    }

    // Check if it's a request with method
    const methodMatch = content.match(/^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$/);
    if (methodMatch) {
      return {
        type: "api_call",
        title: "API Request",
        content: content,
        method: methodMatch[1],
        url: methodMatch[2],
      };
    }

    // Query or Body
    if (content.startsWith("Query:") || content.startsWith("Body:")) {
      return {
        type: "api_call",
        title: content.startsWith("Query:") ? "Query params" : "Request body",
        content: content.replace(/^(Query|Body):\s*/, ""),
      };
    }
  }

  // [TOOL_RESULT] ...
  if (message.startsWith("[TOOL_RESULT]")) {
    const content = message.replace("[TOOL_RESULT] ", "");
    return {
      type: "tool_result",
      title: "Result",
      content: content,
    };
  }

  // [ASSISTANT] ...
  if (message.startsWith("[ASSISTANT]")) {
    const content = message.replace("[ASSISTANT] ", "");
    return {
      type: "assistant",
      title: "Thinking",
      content: content,
    };
  }

  return {
    type: "unknown",
    title: "Log",
    content: message,
  };
}

function ToolCard({ step }: { step: ParsedStep }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (step.type === "agent") {
    return null; // Hide agent messages, they're redundant with progress indicator
  }

  if (step.type === "tool_use") {
    return (
      <div className="py-1.5 animate-fadeIn">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 text-sm hover:text-[var(--color-pe-green)] transition-colors"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-pe-green)]" />
          <span className="text-[var(--color-text-secondary)] capitalize">{step.title}</span>
          {step.params && Object.keys(step.params).length > 0 && (
            <svg
              className={`w-3 h-3 text-[var(--color-text-muted)] transition-transform ${isExpanded ? "rotate-90" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          )}
        </button>
        {isExpanded && step.params && Object.keys(step.params).length > 0 && (
          <div className="ml-3.5 mt-1 font-mono text-xs text-[var(--color-text-muted)] bg-[var(--color-surface)] rounded px-2 py-1.5">
            {Object.entries(step.params).map(([key, value]) => (
              <div key={key}>
                <span className="text-[var(--color-pe-green)]">{key}</span>
                <span className="text-[var(--color-text-muted)]">: </span>
                <span>{typeof value === "string" ? `"${value}"` : JSON.stringify(value)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Hide API details - too noisy
  if (step.type === "api_call" || step.type === "api_response") {
    return null;
  }

  if (step.type === "tool_result") {
    return (
      <div className="py-1 ml-3.5 animate-fadeIn">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
        >
          <svg className={`w-3 h-3 transition-transform ${isExpanded ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span>Result</span>
        </button>
        {isExpanded && (
          <div className="mt-1.5 font-mono text-xs bg-[var(--color-code-bg)] text-[var(--color-code-text)] rounded p-2 overflow-x-auto max-h-32 overflow-y-auto">
            <pre className="whitespace-pre-wrap">{step.content.slice(0, 1500)}{step.content.length > 1500 ? "\n..." : ""}</pre>
          </div>
        )}
      </div>
    );
  }

  if (step.type === "assistant") {
    return (
      <div className="py-1.5 animate-fadeIn">
        <p className="text-sm text-[var(--color-text-muted)] leading-relaxed">{step.content}</p>
      </div>
    );
  }

  return null;
}

function ProgressIndicator({ logs }: { logs: LogEntry[] }) {
  const stage = useMemo(() => {
    const hasSearch = logs.some(l => l.message.includes("parameters"));
    const hasPolicy = logs.some(l => l.message.includes("policies"));
    const hasAnalysis = logs.some(l => l.message.includes("analysis") || l.message.includes("economic"));
    const hasHousehold = logs.some(l => l.message.includes("household"));
    const isComplete = logs.some(l => l.message.includes("Completed"));

    if (isComplete) return "Complete";
    if (hasAnalysis) return "Running analysis...";
    if (hasPolicy) return "Creating policy...";
    if (hasHousehold) return "Calculating...";
    if (hasSearch) return "Searching parameters...";
    return "Starting...";
  }, [logs]);

  if (logs.length === 0) return null;

  return (
    <div className="flex items-center gap-2 mb-3 text-xs text-[var(--color-text-muted)]">
      {stage !== "Complete" && (
        <div className="w-3 h-3 border-2 border-[var(--color-pe-green)] border-t-transparent rounded-full animate-spin" />
      )}
      <span>{stage}</span>
    </div>
  );
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

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const parsedSteps = useMemo(() => {
    return logs
      .map(log => parseLogEntry(log.message))
      .filter(step => step.type !== "unknown");
  }, [logs]);

  const pollLogs = async (id: string) => {
    try {
      const res = await fetch(`${baseUrl}/agent/logs/${id}`);
      if (!res.ok) return;

      const data = await res.json();
      setLogs(data.logs || []);

      if (data.status === "completed" || data.status === "failed") {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }

        setIsLoading(false);
        setCallId(null);

        let finalContent = "";
        if (data.result?.result) {
          finalContent = data.result.result;
        } else {
          finalContent =
            data.status === "completed"
              ? "Analysis completed. Check the steps above for details."
              : "Analysis failed. Please try again.";
        }

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

    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", status: "pending" },
    ]);

    try {
      const res = await fetch(`${baseUrl}/agent/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userMessage }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const newCallId = data.call_id;
      setCallId(newCallId);

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

      pollIntervalRef.current = setInterval(() => {
        pollLogs(newCallId);
      }, 1000);

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

  const exampleQuestions = [
    "What is the UK personal allowance for 2026?",
    "Calculate tax for someone earning £50,000 in the UK",
    "What would happen if we increased child benefit by 10%?",
    "What benefits would a single parent with two children receive?",
  ];

  return (
    <div className="border border-[var(--color-border)] rounded-2xl overflow-hidden bg-white flex flex-col h-[700px] shadow-sm">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[var(--color-border)] bg-gradient-to-r from-[var(--color-pe-green)] to-[var(--color-pe-green-dark)]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <h2 className="text-white font-semibold">Policy analyst</h2>
              <p className="text-white/70 text-xs">Ask questions about UK and US tax-benefit policy</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isLoading ? "bg-amber-300 animate-pulse" : "bg-green-300"}`} />
            <span className="text-white/70 text-xs font-medium">
              {isLoading ? "Working..." : "Ready"}
            </span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-5">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col justify-center">
            <div className="text-center mb-8">
              <h3 className="font-display text-2xl text-[var(--color-text-primary)] mb-2">
                What would you like to know?
              </h3>
              <p className="text-sm text-[var(--color-text-muted)]">
                Ask about tax rates, benefits, or policy impacts
              </p>
            </div>
            <div className="grid gap-2 max-w-lg mx-auto">
              {exampleQuestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => setInput(q)}
                  className="text-left p-4 rounded-xl bg-[var(--color-surface-sunken)] hover:bg-[var(--color-surface)] border border-transparent hover:border-[var(--color-border)] text-sm text-[var(--color-text-secondary)] transition-all group"
                >
                  <span className="group-hover:text-[var(--color-pe-green)] transition-colors">{q}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((message, i) => (
              <div key={i}>
                {message.role === "user" ? (
                  <div className="flex justify-end">
                    <div className="max-w-[80%] bg-[var(--color-pe-green)] text-white rounded-2xl rounded-br-md px-4 py-3">
                      <p className="text-sm">{message.content}</p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {/* Running state with live steps */}
                    {(message.status === "pending" || message.status === "running") && (
                      <div className="bg-[var(--color-surface-sunken)] rounded-2xl p-4">
                        <ProgressIndicator logs={logs} />

                        {message.status === "pending" ? (
                          <div className="flex items-center gap-3">
                            <div className="w-5 h-5 border-2 border-[var(--color-pe-green)] border-t-transparent rounded-full animate-spin" />
                            <span className="text-sm text-[var(--color-text-secondary)]">Starting analysis...</span>
                          </div>
                        ) : (
                          <div className="space-y-0">
                            {parsedSteps.slice(-10).map((step, j) => (
                              <ToolCard key={j} step={step} />
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Completed/failed state */}
                    {(message.status === "completed" || message.status === "failed") && (
                      <div className="space-y-4">
                        {/* Collapsible steps summary */}
                        {parsedSteps.length > 0 && (
                          <details className="group">
                            <summary className="cursor-pointer list-none flex items-center gap-2 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]">
                              <svg className="w-3 h-3 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                              </svg>
                              <span>{parsedSteps.filter(s => s.type === "tool_use").length} tool calls executed</span>
                            </summary>
                            <div className="mt-3 bg-[var(--color-surface-sunken)] rounded-xl p-4 space-y-0">
                              {parsedSteps.map((step, j) => (
                                <ToolCard key={j} step={step} />
                              ))}
                            </div>
                          </details>
                        )}

                        {/* Final response */}
                        <div className={`rounded-2xl rounded-bl-md px-5 py-4 ${
                          message.status === "failed"
                            ? "bg-red-50 border border-red-200"
                            : "bg-white border border-[var(--color-border)]"
                        }`}>
                          <div className="prose prose-sm max-w-none text-[var(--color-text-primary)] [&_strong]:font-semibold [&_code]:bg-[var(--color-surface-sunken)] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-sm [&_code]:font-mono [&_h1]:text-lg [&_h1]:mt-4 [&_h1]:mb-2 [&_h2]:text-base [&_h2]:mt-3 [&_h2]:mb-2 [&_h3]:text-sm [&_h3]:mt-2 [&_h3]:mb-1 [&_p]:my-3 [&_p]:leading-relaxed [&_ul]:my-3 [&_ul]:space-y-1 [&_ol]:my-3 [&_ol]:space-y-1 [&_li]:my-0 [&_li]:leading-relaxed [&_blockquote]:border-l-2 [&_blockquote]:border-[var(--color-pe-green)] [&_blockquote]:pl-4 [&_blockquote]:my-3 [&_blockquote]:text-[var(--color-text-secondary)]">
                            <ReactMarkdown remarkPlugins={[remarkBreaks]}>
                              {message.content}
                            </ReactMarkdown>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a policy question..."
            disabled={isLoading}
            className="flex-1 px-4 py-3 text-sm border border-[var(--color-border)] rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-[var(--color-pe-green)] focus:border-transparent disabled:opacity-50 placeholder:text-[var(--color-text-muted)]"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-6 py-3 bg-[var(--color-pe-green)] hover:bg-[var(--color-pe-green-dark)] text-white rounded-xl text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {isLoading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Working</span>
              </>
            ) : (
              <>
                <span>Ask</span>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </>
            )}
          </button>
        </div>
      </form>

      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn {
          animation: fadeIn 0.2s ease-out forwards;
        }
      `}</style>
    </div>
  );
}
