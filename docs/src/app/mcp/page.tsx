export default function McpPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        MCP integration
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Use the PolicyEngine API as an MCP server for AI assistants like Claude.
      </p>

      <div className="space-y-8">
        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            What is MCP?
          </h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            The Model Context Protocol (MCP) is a standard for AI assistants to interact with external tools and data sources.
            The PolicyEngine API exposes all endpoints as MCP tools at <code className="px-1.5 py-0.5 bg-[var(--color-surface-sunken)] rounded text-xs">/mcp</code>,
            allowing AI assistants to calculate taxes and benefits, run economic impact analyses, and query policy data.
          </p>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Add to Claude Code
          </h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Run this command:
          </p>
          <pre className="p-4 bg-[var(--color-code-bg)] text-[var(--color-code-text)] rounded-lg text-sm overflow-x-auto">
{`claude mcp add --transport http policyengine https://v2.api.policyengine.org/mcp/`}
          </pre>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Add to Claude Desktop
          </h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Add this to your <code className="px-1.5 py-0.5 bg-[var(--color-surface-sunken)] rounded text-xs">claude_desktop_config.json</code> file:
          </p>
          <pre className="p-4 bg-[var(--color-code-bg)] text-[var(--color-code-text)] rounded-lg text-sm overflow-x-auto">
{`{
  "mcpServers": {
    "policyengine": {
      "type": "url",
      "url": "https://v2.api.policyengine.org/mcp/"
    }
  }
}`}
          </pre>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Available tools
          </h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            All API endpoints are exposed as MCP tools. Key capabilities include:
          </p>
          <ul className="text-sm text-[var(--color-text-secondary)] space-y-2 list-disc list-inside">
            <li><strong>household_calculate</strong> — calculate taxes and benefits for a household</li>
            <li><strong>household_impact</strong> — compare baseline vs reform policy impact</li>
            <li><strong>analysis_economic_impact</strong> — run population-wide economic analysis</li>
            <li><strong>policies_list</strong> / <strong>policies_create</strong> — manage policy reforms</li>
            <li><strong>variables_list</strong> / <strong>parameters_list</strong> — query tax-benefit system metadata</li>
            <li><strong>datasets_list</strong> — list available population datasets</li>
          </ul>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Example prompts
          </h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Once connected, you can ask Claude things like:
          </p>
          <div className="space-y-3">
            <div className="p-3 bg-[var(--color-surface-sunken)] rounded-lg text-sm text-[var(--color-text-secondary)]">
              "Calculate the net income for a UK household with two adults earning £40,000 and £30,000"
            </div>
            <div className="p-3 bg-[var(--color-surface-sunken)] rounded-lg text-sm text-[var(--color-text-secondary)]">
              "What would happen to this household's benefits if we increased the personal allowance to £15,000?"
            </div>
            <div className="p-3 bg-[var(--color-surface-sunken)] rounded-lg text-sm text-[var(--color-text-secondary)]">
              "List all the parameters related to child benefit"
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
