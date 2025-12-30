"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import { useApi } from "./api-context";

interface Message {
  role: "user" | "assistant";
  content: string;
  status?: "pending" | "running" | "completed" | "failed";
  steps?: ParsedStep[];
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
      // Map tool names to human-readable labels
      const toolNameMap: Record<string, string> = {
        // Parameters
        "list_parameters_parameters__get": "Search parameters",
        "get_parameter_parameters__parameter_id__get": "Get parameter",
        "list_parameter_values_parameter_values__get": "Get parameter values",
        "get_parameter_value_parameter_values__parameter_value_id__get": "Get parameter value",
        // Variables
        "list_variables_variables__get": "Search variables",
        "get_variable_variables__variable_id__get": "Get variable",
        // Policies
        "create_policy_policies__post": "Create policy",
        "get_policy_policies__policy_id__get": "Get policy",
        "list_policies_policies__get": "List policies",
        // Household
        "calculate_household_household_calculate_post": "Calculate household",
        "get_household_job_status_household_calculate__job_id__get": "Poll household job",
        // Household impact
        "calculate_household_impact_comparison_household_impact_post": "Calculate household impact",
        "get_household_impact_job_status_household_impact__job_id__get": "Poll household impact",
        // Economic impact
        "economic_impact_analysis_economic_impact_post": "Run economic analysis",
        "get_economic_impact_status_analysis_economic_impact__report_id__get": "Poll economic analysis",
        // Datasets
        "list_datasets_datasets__get": "List datasets",
        "get_dataset_datasets__dataset_id__get": "Get dataset",
        // Models
        "list_tax_benefit_models_tax_benefit_models__get": "List models",
        "get_tax_benefit_model_tax_benefit_models__model_id__get": "Get model",
        // Simulations
        "list_simulations_simulations__get": "List simulations",
        "get_simulation_simulations__simulation_id__get": "Get simulation",
        // Utility
        "sleep": "Wait",
      };
      const displayName = toolNameMap[toolName] || toolName
        .replace(/_+/g, " ")
        .replace(/\s+(get|post|put|delete)$/i, "")
        .replace(/\s+/g, " ")
        .trim();
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
    return null;
  }

  if (step.type === "tool_use") {
    return (
      <div className="py-1 animate-fadeIn">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 hover:text-[var(--color-pe-green)] transition-colors group w-full text-left font-mono"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-pe-green)] shrink-0" />
          <span className="text-[12px] text-[var(--color-text-secondary)]">{step.title}</span>
          {step.params && Object.keys(step.params).length > 0 && (
            <svg
              className={`w-3 h-3 text-[var(--color-text-muted)] transition-transform shrink-0 ${isExpanded ? "rotate-90" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          )}
        </button>
        {isExpanded && step.params && Object.keys(step.params).length > 0 && (
          <div className="ml-3.5 mt-1.5 text-[11px] bg-[var(--color-code-bg)] text-[var(--color-code-text)] rounded-md px-3 py-2 animate-slideDown font-mono">
            {Object.entries(step.params).map(([key, value]) => (
              <div key={key} className="flex gap-2 py-0.5">
                <span className="text-[var(--color-pe-green-light)]">{key}:</span>
                <span className="text-[var(--color-code-text)]/80">
                  {typeof value === "string" ? value : JSON.stringify(value)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (step.type === "api_call" || step.type === "api_response") {
    return null;
  }

  if (step.type === "tool_result") {
    return (
      <div className="py-1 ml-3.5 animate-fadeIn">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-1.5 text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] font-mono"
        >
          <svg className={`w-3 h-3 transition-transform ${isExpanded ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span>result</span>
        </button>
        {isExpanded && (
          <div className="mt-1.5 text-[11px] bg-[var(--color-code-bg)] text-[var(--color-code-text)] rounded-md p-2.5 overflow-x-auto max-h-48 overflow-y-auto animate-slideDown font-mono">
            <pre className="whitespace-pre-wrap leading-relaxed">{step.content}</pre>
          </div>
        )}
      </div>
    );
  }

  if (step.type === "assistant") {
    return (
      <div className="py-1.5 animate-fadeIn">
        <p className="text-[12px] text-[var(--color-text-muted)] leading-relaxed italic">{step.content}</p>
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

    if (isComplete) return "complete";
    if (hasAnalysis) return "running analysis...";
    if (hasPolicy) return "creating policy...";
    if (hasHousehold) return "calculating...";
    if (hasSearch) return "searching parameters...";
    return "starting...";
  }, [logs]);

  if (logs.length === 0) return null;

  return (
    <div className="flex items-center gap-2 mb-3 pb-2.5 border-b border-[var(--color-border)]">
      {stage !== "complete" && (
        <div className="w-3 h-3 border-2 border-[var(--color-pe-green)] border-t-transparent rounded-full animate-spin" />
      )}
      {stage === "complete" && (
        <div className="w-3 h-3 rounded-full bg-[var(--color-success)] flex items-center justify-center">
          <svg className="w-2 h-2 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
      )}
      <span className="text-[11px] font-mono text-[var(--color-text-muted)]">{stage}</span>
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

        // Parse and store steps with the message so they persist
        const finalSteps = (data.logs || [])
          .map((log: LogEntry) => parseLogEntry(log.message))
          .filter((step: ParsedStep) => step.type !== "unknown");

        setMessages((prev) => {
          const newMessages = [...prev];
          const lastIndex = newMessages.length - 1;
          if (newMessages[lastIndex]?.role === "assistant") {
            newMessages[lastIndex] = {
              ...newMessages[lastIndex],
              content: finalContent,
              status: data.status,
              steps: finalSteps,
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
    "Calculate tax for someone earning £50,000",
    "What if we increased child benefit by 10%?",
    "What benefits would a single parent receive?",
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
              <h3 className="text-xl font-medium text-[var(--color-text-primary)] mb-2">
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
                  className="text-left px-4 py-3 rounded-lg bg-[var(--color-surface-sunken)] hover:bg-white border border-transparent hover:border-[var(--color-border)] hover:shadow-sm text-[13px] text-[var(--color-text-secondary)] transition-all group font-mono"
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
                      <p className="text-[14px] leading-relaxed">{message.content}</p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {/* Running state with live steps */}
                    {(message.status === "pending" || message.status === "running") && (
                      <div className="bg-[var(--color-surface-sunken)] rounded-xl p-4">
                        <ProgressIndicator logs={logs} />

                        {message.status === "pending" ? (
                          <div className="flex items-center gap-2">
                            <div className="w-3 h-3 border-2 border-[var(--color-pe-green)] border-t-transparent rounded-full animate-spin" />
                            <span className="text-[11px] font-mono text-[var(--color-text-muted)]">starting...</span>
                          </div>
                        ) : (
                          <div className="space-y-0">
                            {parsedSteps.slice(-12).map((step, j) => (
                              <ToolCard key={j} step={step} />
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Completed/failed state */}
                    {(message.status === "completed" || message.status === "failed") && (
                      <div className="space-y-3">
                        {/* Collapsible steps summary */}
                        {message.steps && message.steps.length > 0 && (
                          <details className="group">
                            <summary className="cursor-pointer list-none flex items-center gap-2 text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] font-mono">
                              <svg className="w-3 h-3 group-open:rotate-90 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                              </svg>
                              <span>{message.steps.filter(s => s.type === "tool_use").length} tool calls</span>
                            </summary>
                            <div className="mt-2 bg-[var(--color-surface-sunken)] rounded-lg p-3 space-y-0">
                              {message.steps.map((step, j) => (
                                <ToolCard key={j} step={step} />
                              ))}
                            </div>
                          </details>
                        )}

                        {/* Final response */}
                        <div className={`rounded-lg px-4 py-3 ${
                          message.status === "failed"
                            ? "bg-red-50 border border-red-200"
                            : "bg-white border border-[var(--color-border)]"
                        }`}>
                          <div className="response-content">
                            <ReactMarkdown remarkPlugins={[remarkBreaks, remarkGfm]}>
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
            className="flex-1 px-4 py-2.5 text-[13px] font-mono border border-[var(--color-border)] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[var(--color-pe-green)] focus:border-transparent disabled:opacity-50 placeholder:text-[var(--color-text-muted)]"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-4 py-2.5 bg-[var(--color-pe-green)] hover:bg-[var(--color-pe-green-dark)] text-white rounded-lg text-[13px] font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
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

      <style jsx global>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slideDown {
          from { opacity: 0; max-height: 0; }
          to { opacity: 1; max-height: 500px; }
        }
        .animate-fadeIn {
          animation: fadeIn 0.2s ease-out forwards;
        }
        .animate-slideDown {
          animation: slideDown 0.2s ease-out forwards;
        }

        /* Response content typography */
        .response-content {
          font-family: var(--font-sans);
          font-size: 14px;
          line-height: 1.6;
          color: var(--color-text-primary);
        }
        .response-content p {
          margin: 0.75em 0;
        }
        .response-content p:first-child {
          margin-top: 0;
        }
        .response-content p:last-child {
          margin-bottom: 0;
        }
        .response-content h1, .response-content h2, .response-content h3 {
          font-weight: 600;
          margin-top: 1.25em;
          margin-bottom: 0.5em;
          line-height: 1.3;
        }
        .response-content h1 { font-size: 1.25em; }
        .response-content h2 { font-size: 1.1em; }
        .response-content h3 { font-size: 1em; }
        .response-content h1:first-child,
        .response-content h2:first-child,
        .response-content h3:first-child {
          margin-top: 0;
        }
        .response-content strong {
          font-weight: 600;
        }
        .response-content ul, .response-content ol {
          margin: 0.75em 0;
          padding-left: 1.5em;
        }
        .response-content li {
          margin: 0.25em 0;
        }
        .response-content code {
          font-family: var(--font-mono);
          font-size: 0.9em;
          background: var(--color-surface-sunken);
          padding: 0.15em 0.4em;
          border-radius: 4px;
        }
        .response-content pre {
          font-family: var(--font-mono);
          font-size: 12px;
          background: var(--color-code-bg);
          color: var(--color-code-text);
          padding: 1em;
          border-radius: 8px;
          overflow-x: auto;
          margin: 1em 0;
        }
        .response-content pre code {
          background: none;
          padding: 0;
          font-size: inherit;
        }
        .response-content table {
          width: 100%;
          border-collapse: collapse;
          margin: 1em 0;
          font-size: 13px;
        }
        .response-content th {
          background: var(--color-surface-sunken);
          border: 1px solid var(--color-border);
          padding: 0.5em 0.75em;
          text-align: left;
          font-weight: 600;
        }
        .response-content td {
          border: 1px solid var(--color-border);
          padding: 0.5em 0.75em;
        }
        .response-content tr:hover td {
          background: var(--color-surface-sunken);
        }
        .response-content blockquote {
          border-left: 3px solid var(--color-pe-green);
          padding-left: 1em;
          margin: 1em 0;
          color: var(--color-text-secondary);
          font-style: italic;
        }
        .response-content a {
          color: var(--color-pe-green);
          text-decoration: underline;
        }
        .response-content a:hover {
          color: var(--color-pe-green-dark);
        }
        .response-content hr {
          border: none;
          border-top: 1px solid var(--color-border);
          margin: 1.5em 0;
        }
      `}</style>
    </div>
  );
}
