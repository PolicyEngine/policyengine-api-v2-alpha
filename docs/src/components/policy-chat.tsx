"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { useApi } from "./api-context";

// Types for Claude Code stream-json format
interface StreamEvent {
  type: "system" | "assistant" | "user" | "result";
  subtype?: string;
  message?: {
    content: Array<{ type: string; text?: string; name?: string; input?: unknown }>;
  };
  result?: string;
  mcp_servers?: Array<{ name: string; status: string }>;
  tool_use_result?: string | { stdout?: string };
  total_cost_usd?: number;
  duration_ms?: number;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  status?: "pending" | "streaming" | "completed" | "failed";
}

interface ToolCall {
  name: string;
  input: unknown;
  result?: string;
  isExpanded?: boolean;
}

export function PolicyChat() {
  const { baseUrl } = useApi();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentToolCalls, setCurrentToolCalls] = useState<ToolCall[]>([]);
  const [mcpConnected, setMcpConnected] = useState<boolean | null>(null);
  const [displayedContent, setDisplayedContent] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fullContentRef = useRef("");

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentToolCalls, displayedContent]);

  // Typing animation effect
  useEffect(() => {
    if (!isTyping || !fullContentRef.current) return;

    const targetContent = fullContentRef.current;
    if (displayedContent.length >= targetContent.length) {
      setIsTyping(false);
      return;
    }

    const charsToAdd = Math.min(3, targetContent.length - displayedContent.length);
    const timeout = setTimeout(() => {
      setDisplayedContent(targetContent.slice(0, displayedContent.length + charsToAdd));
    }, 10);

    return () => clearTimeout(timeout);
  }, [displayedContent, isTyping]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setIsLoading(true);
    setCurrentToolCalls([]);
    setMcpConnected(null);
    setDisplayedContent("");
    setIsTyping(false);
    fullContentRef.current = "";

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
      let assistantText = "";
      let finalResult = "";
      const toolCalls: ToolCall[] = [];

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
              const outerData = JSON.parse(line.slice(6));

              if (outerData.type === "output" && outerData.content) {
                const event: StreamEvent = JSON.parse(outerData.content);

                // Handle system init - check MCP connection
                if (event.type === "system" && event.subtype === "init") {
                  const mcpServer = event.mcp_servers?.find(
                    (s) => s.name === "policyengine"
                  );
                  setMcpConnected(mcpServer?.status === "connected");
                }

                // Handle assistant messages
                if (event.type === "assistant" && event.message?.content) {
                  for (const item of event.message.content) {
                    if (item.type === "text" && item.text) {
                      assistantText += item.text + "\n";
                      fullContentRef.current = assistantText.trim();
                      setIsTyping(true);
                      setMessages((prev) => {
                        const newMessages = [...prev];
                        const lastIndex = newMessages.length - 1;
                        if (newMessages[lastIndex]?.role === "assistant") {
                          newMessages[lastIndex] = {
                            ...newMessages[lastIndex],
                            content: assistantText.trim(),
                          };
                        }
                        return newMessages;
                      });
                    } else if (item.type === "tool_use" && item.name) {
                      const toolCall: ToolCall = {
                        name: item.name,
                        input: item.input,
                        isExpanded: false,
                      };
                      toolCalls.push(toolCall);
                      setCurrentToolCalls([...toolCalls]);
                    }
                  }
                }

                // Handle tool results
                if (event.type === "user" && event.tool_use_result) {
                  if (toolCalls.length > 0) {
                    const result =
                      typeof event.tool_use_result === "string"
                        ? event.tool_use_result
                        : event.tool_use_result.stdout || "";
                    toolCalls[toolCalls.length - 1].result = result;
                    setCurrentToolCalls([...toolCalls]);
                  }
                }

                // Handle final result
                if (event.type === "result" && event.result) {
                  finalResult = event.result;
                  fullContentRef.current = finalResult;
                  setIsTyping(true);
                  setMessages((prev) => {
                    const newMessages = [...prev];
                    const lastIndex = newMessages.length - 1;
                    if (newMessages[lastIndex]?.role === "assistant") {
                      newMessages[lastIndex] = {
                        ...newMessages[lastIndex],
                        content: finalResult,
                        status: "completed",
                      };
                    }
                    return newMessages;
                  });
                }
              } else if (outerData.type === "error") {
                setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastIndex = newMessages.length - 1;
                  if (newMessages[lastIndex]?.role === "assistant") {
                    newMessages[lastIndex] = {
                      role: "assistant",
                      content: `Error: ${outerData.content}`,
                      status: "failed",
                    };
                  }
                  return newMessages;
                });
              } else if (outerData.type === "done") {
                setCurrentToolCalls([]);
                setIsTyping(false);
                setDisplayedContent(fullContentRef.current);
                if (outerData.returncode !== 0) {
                  setMessages((prev) => {
                    const newMessages = [...prev];
                    const lastIndex = newMessages.length - 1;
                    if (newMessages[lastIndex]?.role === "assistant") {
                      newMessages[lastIndex] = {
                        ...newMessages[lastIndex],
                        status: "failed",
                      };
                    }
                    return newMessages;
                  });
                }
              }
            } catch {
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

  const toggleToolExpanded = (index: number) => {
    setCurrentToolCalls((prev) =>
      prev.map((t, i) =>
        i === index ? { ...t, isExpanded: !t.isExpanded } : t
      )
    );
  };

  const exampleQuestions = [
    "How much would it cost to set the UK basic income tax rate to 19p?",
    "What would happen if we doubled child benefit?",
    "How would a £15,000 personal allowance affect different income groups?",
  ];

  const formatToolName = (name: string) => {
    return name
      .replace("mcp__policyengine__", "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  const getDisplayContent = (message: Message, isLastMessage: boolean) => {
    if (isLastMessage && isTyping) {
      return displayedContent;
    }
    return message.content;
  };

  return (
    <div className="border border-[var(--color-border)] rounded-xl overflow-hidden bg-white flex flex-col h-[600px]">
      {/* Header */}
      <div className="p-4 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              mcpConnected === true
                ? "bg-[var(--color-pe-green)]"
                : mcpConnected === false
                  ? "bg-red-500"
                  : "bg-gray-300"
            } ${mcpConnected === null && isLoading ? "animate-pulse" : ""}`}
          />
          <span className="text-sm font-medium text-[var(--color-text-primary)] font-mono">
            Policy analyst
          </span>
          <span className="text-xs text-[var(--color-text-muted)] ml-auto font-mono">
            {mcpConnected === true
              ? "MCP connected"
              : mcpConnected === false
                ? "MCP failed"
                : "Powered by Claude Code"}
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

        {messages.map((message, i) => {
          const isLastMessage = i === messages.length - 1;
          const content = getDisplayContent(message, isLastMessage);

          return (
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
                  <div className="flex items-center gap-2 font-mono">
                    <div className="w-3 h-3 border-2 border-[var(--color-pe-green)] border-t-transparent rounded-full animate-spin" />
                    <span className="text-sm">Starting Claude Code...</span>
                  </div>
                ) : message.role === "assistant" && message.status === "streaming" ? (
                  <div className="font-mono">
                    {content ? (
                      <div className="prose prose-sm max-w-none text-sm [&>*]:text-[var(--color-text-primary)] [&_code]:bg-[var(--color-surface)] [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_strong]:font-semibold">
                        <ReactMarkdown>{content}</ReactMarkdown>
                      </div>
                    ) : currentToolCalls.length === 0 ? (
                      <span className="text-sm text-[var(--color-text-muted)]">
                        Thinking...
                      </span>
                    ) : null}
                    {isLastMessage && isTyping && (
                      <span className="inline-block w-2 h-4 bg-[var(--color-pe-green)] ml-0.5 animate-pulse" />
                    )}
                  </div>
                ) : message.status === "completed" ? (
                  <div className="font-mono prose prose-sm max-w-none text-sm [&>*]:text-[var(--color-text-primary)] [&_code]:bg-[var(--color-surface)] [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_strong]:font-semibold [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-sm">
                    <ReactMarkdown>{content}</ReactMarkdown>
                    {isLastMessage && isTyping && (
                      <span className="inline-block w-2 h-4 bg-[var(--color-pe-green)] ml-0.5 animate-pulse" />
                    )}
                  </div>
                ) : (
                  <div className="text-sm whitespace-pre-wrap font-mono">{content}</div>
                )}
              </div>
            </div>
          );
        })}

        {/* Live tool calls */}
        {currentToolCalls.length > 0 && (
          <div className="bg-[var(--color-surface-sunken)] rounded-xl p-3 space-y-2">
            <div className="text-xs font-medium text-[var(--color-text-muted)] mb-2 font-mono">
              API calls
            </div>
            {currentToolCalls.map((tool, i) => (
              <div
                key={i}
                className="bg-white rounded-lg border border-[var(--color-border)] overflow-hidden"
              >
                <button
                  onClick={() => toggleToolExpanded(i)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-[var(--color-surface)]"
                >
                  <div
                    className={`w-2 h-2 rounded-full ${
                      tool.result ? "bg-[var(--color-pe-green)]" : "bg-amber-400 animate-pulse"
                    }`}
                  />
                  <span className="text-xs font-mono text-[var(--color-text-secondary)] flex-1">
                    {formatToolName(tool.name)}
                  </span>
                  <span className="text-xs text-[var(--color-text-muted)] font-mono">
                    {tool.isExpanded ? "−" : "+"}
                  </span>
                </button>
                {tool.isExpanded && (
                  <div className="px-3 py-2 border-t border-[var(--color-border)] bg-[var(--color-surface-sunken)]">
                    {tool.input !== undefined && tool.input !== null && (
                      <div className="mb-2">
                        <div className="text-xs text-[var(--color-text-muted)] mb-1 font-mono">
                          Input:
                        </div>
                        <pre className="text-xs font-mono overflow-x-auto bg-white p-2 rounded">
                          {JSON.stringify(tool.input, null, 2)}
                        </pre>
                      </div>
                    )}
                    {tool.result && (
                      <div>
                        <div className="text-xs text-[var(--color-text-muted)] mb-1 font-mono">
                          Result:
                        </div>
                        <pre className="text-xs font-mono overflow-x-auto bg-white p-2 rounded max-h-32 overflow-y-auto">
                          {tool.result.slice(0, 500)}
                          {tool.result.length > 500 && "..."}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
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
