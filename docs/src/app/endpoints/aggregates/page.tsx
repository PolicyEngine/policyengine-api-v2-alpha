"use client";

import { ApiPlayground } from "@/components/api-playground";

export default function AggregatesPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Aggregates
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Compute aggregate statistics from simulation results. Supports sums, means, and counts with optional filtering. Accepts a list of specifications.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            List aggregates
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/outputs/aggregates"
            description="Retrieve all computed aggregates."
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Get aggregate
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/outputs/aggregates/:output_id"
            description="Retrieve a specific aggregate result."
            pathParams={[
              {
                name: "output_id",
                description: "UUID of the aggregate output",
                example: "880e8400-e29b-41d4-a716-446655440000",
              },
            ]}
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Create aggregates (batch)
          </h2>
          <ApiPlayground
            method="POST"
            endpoint="/outputs/aggregates"
            description="Create multiple aggregates from a list of specifications. Worker will compute them."
            defaultBody={[
              {
                simulation_id: "bc147839-72a1-5544-b07a-829b26c0d5dc",
                variable: "universal_credit",
                aggregate_type: "sum",
                entity: "benunit",
              },
              {
                simulation_id: "bc147839-72a1-5544-b07a-829b26c0d5dc",
                variable: "household_net_income",
                aggregate_type: "mean",
                entity: "household",
                filter_config: { quantile: 10, quantile_eq: 10 },
              },
              {
                simulation_id: "bc147839-72a1-5544-b07a-829b26c0d5dc",
                variable: "income_tax",
                aggregate_type: "sum",
                entity: "person",
              },
            ]}
          />
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Aggregate specification
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">simulation_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Source simulation</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">variable</code>
              <span className="text-[var(--color-text-secondary)]">string - Variable name to aggregate</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">aggregate_type</code>
              <span className="text-[var(--color-text-secondary)]">sum | mean | count</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">entity</code>
              <span className="text-[var(--color-text-secondary)]">string - Entity level (person, household, benunit, etc.)</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">filter_config</code>
              <span className="text-[var(--color-text-secondary)]">object | null - Optional quantile filtering</span>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Aggregate types
          </h2>
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <code className="flex-shrink-0 px-2 py-1 rounded text-xs font-mono bg-[var(--color-surface-sunken)] text-[var(--color-pe-green)]">sum</code>
              <span className="text-sm text-[var(--color-text-secondary)]">Total across population (weighted)</span>
            </div>
            <div className="flex items-start gap-3">
              <code className="flex-shrink-0 px-2 py-1 rounded text-xs font-mono bg-[var(--color-surface-sunken)] text-[var(--color-pe-green)]">mean</code>
              <span className="text-sm text-[var(--color-text-secondary)]">Weighted average</span>
            </div>
            <div className="flex items-start gap-3">
              <code className="flex-shrink-0 px-2 py-1 rounded text-xs font-mono bg-[var(--color-surface-sunken)] text-[var(--color-pe-green)]">count</code>
              <span className="text-sm text-[var(--color-text-secondary)]">Number of entities (weighted)</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
