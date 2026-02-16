"use client";

import { ApiPlayground } from "@/components/api-playground";

export default function HouseholdPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Household calculate
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Calculate tax and benefit impacts for a single household. Returns computed values for all variables.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Calculate household
          </h2>
          <ApiPlayground
            method="POST"
            endpoint="/household/calculate"
            description="Calculate all tax and benefit variables for a household under current law or a policy reform."
            defaultBody={{
              tax_benefit_model_name: "policyengine_uk",
              people: [
                {
                  age: 35,
                  employment_income: 50000,
                },
              ],
              household: {
                region: "LONDON",
              },
              year: 2026,
            }}
          />
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Request parameters
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">tax_benefit_model_name</code>
              <span className="text-[var(--color-text-secondary)]">policyengine_uk or policyengine_us</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">people</code>
              <span className="text-[var(--color-text-secondary)]">Array of person objects with variable values (e.g., age, employment_income)</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">benunit</code>
              <span className="text-[var(--color-text-secondary)]">UK: Benefit unit configuration</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">household</code>
              <span className="text-[var(--color-text-secondary)]">Household-level variables</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">year</code>
              <span className="text-[var(--color-text-secondary)]">Simulation year (default: 2026 UK, 2024 US)</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">policy_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID | null - Optional policy reform to apply</span>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            US-specific entities
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">marital_unit</code>
              <span className="text-[var(--color-text-secondary)]">US marital unit configuration</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">family</code>
              <span className="text-[var(--color-text-secondary)]">US family configuration</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">spm_unit</code>
              <span className="text-[var(--color-text-secondary)]">US SPM unit configuration</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">tax_unit</code>
              <span className="text-[var(--color-text-secondary)]">US tax unit configuration</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
