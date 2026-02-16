export default function ArchitecturePage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Architecture
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        The PolicyEngine API v2 is a distributed system for running tax-benefit microsimulations with persistence and async processing.
      </p>

      <div className="space-y-8">
        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Components</h2>

          <div className="space-y-6">
            <div>
              <h3 className="font-medium text-[var(--color-text-primary)] mb-2">API server</h3>
              <p className="text-sm text-[var(--color-text-secondary)]">
                FastAPI application exposing RESTful endpoints for creating and managing datasets, defining policy reforms, queueing simulations, and computing aggregates. The server validates requests, persists to PostgreSQL, and queues background tasks.
              </p>
            </div>

            <div>
              <h3 className="font-medium text-[var(--color-text-primary)] mb-2">Database</h3>
              <p className="text-sm text-[var(--color-text-secondary)] mb-3">
                PostgreSQL (via Supabase) stores all persistent data using SQLModel for type-safe ORM with Pydantic integration.
              </p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {["datasets", "policies", "simulations", "aggregates", "reports", "decile_impacts", "program_statistics", "parameters"].map((table) => (
                  <span key={table} className="px-2 py-1 bg-[var(--color-surface-sunken)] rounded text-xs font-mono text-[var(--color-text-secondary)]">
                    {table}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <h3 className="font-medium text-[var(--color-text-primary)] mb-2">Worker</h3>
              <p className="text-sm text-[var(--color-text-secondary)]">
                Background workers poll for pending simulations and reports. They load datasets from storage, run PolicyEngine simulations, compute aggregates and impact statistics, then store results to the database.
              </p>
            </div>

            <div>
              <h3 className="font-medium text-[var(--color-text-primary)] mb-2">Storage</h3>
              <p className="text-sm text-[var(--color-text-secondary)]">
                Dataset files (HDF5 format) are stored in Supabase Storage with local caching for performance. The storage layer handles downloads and caching transparently.
              </p>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Request flow</h2>

          <div className="space-y-3">
            {[
              "Client creates simulation via POST /analysis/economic-impact",
              "API validates request and persists simulation + report records",
              "API returns pending status immediately",
              "Worker picks up pending simulation from queue",
              "Worker loads dataset and runs PolicyEngine simulation",
              "Worker updates simulation status to completed",
              "Worker picks up pending report",
              "Worker computes decile impacts and program statistics",
              "Client polls GET /analysis/economic-impact/{id} to check status",
              "Once complete, response includes full analysis results",
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

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Data models</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            All models follow Pydantic/SQLModel patterns for type safety across API, database, and business logic:
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 bg-[var(--color-surface-sunken)] rounded-lg">
              <code className="text-sm font-mono text-[var(--color-pe-green)]">Base</code>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">Shared fields across models</p>
            </div>
            <div className="p-3 bg-[var(--color-surface-sunken)] rounded-lg">
              <code className="text-sm font-mono text-[var(--color-pe-green)]">Table</code>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">Database model with ID and timestamps</p>
            </div>
            <div className="p-3 bg-[var(--color-surface-sunken)] rounded-lg">
              <code className="text-sm font-mono text-[var(--color-pe-green)]">Create</code>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">Request schema (no ID)</p>
            </div>
            <div className="p-3 bg-[var(--color-surface-sunken)] rounded-lg">
              <code className="text-sm font-mono text-[var(--color-pe-green)]">Read</code>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">Response schema (with ID and timestamps)</p>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Scaling</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h4 className="font-medium text-[var(--color-text-primary)] text-sm mb-1">API scaling</h4>
              <p className="text-xs text-[var(--color-text-secondary)]">
                Multiple uvicorn workers behind load balancer for horizontal scaling.
              </p>
            </div>
            <div>
              <h4 className="font-medium text-[var(--color-text-primary)] text-sm mb-1">Worker scaling</h4>
              <p className="text-xs text-[var(--color-text-secondary)]">
                Increase worker count for parallel simulation processing.
              </p>
            </div>
            <div>
              <h4 className="font-medium text-[var(--color-text-primary)] text-sm mb-1">Database</h4>
              <p className="text-xs text-[var(--color-text-secondary)]">
                PostgreSQL supports read replicas for high read throughput.
              </p>
            </div>
            <div>
              <h4 className="font-medium text-[var(--color-text-primary)] text-sm mb-1">Caching</h4>
              <p className="text-xs text-[var(--color-text-secondary)]">
                Deterministic UUIDs ensure same requests reuse cached results.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
