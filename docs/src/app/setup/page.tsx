export default function SetupPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Environment setup
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Environment variables across services: local dev, Cloud Run, Modal, and GitHub Actions.
      </p>

      <div className="space-y-8">
        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Overview</h2>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">Service</th>
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">Config location</th>
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">Secrets storage</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-secondary)]">
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2">Local dev</td>
                  <td className="py-2 font-mono text-xs">.env file</td>
                  <td className="py-2">Local file</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2">Cloud Run (API)</td>
                  <td className="py-2 font-mono text-xs">Terraform</td>
                  <td className="py-2">GitHub Secrets</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2">Modal.com</td>
                  <td className="py-2 font-mono text-xs">Modal secrets</td>
                  <td className="py-2">Modal dashboard</td>
                </tr>
                <tr>
                  <td className="py-2">GitHub Actions</td>
                  <td className="py-2 font-mono text-xs">Workflow files</td>
                  <td className="py-2">GitHub Secrets</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Local development</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Copy <code className="px-1 py-0.5 bg-[var(--color-surface-sunken)] rounded text-xs">.env.example</code> to <code className="px-1 py-0.5 bg-[var(--color-surface-sunken)] rounded text-xs">.env</code> and configure:
          </p>

          <div className="bg-[var(--color-surface-sunken)] rounded-lg p-4 font-mono text-xs overflow-x-auto">
            <pre className="text-[var(--color-text-secondary)]">{`# Supabase (from \`supabase start\` output)
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres

# Storage
STORAGE_BUCKET=datasets

# API
API_TITLE=PolicyEngine API
API_VERSION=0.1.0
API_PORT=8000
DEBUG=true

# Observability
LOGFIRE_TOKEN=...
LOGFIRE_ENVIRONMENT=local

# Modal (for local testing)
MODAL_TOKEN_ID=ak-...
MODAL_TOKEN_SECRET=as-...`}</pre>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Modal.com secrets</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Modal functions read from a secret named <code className="px-1 py-0.5 bg-[var(--color-surface-sunken)] rounded text-xs">policyengine-db</code>:
          </p>

          <div className="bg-[var(--color-surface-sunken)] rounded-lg p-4 font-mono text-xs overflow-x-auto mb-4">
            <pre className="text-[var(--color-text-secondary)]">{`modal secret create policyengine-db \\
  DATABASE_URL="postgresql://..." \\
  SUPABASE_URL="https://xxx.supabase.co" \\
  SUPABASE_KEY="eyJ..." \\
  STORAGE_BUCKET="datasets"`}</pre>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">Key</th>
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">Description</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-secondary)]">
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 font-mono text-xs">DATABASE_URL</td>
                  <td className="py-2">Supabase Postgres (use connection pooler)</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 font-mono text-xs">SUPABASE_URL</td>
                  <td className="py-2">Supabase project URL</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2 font-mono text-xs">SUPABASE_KEY</td>
                  <td className="py-2">Supabase anon or service key</td>
                </tr>
                <tr>
                  <td className="py-2 font-mono text-xs">STORAGE_BUCKET</td>
                  <td className="py-2">Supabase storage bucket name</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">GitHub Actions</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Required secrets for CI/CD (Settings → Secrets):
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h3 className="font-medium text-[var(--color-text-primary)] text-sm mb-2">Secrets</h3>
              <div className="space-y-1">
                {["SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_DB_URL", "LOGFIRE_TOKEN", "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "GCP_WORKLOAD_IDENTITY_PROVIDER", "GCP_SERVICE_ACCOUNT"].map((secret) => (
                  <div key={secret} className="px-2 py-1 bg-[var(--color-surface-sunken)] rounded text-xs font-mono text-[var(--color-text-secondary)]">
                    {secret}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h3 className="font-medium text-[var(--color-text-primary)] text-sm mb-2">Variables</h3>
              <div className="space-y-1">
                {["GCP_PROJECT_ID", "GCP_REGION", "PROJECT_NAME", "API_SERVICE_NAME"].map((variable) => (
                  <div key={variable} className="px-2 py-1 bg-[var(--color-surface-sunken)] rounded text-xs font-mono text-[var(--color-text-secondary)]">
                    {variable}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">Database URLs</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Supabase provides multiple connection options:
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">Type</th>
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">Use case</th>
                  <th className="text-left py-2 font-medium text-[var(--color-text-primary)]">Port</th>
                </tr>
              </thead>
              <tbody className="text-[var(--color-text-secondary)]">
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2">Direct</td>
                  <td className="py-2">Local dev</td>
                  <td className="py-2 font-mono text-xs">54322</td>
                </tr>
                <tr className="border-b border-[var(--color-border)]">
                  <td className="py-2">Pooler (transaction)</td>
                  <td className="py-2">Cloud Run, Modal</td>
                  <td className="py-2 font-mono text-xs">6543</td>
                </tr>
                <tr>
                  <td className="py-2">Pooler (session)</td>
                  <td className="py-2">Long connections</td>
                  <td className="py-2 font-mono text-xs">5432</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="text-sm text-[var(--color-text-muted)] mt-4">
            Use the transaction pooler (port 6543) for serverless environments - handles IPv4 and connection limits.
          </p>
        </section>
      </div>
    </div>
  );
}
