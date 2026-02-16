"use client";

import { ApiPlayground } from "@/components/api-playground";

export default function ParametersPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Parameters
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Tax-benefit system parameters that can be modified in policy reforms. Each parameter has a name, description, and default values over time.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            List parameters
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/parameters"
            description="Retrieve all parameters. Can filter by model version."
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Get parameter
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/parameters/:parameter_id"
            description="Retrieve a specific parameter by ID."
            pathParams={[
              {
                name: "parameter_id",
                description: "UUID of the parameter",
                example: "ee0e8400-e29b-41d4-a716-446655440000",
              },
            ]}
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            List parameter values
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/parameter-values"
            description="Retrieve all parameter values."
          />
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Parameter object
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Unique identifier</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">name</code>
              <span className="text-[var(--color-text-secondary)]">string - Full parameter path</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">label</code>
              <span className="text-[var(--color-text-secondary)]">string - Human-readable label</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">description</code>
              <span className="text-[var(--color-text-secondary)]">string | null - Detailed description</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">unit</code>
              <span className="text-[var(--color-text-secondary)]">string | null - Unit (currency, percent, etc.)</span>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Example UK parameters
          </h2>
          <div className="space-y-2 text-sm">
            <code className="block px-2 py-1 bg-[var(--color-surface-sunken)] rounded font-mono text-xs">
              gov.hmrc.income_tax.allowances.personal_allowance.amount
            </code>
            <code className="block px-2 py-1 bg-[var(--color-surface-sunken)] rounded font-mono text-xs">
              gov.hmrc.income_tax.rates.uk.basic
            </code>
            <code className="block px-2 py-1 bg-[var(--color-surface-sunken)] rounded font-mono text-xs">
              gov.dwp.universal_credit.elements.standard_allowance.single_young
            </code>
          </div>
        </section>
      </div>
    </div>
  );
}
