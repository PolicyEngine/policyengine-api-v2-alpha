import { PolicyChat } from "../../components/policy-chat";

export default function DemoPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        AI policy analyst
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Ask questions in natural language and get AI-generated policy analysis reports.
      </p>

      <div className="space-y-8">
        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            How it works
          </h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            This demo uses an AI agent powered by Claude that interacts with the PolicyEngine API to answer your questions.
            When you ask a question, the agent:
          </p>
          <ol className="text-sm text-[var(--color-text-secondary)] space-y-2 list-decimal list-inside mb-4">
            <li>Searches for relevant policy parameters</li>
            <li>Creates a policy reform based on your question</li>
            <li>Runs an economy-wide impact analysis</li>
            <li>Generates a report with the findings</li>
          </ol>
          <p className="text-sm text-[var(--color-text-muted)]">
            Analysis typically takes 30-60 seconds as it runs full microsimulations on population data.
          </p>
        </section>

        <PolicyChat />

        <section className="p-4 bg-[var(--color-surface-sunken)] rounded-lg">
          <p className="text-sm text-[var(--color-text-muted)]">
            <strong className="text-[var(--color-text-secondary)]">Note:</strong> This is a demo of the API's capabilities.
            Results are from real PolicyEngine microsimulations but should be verified for policy research.
            The agent uses Claude Sonnet via a Modal Sandbox for secure, isolated execution.
          </p>
        </section>
      </div>
    </div>
  );
}
