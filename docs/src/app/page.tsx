import Link from "next/link";

export default function Home() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        PolicyEngine API v2
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        A distributed system for running tax-benefit microsimulations with persistence and async processing.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <Link
          href="/quickstart"
          className="block p-6 border border-[var(--color-border)] rounded-xl bg-white hover:border-[var(--color-pe-green)] transition-colors group"
        >
          <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2 group-hover:text-[var(--color-pe-green)]">
            Quick start
          </h3>
          <p className="text-sm text-[var(--color-text-secondary)]">
            Get up and running with the API in minutes. Complete walkthrough from setup to your first simulation.
          </p>
        </Link>

        <Link
          href="/endpoints/economic-impact"
          className="block p-6 border border-[var(--color-border)] rounded-xl bg-white hover:border-[var(--color-pe-green)] transition-colors group"
        >
          <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2 group-hover:text-[var(--color-pe-green)]">
            Economic impact
          </h3>
          <p className="text-sm text-[var(--color-text-secondary)]">
            Calculate distributional impacts, decile analysis, and program statistics for policy reforms.
          </p>
        </Link>

        <Link
          href="/architecture"
          className="block p-6 border border-[var(--color-border)] rounded-xl bg-white hover:border-[var(--color-pe-green)] transition-colors group"
        >
          <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2 group-hover:text-[var(--color-pe-green)]">
            Architecture
          </h3>
          <p className="text-sm text-[var(--color-text-secondary)]">
            Understand the system design: API server, worker, database, and how they work together.
          </p>
        </Link>

        <Link
          href="/endpoints/datasets"
          className="block p-6 border border-[var(--color-border)] rounded-xl bg-white hover:border-[var(--color-pe-green)] transition-colors group"
        >
          <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2 group-hover:text-[var(--color-pe-green)]">
            API reference
          </h3>
          <p className="text-sm text-[var(--color-text-secondary)]">
            Interactive documentation for all endpoints with live testing capabilities.
          </p>
        </Link>
      </div>

      <div className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
        <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
          Features
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium text-[var(--color-text-primary)] mb-1">Async processing</h4>
            <p className="text-sm text-[var(--color-text-secondary)]">
              Simulations run asynchronously via a worker queue. Poll for status or use webhooks.
            </p>
          </div>
          <div>
            <h4 className="font-medium text-[var(--color-text-primary)] mb-1">Deterministic caching</h4>
            <p className="text-sm text-[var(--color-text-secondary)]">
              Same inputs produce the same simulation ID. Results are cached and reused automatically.
            </p>
          </div>
          <div>
            <h4 className="font-medium text-[var(--color-text-primary)] mb-1">UK and US models</h4>
            <p className="text-sm text-[var(--color-text-secondary)]">
              Full support for PolicyEngine UK and US tax-benefit systems with comprehensive datasets.
            </p>
          </div>
          <div>
            <h4 className="font-medium text-[var(--color-text-primary)] mb-1">Policy reforms</h4>
            <p className="text-sm text-[var(--color-text-secondary)]">
              Define custom parameter changes and compare reform scenarios against baselines.
            </p>
          </div>
        </div>
      </div>

      <div className="mt-8 p-4 bg-[var(--color-surface-sunken)] rounded-lg">
        <p className="text-sm text-[var(--color-text-muted)]">
          <strong className="text-[var(--color-text-secondary)]">Tip:</strong> Use the base URL input in the header to switch between local and production environments.
          The default is <code className="px-1.5 py-0.5 bg-[var(--color-surface-elevated)] rounded text-xs">https://v2.api.policyengine.org</code>.
        </p>
      </div>
    </div>
  );
}
