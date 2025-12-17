"use client";

import { ApiPlayground } from "@/components/api-playground";

export default function DatasetsPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Datasets
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Manage microdata datasets for tax-benefit simulations.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            List datasets
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/datasets"
            description="Retrieve all available datasets."
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Get dataset
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/datasets/:dataset_id"
            description="Retrieve a specific dataset by ID."
            pathParams={[
              {
                name: "dataset_id",
                description: "UUID of the dataset",
                example: "550e8400-e29b-41d4-a716-446655440000",
              },
            ]}
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Create dataset
          </h2>
          <ApiPlayground
            method="POST"
            endpoint="/datasets"
            description="Create a new dataset. The filepath should reference a file in Supabase Storage."
            defaultBody={{
              name: "FRS 2023-24",
              description: "Family Resources Survey representative microdata",
              filepath: "datasets/frs_2023_24_year_2026.h5",
              year: 2026,
              tax_benefit_model_version_id: "a8a20af0-b0bf-4b98-9e42-a62034f99da5",
            }}
          />
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Request parameters
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-52 font-mono text-[var(--color-pe-green)]">name</code>
              <span className="text-[var(--color-text-secondary)]">string - Human-readable dataset name</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-52 font-mono text-[var(--color-pe-green)]">description</code>
              <span className="text-[var(--color-text-secondary)]">string | null - Optional description</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-52 font-mono text-[var(--color-pe-green)]">filepath</code>
              <span className="text-[var(--color-text-secondary)]">string - Path to HDF5 file in storage</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-52 font-mono text-[var(--color-pe-green)]">year</code>
              <span className="text-[var(--color-text-secondary)]">integer - Simulation year for this dataset</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-52 font-mono text-[var(--color-pe-green)]">tax_benefit_model_version_id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Model version this dataset is compatible with</span>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Delete dataset
          </h2>
          <ApiPlayground
            method="DELETE"
            endpoint="/datasets/:dataset_id"
            description="Delete a dataset by ID."
            pathParams={[
              {
                name: "dataset_id",
                description: "UUID of the dataset to delete",
                example: "550e8400-e29b-41d4-a716-446655440000",
              },
            ]}
          />
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Dataset object
          </h2>
          <div className="space-y-3 text-sm">
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">id</code>
              <span className="text-[var(--color-text-secondary)]">UUID - Unique identifier</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">name</code>
              <span className="text-[var(--color-text-secondary)]">string - Human-readable name</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">description</code>
              <span className="text-[var(--color-text-secondary)]">string | null - Optional description</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">filepath</code>
              <span className="text-[var(--color-text-secondary)]">string - Path in storage bucket</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">year</code>
              <span className="text-[var(--color-text-secondary)]">integer - Simulation year</span>
            </div>
            <div className="flex gap-4">
              <code className="flex-shrink-0 w-40 font-mono text-[var(--color-pe-green)]">created_at</code>
              <span className="text-[var(--color-text-secondary)]">datetime - Creation timestamp</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
