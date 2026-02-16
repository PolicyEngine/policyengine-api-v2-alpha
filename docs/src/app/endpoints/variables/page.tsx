"use client";

import { ApiPlayground } from "@/components/api-playground";

export default function VariablesPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Variables
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Tax-benefit system variables that can be calculated or used as inputs. Variables are associated with model versions.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            List variables
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/variables"
            description="Retrieve all variables. Can filter by model version."
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Get variable
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/variables/:variable_id"
            description="Retrieve a specific variable by ID."
            pathParams={[
              {
                name: "variable_id",
                description: "UUID of the variable",
                example: "dd0e8400-e29b-41d4-a716-446655440000",
              },
            ]}
          />
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Variable object
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Unique identifier</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">name</code>
              <span className="text-[var(--color-text-secondary)]">string - Variable name (e.g., income_tax)</span>
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
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">entity</code>
              <span className="text-[var(--color-text-secondary)]">string - Entity level (person, household, etc.)</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">value_type</code>
              <span className="text-[var(--color-text-secondary)]">string - Data type (float, int, bool, enum)</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">unit</code>
              <span className="text-[var(--color-text-secondary)]">string | null - Unit of measurement</span>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Common UK variables
          </h2>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {["income_tax", "national_insurance", "universal_credit", "child_benefit", "council_tax", "household_net_income", "employment_income", "pension_income"].map((v) => (
              <code key={v} className="px-2 py-1 bg-[var(--color-surface-sunken)] rounded font-mono text-xs">{v}</code>
            ))}
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Common US variables
          </h2>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {["income_tax", "employee_payroll_tax", "snap", "tanf", "ssi", "social_security", "employment_income", "spm_unit_net_income"].map((v) => (
              <code key={v} className="px-2 py-1 bg-[var(--color-surface-sunken)] rounded font-mono text-xs">{v}</code>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
