"use client";

import { ReactNode } from "react";

interface JsonViewerProps {
  data: unknown;
}

export function JsonViewer({ data }: JsonViewerProps) {
  const formatJson = (obj: unknown, indent: number = 0, path: string = "root"): ReactNode[] => {
    const elements: ReactNode[] = [];
    const spaces = "  ".repeat(indent);

    if (obj === null) {
      return [<span key={`${path}-null`} className="text-purple-400">null</span>];
    }

    if (typeof obj === "boolean") {
      return [<span key={`${path}-bool`} className="text-pink-400">{obj.toString()}</span>];
    }

    if (typeof obj === "number") {
      return [<span key={`${path}-num`} className="text-amber-400">{obj}</span>];
    }

    if (typeof obj === "string") {
      return [<span key={`${path}-str`} className="text-green-400">&quot;{obj}&quot;</span>];
    }

    if (Array.isArray(obj)) {
      if (obj.length === 0) {
        return [<span key={`${path}-empty-arr`}>[]</span>];
      }

      elements.push(<span key={`${path}-arr-open`}>[</span>);
      elements.push(<span key={`${path}-arr-newline`}>{"\n"}</span>);

      obj.forEach((item, index) => {
        const itemPath = `${path}[${index}]`;
        elements.push(<span key={`${itemPath}-space`}>{spaces}  </span>);
        elements.push(...formatJson(item, indent + 1, itemPath));
        if (index < obj.length - 1) {
          elements.push(<span key={`${itemPath}-comma`}>,</span>);
        }
        elements.push(<span key={`${itemPath}-nl`}>{"\n"}</span>);
      });

      elements.push(<span key={`${path}-arr-close-space`}>{spaces}</span>);
      elements.push(<span key={`${path}-arr-close`}>]</span>);
      return elements;
    }

    if (typeof obj === "object") {
      const keys = Object.keys(obj);
      if (keys.length === 0) {
        return [<span key={`${path}-empty-obj`}>{"{}"}</span>];
      }

      elements.push(<span key={`${path}-obj-open`}>{"{"}</span>);
      elements.push(<span key={`${path}-obj-newline`}>{"\n"}</span>);

      keys.forEach((key, index) => {
        const keyPath = `${path}.${key}`;
        elements.push(<span key={`${keyPath}-space`}>{spaces}  </span>);
        elements.push(<span key={`${keyPath}-key`} className="text-blue-400">&quot;{key}&quot;</span>);
        elements.push(<span key={`${keyPath}-colon`}>: </span>);
        elements.push(...formatJson((obj as Record<string, unknown>)[key], indent + 1, keyPath));
        if (index < keys.length - 1) {
          elements.push(<span key={`${keyPath}-comma`}>,</span>);
        }
        elements.push(<span key={`${keyPath}-nl`}>{"\n"}</span>);
      });

      elements.push(<span key={`${path}-obj-close-space`}>{spaces}</span>);
      elements.push(<span key={`${path}-obj-close`}>{"}"}</span>);
      return elements;
    }

    return [<span key={`${path}-unknown`}>{String(obj)}</span>];
  };

  return (
    <pre className="p-4 bg-[var(--color-code-bg)] text-[var(--color-code-text)] text-sm overflow-auto max-h-96">
      <code>{formatJson(data)}</code>
    </pre>
  );
}
