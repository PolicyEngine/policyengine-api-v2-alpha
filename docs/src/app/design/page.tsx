export default function DesignPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        API hierarchy design
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Three-level architecture for simulations, analyses, and reports.
      </p>

      <div className="space-y-8">
        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Levels of analysis</h2>

          <div className="space-y-4">
            <div className="p-4 bg-[var(--color-surface-sunken)] rounded-lg">
              <div className="flex items-center gap-3 mb-2">
                <span className="px-2 py-1 bg-[var(--color-pe-green)] text-white text-xs font-medium rounded">Level 2</span>
                <h3 className="font-medium text-[var(--color-text-primary)]">Reports</h3>
              </div>
              <p className="text-sm text-[var(--color-text-secondary)]">
                AI-generated documents orchestrating multiple jobs. Future feature.
              </p>
            </div>

            <div className="p-4 bg-[var(--color-surface-sunken)] rounded-lg">
              <div className="flex items-center gap-3 mb-2">
                <span className="px-2 py-1 bg-[var(--color-pe-green)] text-white text-xs font-medium rounded">Level 1</span>
                <h3 className="font-medium text-[var(--color-text-primary)]">Analyses</h3>
              </div>
              <p className="text-sm text-[var(--color-text-secondary)] mb-3">
                Operations on simulations - thin wrappers around policyengine package functions.
              </p>
              <div className="grid grid-cols-2 gap-2">
                <code className="px-2 py-1 bg-white rounded text-xs font-mono text-[var(--color-text-secondary)]">/analysis/decile-impact/*</code>
                <code className="px-2 py-1 bg-white rounded text-xs font-mono text-[var(--color-text-secondary)]">/analysis/budget-impact/*</code>
                <code className="px-2 py-1 bg-white rounded text-xs font-mono text-[var(--color-text-secondary)]">/analysis/winners-losers/*</code>
                <code className="px-2 py-1 bg-white rounded text-xs font-mono text-[var(--color-text-secondary)]">/analysis/compare/*</code>
              </div>
            </div>

            <div className="p-4 bg-[var(--color-surface-sunken)] rounded-lg">
              <div className="flex items-center gap-3 mb-2">
                <span className="px-2 py-1 bg-[var(--color-pe-green)] text-white text-xs font-medium rounded">Level 0</span>
                <h3 className="font-medium text-[var(--color-text-primary)]">Simulations</h3>
              </div>
              <p className="text-sm text-[var(--color-text-secondary)] mb-3">
                Single world-state calculations - the foundation for all analyses.
              </p>
              <div className="grid grid-cols-2 gap-2">
                <code className="px-2 py-1 bg-white rounded text-xs font-mono text-[var(--color-text-secondary)]">/simulate/household</code>
                <code className="px-2 py-1 bg-white rounded text-xs font-mono text-[var(--color-text-secondary)]">/simulate/economy</code>
              </div>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Modal functions</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            All compute runs on Modal.com serverless functions with sub-1s cold starts.
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">Function</th>
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">Purpose</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-secondary)]">
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 font-mono text-xs">simulate_household_uk/us</td>
                  <td className="py-2">Single household calculation</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 font-mono text-xs">simulate_economy_uk/us</td>
                  <td className="py-2">Single economy simulation</td>
                </tr>
                <tr>
                  <td className="py-2 font-mono text-xs">economy_comparison_uk/us</td>
                  <td className="py-2">Economy comparison (decile impacts, budget)</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Mapping to policyengine package</h2>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">API endpoint</th>
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">policyengine function</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-secondary)]">
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 font-mono text-xs">/simulate/household</td>
                  <td className="py-2 font-mono text-xs">calculate_household_impact()</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 font-mono text-xs">/simulate/economy</td>
                  <td className="py-2 font-mono text-xs">Simulation.run()</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 font-mono text-xs">/analysis/decile-impact/*</td>
                  <td className="py-2 font-mono text-xs">calculate_decile_impacts()</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 font-mono text-xs">/analysis/budget-impact/*</td>
                  <td className="py-2 font-mono text-xs">ProgrammeStatistics</td>
                </tr>
                <tr>
                  <td className="py-2 font-mono text-xs">/analysis/winners-losers/*</td>
                  <td className="py-2 font-mono text-xs">ChangeAggregate</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Use cases</h2>

          <div className="space-y-3">
            {[
              { case: "My tax under current law", endpoint: "/simulate/household" },
              { case: "Reform impact on my household", endpoint: "/analysis/compare/household" },
              { case: "Revenue impact of reform", endpoint: "/analysis/budget-impact/economy" },
              { case: "Decile breakdown of reform", endpoint: "/analysis/decile-impact/economy" },
              { case: "Who wins and loses", endpoint: "/analysis/winners-losers/economy" },
              { case: "Full reform analysis", endpoint: "/analysis/compare/economy" },
            ].map((item) => (
              <div key={item.case} className="flex items-center justify-between py-2 border-b border-[var(--color-border)] last:border-0">
                <span className="text-sm text-[var(--color-text-secondary)]">{item.case}</span>
                <code className="px-2 py-1 bg-[var(--color-surface-sunken)] rounded text-xs font-mono text-[var(--color-text-secondary)]">
                  {item.endpoint}
                </code>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
