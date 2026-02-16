"use client";

import { ApiPlayground } from "@/components/api-playground";
import { JsonViewer } from "@/components/json-viewer";

export default function HouseholdImpactPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Household impact comparison
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Compare a household under baseline (current law) vs a policy reform. Returns both calculations plus computed differences.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Calculate household impact
          </h2>
          <ApiPlayground
            method="POST"
            endpoint="/household/impact"
            description="Calculate the difference between baseline and reform for a household."
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
              policy_id: "d6563842-920b-4368-be52-67e82529bb60",
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
              <span className="text-[var(--color-text-secondary)]">Array of person objects (age, employment_income, etc.)</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">household</code>
              <span className="text-[var(--color-text-secondary)]">Household-level variables (region, etc.)</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">year</code>
              <span className="text-[var(--color-text-secondary)]">integer | null - Simulation year</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">policy_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID | null - Reform policy to compare against baseline</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">dynamic_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID | null - Optional behavioural response model</span>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">
            Example response
          </h2>
          <div className="rounded-lg overflow-hidden border border-[var(--color-border)]">
            <JsonViewer
              data={{
                baseline: {
                  person: [{ income_tax: 7486, net_income: 42514 }],
                  household: { household_net_income: 42514 },
                },
                reform: {
                  person: [{ income_tax: 6486, net_income: 43514 }],
                  household: { household_net_income: 43514 },
                },
                impact: {
                  household: {
                    household_net_income: {
                      baseline: 42514,
                      reform: 43514,
                      change: 1000,
                    },
                  },
                  person: [
                    {
                      income_tax: { baseline: 7486, reform: 6486, change: -1000 },
                      net_income: { baseline: 42514, reform: 43514, change: 1000 },
                    },
                  ],
                },
              }}
            />
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Response structure
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-32 font-mono text-[var(--color-pe-green)]">baseline</code>
              <span className="text-[var(--color-text-secondary)]">Full household calculation under current law</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-32 font-mono text-[var(--color-pe-green)]">reform</code>
              <span className="text-[var(--color-text-secondary)]">Full household calculation with policy applied</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-32 font-mono text-[var(--color-pe-green)]">impact</code>
              <span className="text-[var(--color-text-secondary)]">Computed differences (baseline, reform, change) for numeric variables</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
