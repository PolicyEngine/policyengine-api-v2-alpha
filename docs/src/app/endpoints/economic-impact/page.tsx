"use client";

import { ApiPlayground } from "@/components/api-playground";
import { JsonViewer } from "@/components/json-viewer";

export default function EconomicImpactPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Economic impact
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Calculate the distributional impact of policy reforms. Compares reform scenario against baseline and produces decile-level analysis plus program statistics.
      </p>

      <div className="p-4 mb-8 bg-green-50 border border-green-200 rounded-lg">
        <p className="text-sm text-green-800">
          <strong>Recommended endpoint:</strong> This is the primary way to analyse policy reforms. It handles simulation creation, comparison, and statistical analysis automatically.
        </p>
      </div>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Create economic impact analysis
          </h2>
          <ApiPlayground
            method="POST"
            endpoint="/analysis/economic-impact"
            description="Create or retrieve an economic impact analysis. Creates baseline and reform simulations automatically."
            defaultBody={{
              tax_benefit_model_name: "policyengine_uk",
              dataset_id: "4d5b4f7c-c7cf-4f49-8b59-a491e0adbf8d",
              policy_id: "d6563842-920b-4368-be52-67e82529bb60",
              dynamic_id: null,
            }}
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Get economic impact status
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/analysis/economic-impact/:report_id"
            description="Check status and retrieve results of an economic impact analysis."
            pathParams={[
              {
                name: "report_id",
                description: "UUID of the report",
                example: "990e8400-e29b-41d4-a716-446655440000",
              },
            ]}
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
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">dataset_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Dataset to run simulations on</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">policy_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID | null - Reform policy (baseline uses current law)</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-48 font-mono text-[var(--color-pe-green)]">dynamic_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID | null - Optional behavioural response model</span>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">
            Example response (completed)
          </h2>
          <div className="rounded-lg overflow-hidden border border-[var(--color-border)]">
            <JsonViewer
              data={{
                report_id: "990e8400-e29b-41d4-a716-446655440000",
                status: "completed",
                baseline_simulation: {
                  id: "aaa11111-e29b-41d4-a716-446655440000",
                  status: "completed",
                  error_message: null,
                },
                reform_simulation: {
                  id: "bbb22222-e29b-41d4-a716-446655440000",
                  status: "completed",
                  error_message: null,
                },
                decile_impacts: [
                  {
                    decile: 1,
                    income_variable: "household_net_income",
                    baseline_mean: 12500.0,
                    reform_mean: 13200.0,
                    absolute_change: 700.0,
                    relative_change: 0.056,
                    count_better_off: 450000,
                    count_worse_off: 120000,
                    count_no_change: 30000,
                  },
                  {
                    decile: 2,
                    income_variable: "household_net_income",
                    baseline_mean: 18000.0,
                    reform_mean: 18450.0,
                    absolute_change: 450.0,
                    relative_change: 0.025,
                    count_better_off: 380000,
                    count_worse_off: 150000,
                    count_no_change: 70000,
                  },
                ],
                program_statistics: [
                  {
                    program_name: "income_tax",
                    entity: "person",
                    is_tax: true,
                    baseline_total: 210000000000,
                    reform_total: 195000000000,
                    change: -15000000000,
                    baseline_count: 31000000,
                    reform_count: 29000000,
                    winners: 8000000,
                    losers: 0,
                  },
                  {
                    program_name: "universal_credit",
                    entity: "person",
                    is_tax: false,
                    baseline_total: 45000000000,
                    reform_total: 42000000000,
                    change: -3000000000,
                    baseline_count: 6000000,
                    reform_count: 5500000,
                    winners: 0,
                    losers: 500000,
                  },
                ],
              }}
            />
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Decile impact object
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">decile</code>
              <span className="text-[var(--color-text-secondary)]">integer (1-10) - Income decile</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">income_variable</code>
              <span className="text-[var(--color-text-secondary)]">string - Variable used for decile ranking</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">baseline_mean</code>
              <span className="text-[var(--color-text-secondary)]">number - Mean income under baseline</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">reform_mean</code>
              <span className="text-[var(--color-text-secondary)]">number - Mean income under reform</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">absolute_change</code>
              <span className="text-[var(--color-text-secondary)]">number - reform_mean - baseline_mean</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">relative_change</code>
              <span className="text-[var(--color-text-secondary)]">number - Percentage change (0.05 = 5%)</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">count_better_off</code>
              <span className="text-[var(--color-text-secondary)]">number - People gaining from reform</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">count_worse_off</code>
              <span className="text-[var(--color-text-secondary)]">number - People losing from reform</span>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Program statistics object
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">program_name</code>
              <span className="text-[var(--color-text-secondary)]">string - Tax or benefit name</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">entity</code>
              <span className="text-[var(--color-text-secondary)]">string - Entity level (person, household, etc.)</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">is_tax</code>
              <span className="text-[var(--color-text-secondary)]">boolean - True for taxes, false for benefits</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">baseline_total</code>
              <span className="text-[var(--color-text-secondary)]">number - Total revenue/spending under baseline</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">reform_total</code>
              <span className="text-[var(--color-text-secondary)]">number - Total revenue/spending under reform</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">change</code>
              <span className="text-[var(--color-text-secondary)]">number - Difference (reform - baseline)</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">winners</code>
              <span className="text-[var(--color-text-secondary)]">number - Count of people benefiting</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">losers</code>
              <span className="text-[var(--color-text-secondary)]">number - Count of people losing out</span>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Programs analysed
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-sm font-medium text-[var(--color-text-primary)] mb-2">UK</h4>
              <ul className="text-sm text-[var(--color-text-secondary)] space-y-1">
                <li>income_tax</li>
                <li>national_insurance</li>
                <li>vat</li>
                <li>council_tax</li>
                <li>universal_credit</li>
                <li>child_benefit</li>
                <li>pension_credit</li>
                <li>income_support</li>
                <li>working_tax_credit</li>
                <li>child_tax_credit</li>
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-medium text-[var(--color-text-primary)] mb-2">US</h4>
              <ul className="text-sm text-[var(--color-text-secondary)] space-y-1">
                <li>income_tax</li>
                <li>employee_payroll_tax</li>
                <li>snap</li>
                <li>tanf</li>
                <li>ssi</li>
                <li>social_security</li>
              </ul>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
