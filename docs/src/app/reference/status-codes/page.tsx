export default function StatusCodesPage() {
  const statusCodes = [
    {
      code: "200",
      name: "OK",
      description: "Request succeeded. Response body contains the requested data.",
      color: "bg-green-100 text-green-700",
    },
    {
      code: "201",
      name: "Created",
      description: "Resource created successfully. Response body contains the new resource.",
      color: "bg-green-100 text-green-700",
    },
    {
      code: "204",
      name: "No Content",
      description: "Request succeeded with no response body (e.g., DELETE operations).",
      color: "bg-green-100 text-green-700",
    },
    {
      code: "400",
      name: "Bad Request",
      description: "Invalid request body or parameters. Check the error message for details.",
      color: "bg-red-100 text-red-700",
    },
    {
      code: "404",
      name: "Not Found",
      description: "The requested resource does not exist.",
      color: "bg-red-100 text-red-700",
    },
    {
      code: "422",
      name: "Unprocessable Entity",
      description: "Request body failed validation. Response contains field-level errors.",
      color: "bg-red-100 text-red-700",
    },
    {
      code: "500",
      name: "Internal Server Error",
      description: "Unexpected server error. Please report if persistent.",
      color: "bg-red-100 text-red-700",
    },
  ];

  const simulationStatuses = [
    {
      status: "pending",
      description: "Queued and waiting for a worker to pick up",
      color: "bg-gray-100 text-gray-700",
    },
    {
      status: "running",
      description: "Currently being processed by a worker",
      color: "bg-blue-100 text-blue-700",
    },
    {
      status: "completed",
      description: "Successfully finished processing",
      color: "bg-green-100 text-green-700",
    },
    {
      status: "failed",
      description: "An error occurred during processing",
      color: "bg-red-100 text-red-700",
    },
  ];

  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Status codes
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        HTTP status codes and resource statuses used by the API.
      </p>

      <div className="space-y-8">
        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            HTTP status codes
          </h2>
          <div className="space-y-4">
            {statusCodes.map((item) => (
              <div key={item.code} className="flex items-start gap-4">
                <span className={`px-2.5 py-1 rounded text-sm font-mono font-medium ${item.color}`}>
                  {item.code}
                </span>
                <div>
                  <span className="font-medium text-[var(--color-text-primary)]">{item.name}</span>
                  <p className="text-sm text-[var(--color-text-secondary)] mt-0.5">
                    {item.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Simulation status
          </h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Simulations and reports progress through these statuses:
          </p>
          <div className="space-y-4">
            {simulationStatuses.map((item) => (
              <div key={item.status} className="flex items-start gap-4">
                <span className={`px-2.5 py-1 rounded text-sm font-mono font-medium ${item.color}`}>
                  {item.status}
                </span>
                <p className="text-sm text-[var(--color-text-secondary)] pt-0.5">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Error response format
          </h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Error responses follow a consistent format:
          </p>
          <pre className="p-4 bg-[var(--color-code-bg)] text-[var(--color-code-text)] rounded-lg text-sm overflow-x-auto">
{`{
  "detail": "Error message describing what went wrong"
}`}
          </pre>
          <p className="text-sm text-[var(--color-text-secondary)] mt-4">
            Validation errors (422) include field-level details:
          </p>
          <pre className="p-4 bg-[var(--color-code-bg)] text-[var(--color-code-text)] rounded-lg text-sm overflow-x-auto mt-2">
{`{
  "detail": [
    {
      "loc": ["body", "dataset_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}`}
          </pre>
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Polling strategy
          </h2>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            For async operations like simulations and reports:
          </p>
          <ol className="list-decimal list-inside space-y-2 text-sm text-[var(--color-text-secondary)]">
            <li>Submit the request (POST) and receive the resource with pending status</li>
            <li>Poll the GET endpoint every 2-5 seconds</li>
            <li>Check the status field in the response</li>
            <li>Stop polling when status is completed or failed</li>
            <li>If failed, check the error_message field for details</li>
          </ol>
          <div className="mt-4 p-3 bg-[var(--color-surface-sunken)] rounded-lg">
            <p className="text-xs text-[var(--color-text-muted)]">
              <strong>Tip:</strong> Use exponential backoff for production systems to avoid overwhelming the API during high load.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
