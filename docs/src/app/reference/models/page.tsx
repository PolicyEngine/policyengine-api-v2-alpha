export default function ModelsPage() {
  const models = [
    {
      name: "Dataset",
      description: "Microdata file metadata",
      fields: [
        { name: "id", type: "UUID", description: "Unique identifier" },
        { name: "name", type: "string", description: "Human-readable name" },
        { name: "description", type: "string | null", description: "Optional description" },
        { name: "filepath", type: "string", description: "Path in storage bucket" },
        { name: "year", type: "integer", description: "Simulation year" },
        { name: "tax_benefit_model_version_id", type: "UUID", description: "Associated model version" },
        { name: "created_at", type: "datetime", description: "Creation timestamp" },
      ],
    },
    {
      name: "Policy",
      description: "Parameter reform definition",
      fields: [
        { name: "id", type: "UUID", description: "Unique identifier" },
        { name: "name", type: "string", description: "Policy name" },
        { name: "description", type: "string | null", description: "Optional description" },
        { name: "parameter_values", type: "ParameterValue[]", description: "Parameter modifications" },
        { name: "created_at", type: "datetime", description: "Creation timestamp" },
      ],
    },
    {
      name: "ParameterValue",
      description: "Single parameter modification",
      fields: [
        { name: "id", type: "UUID", description: "Unique identifier" },
        { name: "parameter_id", type: "UUID", description: "Reference to parameter" },
        { name: "value_json", type: "object", description: "New parameter value" },
        { name: "start_date", type: "date", description: "Effective start date" },
        { name: "end_date", type: "date", description: "Effective end date" },
      ],
    },
    {
      name: "Simulation",
      description: "Tax-benefit microsimulation run",
      fields: [
        { name: "id", type: "UUID", description: "Deterministic identifier" },
        { name: "dataset_id", type: "UUID", description: "Input dataset" },
        { name: "tax_benefit_model_version_id", type: "UUID", description: "Model version" },
        { name: "policy_id", type: "UUID | null", description: "Optional reform policy" },
        { name: "dynamic_id", type: "UUID | null", description: "Optional behavioural model" },
        { name: "status", type: "SimulationStatus", description: "Processing status" },
        { name: "error_message", type: "string | null", description: "Error if failed" },
        { name: "started_at", type: "datetime | null", description: "Processing start time" },
        { name: "completed_at", type: "datetime | null", description: "Processing end time" },
      ],
    },
    {
      name: "Report",
      description: "Economic impact analysis container",
      fields: [
        { name: "id", type: "UUID", description: "Deterministic identifier" },
        { name: "label", type: "string", description: "Human-readable label" },
        { name: "baseline_simulation_id", type: "UUID", description: "Baseline simulation" },
        { name: "reform_simulation_id", type: "UUID", description: "Reform simulation" },
        { name: "status", type: "ReportStatus", description: "Processing status" },
        { name: "error_message", type: "string | null", description: "Error if failed" },
        { name: "created_at", type: "datetime", description: "Creation timestamp" },
      ],
    },
    {
      name: "DecileImpact",
      description: "Distributional impact by income decile",
      fields: [
        { name: "id", type: "UUID", description: "Unique identifier" },
        { name: "report_id", type: "UUID", description: "Parent report" },
        { name: "decile", type: "integer", description: "Income decile (1-10)" },
        { name: "income_variable", type: "string", description: "Variable for ranking" },
        { name: "baseline_mean", type: "number", description: "Baseline mean income" },
        { name: "reform_mean", type: "number", description: "Reform mean income" },
        { name: "absolute_change", type: "number", description: "Absolute difference" },
        { name: "relative_change", type: "number", description: "Percentage change" },
        { name: "count_better_off", type: "number", description: "Winners count" },
        { name: "count_worse_off", type: "number", description: "Losers count" },
        { name: "count_no_change", type: "number", description: "No change count" },
      ],
    },
    {
      name: "ProgramStatistics",
      description: "Tax/benefit program impact statistics",
      fields: [
        { name: "id", type: "UUID", description: "Unique identifier" },
        { name: "report_id", type: "UUID", description: "Parent report" },
        { name: "program_name", type: "string", description: "Program name" },
        { name: "entity", type: "string", description: "Entity level" },
        { name: "is_tax", type: "boolean", description: "True for taxes" },
        { name: "baseline_total", type: "number", description: "Baseline total" },
        { name: "reform_total", type: "number", description: "Reform total" },
        { name: "change", type: "number", description: "Difference" },
        { name: "baseline_count", type: "number", description: "Baseline recipients" },
        { name: "reform_count", type: "number", description: "Reform recipients" },
        { name: "winners", type: "number", description: "Winners count" },
        { name: "losers", type: "number", description: "Losers count" },
      ],
    },
    {
      name: "AggregateOutput",
      description: "Computed aggregate statistic",
      fields: [
        { name: "id", type: "UUID", description: "Unique identifier" },
        { name: "simulation_id", type: "UUID", description: "Source simulation" },
        { name: "variable", type: "string", description: "Variable name" },
        { name: "aggregate_type", type: "AggregateType", description: "Calculation type" },
        { name: "entity", type: "string", description: "Entity level" },
        { name: "filter_config", type: "object | null", description: "Optional filter" },
        { name: "result", type: "number", description: "Computed value" },
      ],
    },
  ];

  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Models
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Data models used throughout the API. All models use UUID identifiers and include timestamps.
      </p>

      <div className="space-y-8">
        {models.map((model) => (
          <section
            key={model.name}
            className="p-6 border border-[var(--color-border)] rounded-xl bg-white"
          >
            <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-2">
              {model.name}
            </h2>
            <p className="text-sm text-[var(--color-text-secondary)] mb-4">
              {model.description}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)]">
                    <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-muted)]">
                      Field
                    </th>
                    <th className="text-left py-2 pr-4 font-medium text-[var(--color-text-muted)]">
                      Type
                    </th>
                    <th className="text-left py-2 font-medium text-[var(--color-text-muted)]">
                      Description
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {model.fields.map((field) => (
                    <tr key={field.name} className="border-b border-[var(--color-border)] last:border-0">
                      <td className="py-2 pr-4">
                        <code className="font-mono text-[var(--color-pe-green)]">{field.name}</code>
                      </td>
                      <td className="py-2 pr-4">
                        <code className="font-mono text-[var(--color-text-secondary)]">{field.type}</code>
                      </td>
                      <td className="py-2 text-[var(--color-text-secondary)]">{field.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
