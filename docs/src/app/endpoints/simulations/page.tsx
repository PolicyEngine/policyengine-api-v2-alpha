"use client";

import { ApiPlayground } from "@/components/api-playground";

export default function SimulationsPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Simulations
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Run tax-benefit microsimulations on datasets. Simulations are processed asynchronously by background workers.
      </p>

      <div className="p-4 mb-8 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          <strong>Note:</strong> Simulations use deterministic UUIDs based on inputs. Requesting the same simulation twice returns the cached result instead of running again.
        </p>
      </div>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            List simulations
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/simulations"
            description="Retrieve all simulations."
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Get simulation
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/simulations/:simulation_id"
            description="Retrieve a specific simulation and its status."
            pathParams={[
              {
                name: "simulation_id",
                description: "UUID of the simulation",
                example: "770e8400-e29b-41d4-a716-446655440000",
              },
            ]}
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Create simulation
          </h2>
          <ApiPlayground
            method="POST"
            endpoint="/simulations"
            description="Create a new simulation. Returns immediately with pending status."
            defaultBody={{
              dataset_id: "4d5b4f7c-c7cf-4f49-8b59-a491e0adbf8d",
              tax_benefit_model_version_id: "a8a20af0-b0bf-4b98-9e42-a62034f99da5",
              policy_id: null,
              dynamic_id: null,
            }}
          />
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Request parameters
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-52 font-mono text-[var(--color-pe-green)]">dataset_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Dataset to run simulation on</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-52 font-mono text-[var(--color-pe-green)]">tax_benefit_model_version_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Model version to use</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-52 font-mono text-[var(--color-pe-green)]">policy_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID | null - Optional policy reform</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-52 font-mono text-[var(--color-pe-green)]">dynamic_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID | null - Optional behavioural response model</span>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Response object
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Deterministic identifier</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">dataset_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Reference to dataset</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">policy_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID | null - Optional policy reform</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">dynamic_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID | null - Optional behavioural response</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">status</code>
              <span className="text-[var(--color-text-secondary)]">enum - pending | running | completed | failed</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">error_message</code>
              <span className="text-[var(--color-text-secondary)]">string | null - Error details if failed</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">started_at</code>
              <span className="text-[var(--color-text-secondary)]">datetime | null - When processing started</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">completed_at</code>
              <span className="text-[var(--color-text-secondary)]">datetime | null - When processing finished</span>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Status values
          </h2>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-700">pending</span>
              <span className="text-sm text-[var(--color-text-secondary)]">Queued, waiting for worker</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700">running</span>
              <span className="text-sm text-[var(--color-text-secondary)]">Worker is processing</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-700">completed</span>
              <span className="text-sm text-[var(--color-text-secondary)]">Successfully finished</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-700">failed</span>
              <span className="text-sm text-[var(--color-text-secondary)]">Error occurred (see error_message)</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
