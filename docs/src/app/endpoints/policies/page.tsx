"use client";

import { ApiPlayground } from "@/components/api-playground";

export default function PoliciesPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Policies
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Define policy reforms by modifying tax-benefit system parameters.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            List policies
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/policies"
            description="Retrieve all defined policies."
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Get policy
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/policies/:policy_id"
            description="Retrieve a specific policy by ID."
            pathParams={[
              {
                name: "policy_id",
                description: "UUID of the policy",
                example: "660e8400-e29b-41d4-a716-446655440000",
              },
            ]}
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Create policy
          </h2>
          <ApiPlayground
            method="POST"
            endpoint="/policies"
            description="Create a new policy reform with parameter value changes."
            defaultBody={{
              name: "Increased personal allowance",
              description: "Raises personal allowance to £15,000",
              parameter_values: [
                {
                  parameter_id: "fae4ceb3-1ec2-4e05-baa7-00ecc9060592",
                  value_json: { value: 15000 },
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
              <span className="text-[var(--color-text-secondary)]">string - Policy name</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">description</code>
              <span className="text-[var(--color-text-secondary)]">string | null - Optional description</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">parameter_values</code>
              <span className="text-[var(--color-text-secondary)]">array - Parameter modifications (see below)</span>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Delete policy
          </h2>
          <ApiPlayground
            method="DELETE"
            endpoint="/policies/:policy_id"
            description="Delete a policy by ID."
            pathParams={[
              {
                name: "policy_id",
                description: "UUID of the policy to delete",
                example: "660e8400-e29b-41d4-a716-446655440000",
              },
            ]}
          />
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Policy object
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Unique identifier</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">name</code>
              <span className="text-[var(--color-text-secondary)]">string - Policy name</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">description</code>
              <span className="text-[var(--color-text-secondary)]">string | null - Optional description</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">parameter_values</code>
              <span className="text-[var(--color-text-secondary)]">array - Parameter modifications</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">created_at</code>
              <span className="text-[var(--color-text-secondary)]">datetime - Creation timestamp</span>
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
      </div>
    </div>
  );
}
