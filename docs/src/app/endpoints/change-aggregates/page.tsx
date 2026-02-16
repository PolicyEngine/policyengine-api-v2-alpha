"use client";

import { ApiPlayground } from "@/components/api-playground";

export default function ChangeAggregatesPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Change aggregates
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Compute change statistics comparing baseline vs reform simulations. Accepts a list of specifications.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            List change aggregates
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/outputs/change-aggregates"
            description="Retrieve all computed change aggregates."
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Get change aggregate
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/outputs/change-aggregates/:output_id"
            description="Retrieve a specific change aggregate result."
            pathParams={[
              {
                name: "output_id",
                description: "UUID of the change aggregate output",
                example: "990e8400-e29b-41d4-a716-446655440000",
              },
            ]}
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Create change aggregates (batch)
          </h2>
          <ApiPlayground
            method="POST"
            endpoint="/outputs/change-aggregates"
            description="Create multiple change aggregates from a list of specifications."
            defaultBody={[
              {
                baseline_simulation_id: "bc147839-72a1-5544-b07a-829b26c0d5dc",
                reform_simulation_id: "0194df0d-212b-5897-b2cf-5ecfc0308413",
                variable: "household_net_income",
                aggregate_type: "sum",
                entity: "household",
              },
              {
                baseline_simulation_id: "bc147839-72a1-5544-b07a-829b26c0d5dc",
                reform_simulation_id: "0194df0d-212b-5897-b2cf-5ecfc0308413",
                variable: "household_net_income",
                aggregate_type: "mean",
                entity: "household",
                change_geq: 0,
              },
              {
                baseline_simulation_id: "bc147839-72a1-5544-b07a-829b26c0d5dc",
                reform_simulation_id: "0194df0d-212b-5897-b2cf-5ecfc0308413",
                variable: "income_tax",
                aggregate_type: "count",
                entity: "person",
                change_leq: 0,
              },
            ]}
          />
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Change aggregate specification
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">baseline_simulation_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Baseline simulation</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">reform_simulation_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Reform simulation</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">variable</code>
              <span className="text-[var(--color-text-secondary)]">string - Variable name to compare</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">aggregate_type</code>
              <span className="text-[var(--color-text-secondary)]">sum | mean | count</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">entity</code>
              <span className="text-[var(--color-text-secondary)]">string - Entity level</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">change_geq</code>
              <span className="text-[var(--color-text-secondary)]">number | null - Filter: change greater than or equal to</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">change_leq</code>
              <span className="text-[var(--color-text-secondary)]">number | null - Filter: change less than or equal to</span>
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
              <span className="text-sm text-[var(--color-text-secondary)]">Total change across population (weighted)</span>
            </div>
            <div className="flex items-start gap-3">
              <code className="flex-shrink-0 px-2 py-1 rounded text-xs font-mono bg-[var(--color-surface-sunken)] text-[var(--color-pe-green)]">mean</code>
              <span className="text-sm text-[var(--color-text-secondary)]">Weighted average change</span>
            </div>
            <div className="flex items-start gap-3">
              <code className="flex-shrink-0 px-2 py-1 rounded text-xs font-mono bg-[var(--color-surface-sunken)] text-[var(--color-pe-green)]">count</code>
              <span className="text-sm text-[var(--color-text-secondary)]">Number of entities (use with change_geq/change_leq to count winners/losers)</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
