import { JsonViewer } from "@/components/json-viewer";

export default function QuickstartPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Quick start
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Get up and running with the PolicyEngine API in minutes.
      </p>

      <div className="space-y-8">
        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">1. Start the services</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Clone the repository and start the services using Docker Compose:
          </p>
          <pre className="p-4 bg-[var(--color-code-bg)] text-[var(--color-code-text)] rounded-lg text-sm overflow-x-auto">
{`git clone https://github.com/PolicyEngine/policyengine-api-v2
cd policyengine-api-v2
docker compose up -d`}
          </pre>
          <p className="text-sm text-[var(--color-text-muted)] mt-3">
            Wait for all services to be healthy before proceeding.
          </p>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">2. Create a policy reform</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Define a policy reform by specifying parameter changes:
          </p>
          <pre className="p-4 bg-[var(--color-code-bg)] text-[var(--color-code-text)] rounded-lg text-sm overflow-x-auto">
{`curl -X POST https://v2.api.policyengine.org/policies \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Increased personal allowance",
    "description": "Raises personal allowance to £15,000",
    "parameter_values": [{
      "parameter_id": "<parameter-uuid>",
      "value_json": {"value": 15000},
      "start_date": "2026-01-01",
      "end_date": "2026-12-31"
    }]
  }'`}
          </pre>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">3. Run economic impact analysis</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Submit an economic impact analysis request. This creates baseline and reform simulations and queues them for processing:
          </p>
          <pre className="p-4 bg-[var(--color-code-bg)] text-[var(--color-code-text)] rounded-lg text-sm overflow-x-auto">
{`curl -X POST https://v2.api.policyengine.org/analysis/economic-impact \\
  -H "Content-Type: application/json" \\
  -d '{
    "tax_benefit_model_name": "policyengine_uk",
    "dataset_id": "<dataset-uuid>",
    "policy_id": "<policy-uuid>"
  }'`}
          </pre>
          <p className="text-sm text-[var(--color-text-muted)] mt-3">
            The response includes a <code className="px-1.5 py-0.5 bg-[var(--color-surface-sunken)] rounded text-xs">report_id</code> and initial status.
          </p>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">4. Poll for results</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Check the status until the report is complete:
          </p>
          <pre className="p-4 bg-[var(--color-code-bg)] text-[var(--color-code-text)] rounded-lg text-sm overflow-x-auto">
{`curl https://v2.api.policyengine.org/analysis/economic-impact/<report-id>`}
          </pre>
          <p className="text-sm text-[var(--color-text-secondary)] mt-4 mb-3">
            Once complete, the response includes decile impacts and program statistics:
          </p>
          <div className="rounded-lg overflow-hidden border border-[var(--color-border)]">
            <JsonViewer
              data={{
                report_id: "abc123...",
                status: "completed",
                decile_impacts: [
                  {
                    decile: 1,
                    baseline_mean: 12500.0,
                    reform_mean: 13200.0,
                    relative_change: 0.056,
                  },
                ],
                program_statistics: [
                  {
                    program_name: "income_tax",
                    baseline_total: 2.1e11,
                    reform_total: 1.95e11,
                    change: -1.5e10,
                  },
                ],
              }}
            />
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Python example</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Complete workflow using httpx:
          </p>
          <pre className="p-4 bg-[var(--color-code-bg)] text-[var(--color-code-text)] rounded-lg text-sm overflow-x-auto">
{`import httpx
import time

BASE_URL = "https://v2.api.policyengine.org"

# Create economic impact analysis
response = httpx.post(
    f"{BASE_URL}/analysis/economic-impact",
    json={
        "tax_benefit_model_name": "policyengine_uk",
        "dataset_id": "<dataset-uuid>",
        "policy_id": "<policy-uuid>",
    },
).json()

report_id = response["report_id"]

# Poll for completion
while True:
    result = httpx.get(f"{BASE_URL}/analysis/economic-impact/{report_id}").json()
    if result["status"] == "completed":
        break
    elif result["status"] == "failed":
        raise Exception(f"Analysis failed: {result['error_message']}")
    time.sleep(5)

# Access results
for decile in result["decile_impacts"]:
    print(f"Decile {decile['decile']}: {decile['relative_change']:.1%} change")

for prog in result["program_statistics"]:
    print(f"{prog['program_name']}: £{prog['change']/1e9:.1f}bn change")`}
          </pre>
        </section>
      </div>
    </div>
  );
}
