"use client";

import { ApiPlayground } from "@/components/api-playground";

export default function DynamicsPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Dynamics
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Define behavioural response models that modify simulation parameters based on policy changes.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            List dynamics
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/dynamics"
            description="Retrieve all defined dynamic models."
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Get dynamic
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/dynamics/:dynamic_id"
            description="Retrieve a specific dynamic model by ID."
            pathParams={[
              {
                name: "dynamic_id",
                description: "UUID of the dynamic model",
                example: "aa0e8400-e29b-41d4-a716-446655440000",
              },
            ]}
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Create dynamic
          </h2>
          <ApiPlayground
            method="POST"
            endpoint="/dynamics"
            description="Create a new behavioural response model."
            defaultBody={{
              name: "Labour supply elasticity",
              description: "Models labour supply response to tax changes",
              parameter_values: [
                {
                  parameter_id: "fae4ceb3-1ec2-4e05-baa7-00ecc9060592",
                  value_json: { value: 0.2 },
                  start_date: "2026-01-01",
                  end_date: "2026-12-31",
                },
              ],
            }}
          />
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Request parameters
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">name</code>
              <span className="text-[var(--color-text-secondary)]">string - Model name</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">description</code>
              <span className="text-[var(--color-text-secondary)]">string | null - Optional description</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">parameter_values</code>
              <span className="text-[var(--color-text-secondary)]">array - Behavioural parameter modifications (see below)</span>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Parameter value object
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">parameter_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Reference to parameter</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">value_json</code>
              <span className="text-[var(--color-text-secondary)]">object - New parameter value</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">start_date</code>
              <span className="text-[var(--color-text-secondary)]">date - When change takes effect</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">end_date</code>
              <span className="text-[var(--color-text-secondary)]">date - When change ends</span>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Dynamic object
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Unique identifier</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">name</code>
              <span className="text-[var(--color-text-secondary)]">string - Model name</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">description</code>
              <span className="text-[var(--color-text-secondary)]">string | null - Optional description</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">parameter_values</code>
              <span className="text-[var(--color-text-secondary)]">array - Behavioural parameter modifications</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
