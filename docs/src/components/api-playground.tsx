"use client";

import { useState } from "react";
import { useApi } from "./api-context";
import { JsonViewer } from "./json-viewer";

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";

interface ApiPlaygroundProps {
  method: HttpMethod;
  endpoint: string;
  description: string;
  defaultBody?: Record<string, unknown> | Record<string, unknown>[];
  pathParams?: { name: string; description: string; example: string }[];
}

export function ApiPlayground({
  method,
  endpoint,
  description,
  defaultBody,
  pathParams = [],
}: ApiPlaygroundProps) {
  const { baseUrl } = useApi();
  const [body, setBody] = useState(defaultBody ? JSON.stringify(defaultBody, null, 2) : "");
  const [response, setResponse] = useState<{ status: number; data: unknown } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pathValues, setPathValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    pathParams.forEach((p) => {
      initial[p.name] = p.example;
    });
    return initial;
  });

  const resolvedEndpoint = endpoint.replace(/:(\w+)/g, (_, name) => pathValues[name] || `:${name}`);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const url = `${baseUrl}${resolvedEndpoint}`;
      const options: RequestInit = {
        method,
        headers: {
          "Content-Type": "application/json",
        },
      };

      if (body && (method === "POST" || method === "PUT")) {
        options.body = body;
      }

      const res = await fetch(url, options);
      const data = await res.json().catch(() => null);

      setResponse({
        status: res.status,
        data,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const methodColors: Record<HttpMethod, string> = {
    GET: "bg-blue-100 text-blue-700",
    POST: "bg-green-100 text-green-700",
    PUT: "bg-amber-100 text-amber-700",
    DELETE: "bg-red-100 text-red-700",
  };

  return (
    <div className="border border-[var(--color-border)] rounded-xl overflow-hidden bg-white">
      {/* Header */}
      <div className="p-4 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="flex items-center gap-3 mb-2">
          <span className={`px-2.5 py-1 rounded-md text-xs font-semibold ${methodColors[method]}`}>
            {method}
          </span>
          <code className="text-sm font-mono text-[var(--color-text-primary)]">{endpoint}</code>
        </div>
        <p className="text-sm text-[var(--color-text-secondary)]">{description}</p>
      </div>

      {/* Path parameters */}
      {pathParams.length > 0 && (
        <div className="p-4 border-b border-[var(--color-border)]">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] mb-3">
            Path parameters
          </h4>
          <div className="space-y-3">
            {pathParams.map((param) => (
              <div key={param.name}>
                <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">
                  {param.name}
                  <span className="ml-2 text-xs text-[var(--color-text-muted)] font-normal">
                    {param.description}
                  </span>
                </label>
                <input
                  type="text"
                  value={pathValues[param.name]}
                  onChange={(e) =>
                    setPathValues((prev) => ({ ...prev, [param.name]: e.target.value }))
                  }
                  className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg font-mono focus:outline-none focus:ring-2 focus:ring-[var(--color-pe-green)]"
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Request body */}
      {(method === "POST" || method === "PUT") && (
        <div className="p-4 border-b border-[var(--color-border)]">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] mb-3">
            Request body
          </h4>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={Math.min(15, body.split("\n").length + 2)}
            className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg font-mono bg-[var(--color-code-bg)] text-[var(--color-code-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-pe-green)] resize-y"
            placeholder="{}"
          />
        </div>
      )}

      {/* Send button */}
      <div className="p-4 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="px-4 py-2 bg-[var(--color-pe-green)] text-white rounded-lg text-sm font-medium hover:bg-[var(--color-pe-green-dark)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Sending..." : "Send request"}
        </button>
        <span className="ml-3 text-xs text-[var(--color-text-muted)]">
          {baseUrl}{resolvedEndpoint}
        </span>
      </div>

      {/* Response */}
      {(response || error) && (
        <div className="p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] mb-3">
            Response
          </h4>
          {error ? (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          ) : response ? (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    response.status >= 200 && response.status < 300
                      ? "bg-green-100 text-green-700"
                      : response.status >= 400
                      ? "bg-red-100 text-red-700"
                      : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {response.status}
                </span>
              </div>
              <div className="rounded-lg overflow-hidden border border-[var(--color-border)]">
                <JsonViewer data={response.data} />
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
