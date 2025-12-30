export default function ModalPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Modal compute
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        PolicyEngine uses Modal.com for serverless compute, with two separate apps for different workloads.
      </p>

      <div className="space-y-8">
        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Why two apps?</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            The API uses two separate Modal apps rather than one combined app. This separation is intentional and provides several benefits:
          </p>
          <div className="space-y-4">
            <div>
              <h3 className="font-medium text-[var(--color-text-primary)] mb-2">Image size</h3>
              <p className="text-sm text-[var(--color-text-secondary)]">
                The <code className="px-1.5 py-0.5 bg-[var(--color-surface-sunken)] rounded text-xs">policyengine</code> app has massive container images (multiple GB) with the full UK and US tax-benefit models pre-loaded. The <code className="px-1.5 py-0.5 bg-[var(--color-surface-sunken)] rounded text-xs">policyengine-sandbox</code> app is minimal - just the Anthropic SDK and requests library.
              </p>
            </div>
            <div>
              <h3 className="font-medium text-[var(--color-text-primary)] mb-2">Cold start optimisation</h3>
              <p className="text-sm text-[var(--color-text-secondary)]">
                The main app uses Modal&apos;s memory snapshot feature to pre-load PolicyEngine models at build time. When a function cold starts, it restores from the snapshot rather than re-importing the models, achieving sub-1s cold starts for functions that would otherwise take 30+ seconds to import.
              </p>
            </div>
            <div>
              <h3 className="font-medium text-[var(--color-text-primary)] mb-2">Architectural decoupling</h3>
              <p className="text-sm text-[var(--color-text-secondary)]">
                The sandbox/agent calls the public API endpoints, which then trigger the simulation functions. They&apos;re independent - the agent doesn&apos;t directly import PolicyEngine models, it makes HTTP calls.
              </p>
            </div>
            <div>
              <h3 className="font-medium text-[var(--color-text-primary)] mb-2">Independent scaling</h3>
              <p className="text-sm text-[var(--color-text-secondary)]">
                Simulation workloads scale differently from agent chat sessions. Keeping them separate lets Modal scale each independently based on demand.
              </p>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">policyengine app</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            The main compute app for running simulations. Located at <code className="px-1.5 py-0.5 bg-[var(--color-surface-sunken)] rounded text-xs">src/policyengine_api/modal_app.py</code>.
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-primary)]">Function</th>
                  <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-primary)]">Image</th>
                  <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-primary)]">Memory</th>
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">Purpose</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-secondary)]">
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 pr-4 font-mono text-xs">simulate_household_uk</td>
                  <td className="py-2 pr-4">uk_image</td>
                  <td className="py-2 pr-4">4GB</td>
                  <td className="py-2">Single UK household calculation</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 pr-4 font-mono text-xs">simulate_household_us</td>
                  <td className="py-2 pr-4">us_image</td>
                  <td className="py-2 pr-4">4GB</td>
                  <td className="py-2">Single US household calculation</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 pr-4 font-mono text-xs">simulate_economy_uk</td>
                  <td className="py-2 pr-4">uk_image</td>
                  <td className="py-2 pr-4">8GB</td>
                  <td className="py-2">UK economy simulation</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 pr-4 font-mono text-xs">simulate_economy_us</td>
                  <td className="py-2 pr-4">us_image</td>
                  <td className="py-2 pr-4">8GB</td>
                  <td className="py-2">US economy simulation</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 pr-4 font-mono text-xs">economy_comparison_uk</td>
                  <td className="py-2 pr-4">uk_image</td>
                  <td className="py-2 pr-4">8GB</td>
                  <td className="py-2">UK decile impacts, budget impact</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono text-xs">economy_comparison_us</td>
                  <td className="py-2 pr-4">us_image</td>
                  <td className="py-2 pr-4">8GB</td>
                  <td className="py-2">US decile impacts, budget impact</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mt-4 p-3 bg-[var(--color-surface-sunken)] rounded-lg">
            <p className="text-xs text-[var(--color-text-muted)]">
              Deploy with: <code className="font-mono">modal deploy src/policyengine_api/modal_app.py</code>
            </p>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">policyengine-sandbox app</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Lightweight app for the AI agent. Located at <code className="px-1.5 py-0.5 bg-[var(--color-surface-sunken)] rounded text-xs">src/policyengine_api/agent_sandbox.py</code>.
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-primary)]">Function</th>
                  <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-primary)]">Dependencies</th>
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">Purpose</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-secondary)]">
                <tr>
                  <td className="py-2 pr-4 font-mono text-xs">run_agent</td>
                  <td className="py-2 pr-4">anthropic, requests</td>
                  <td className="py-2">Agentic loop using Claude with API tools</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="text-sm text-[var(--color-text-secondary)] mt-4">
            The agent dynamically generates Claude tools from the OpenAPI spec, then executes an agentic loop to answer policy questions by making API calls. It doesn&apos;t import PolicyEngine directly.
          </p>

          <div className="mt-4 p-3 bg-[var(--color-surface-sunken)] rounded-lg">
            <p className="text-xs text-[var(--color-text-muted)]">
              Deploy with: <code className="font-mono">modal deploy src/policyengine_api/agent_sandbox.py</code>
            </p>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Memory snapshots</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            The <code className="px-1.5 py-0.5 bg-[var(--color-surface-sunken)] rounded text-xs">policyengine</code> app uses Modal&apos;s <code className="px-1.5 py-0.5 bg-[var(--color-surface-sunken)] rounded text-xs">run_function</code> to snapshot the Python interpreter state after importing the models:
          </p>
          <pre className="p-4 bg-[var(--color-surface-sunken)] rounded-lg text-xs font-mono overflow-x-auto text-[var(--color-text-secondary)]">
{`def _import_uk():
    from policyengine.tax_benefit_models.uk import uk_latest
    print("UK model loaded and snapshotted")

uk_image = base_image.run_commands(
    "uv pip install --system policyengine-uk>=2.0.0"
).run_function(_import_uk)`}
          </pre>
          <p className="text-sm text-[var(--color-text-secondary)] mt-4">
            When a cold start happens, Modal restores from this snapshot rather than re-running the imports. This turns a 30+ second import into sub-second startup.
          </p>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Secrets</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Each app uses different Modal secrets:
          </p>
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <span className="px-2 py-1 bg-[var(--color-surface-sunken)] rounded text-xs font-mono text-[var(--color-text-secondary)]">policyengine-db</span>
              <p className="text-sm text-[var(--color-text-secondary)]">Database credentials for the main app (DATABASE_URL, SUPABASE_URL, SUPABASE_KEY)</p>
            </div>
            <div className="flex items-start gap-3">
              <span className="px-2 py-1 bg-[var(--color-surface-sunken)] rounded text-xs font-mono text-[var(--color-text-secondary)]">anthropic-api-key</span>
              <p className="text-sm text-[var(--color-text-secondary)]">Anthropic API key for the sandbox app (ANTHROPIC_API_KEY)</p>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Request flow</h2>
          <div className="space-y-3">
            {[
              "Client calls API endpoint (e.g. POST /household/calculate)",
              "FastAPI validates request and creates job record in Supabase",
              "FastAPI triggers Modal function asynchronously",
              "API returns job ID immediately",
              "Modal function runs calculation with pre-loaded models",
              "Modal function writes results directly to Supabase",
              "Client polls API until job status = completed",
            ].map((step, index) => (
              <div key={index} className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[var(--color-pe-green)] text-white text-xs font-medium flex items-center justify-center">
                  {index + 1}
                </span>
                <p className="text-sm text-[var(--color-text-secondary)] pt-0.5">{step}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
