"use client";

import { ApiPlayground } from "@/components/api-playground";

export default function TaxBenefitModelsPage() {
  return (
    <div className="max-w-4xl">
      <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] mb-4">
        Tax benefit models
      </h1>
      <p className="text-lg text-[var(--color-text-secondary)] mb-8">
        Available tax-benefit system models (UK and US). Each model has versions with associated variables and parameters.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            List models
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/tax-benefit-models"
            description="Retrieve all available tax-benefit models."
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Get model
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/tax-benefit-models/:model_id"
            description="Retrieve a specific model by ID."
            pathParams={[
              {
                name: "model_id",
                description: "UUID of the model",
                example: "bb0e8400-e29b-41d4-a716-446655440000",
              },
            ]}
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            List model versions
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/tax-benefit-model-versions"
            description="Retrieve all model versions."
          />
        </section>

        <section>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-4">
            Get model version
          </h2>
          <ApiPlayground
            method="GET"
            endpoint="/tax-benefit-model-versions/:version_id"
            description="Retrieve a specific model version by ID."
            pathParams={[
              {
                name: "version_id",
                description: "UUID of the version",
                example: "cc0e8400-e29b-41d4-a716-446655440000",
              },
            ]}
          />
        </section>

        <section className="p-6 border border-[var(--color-border)] rounded-xl bg-white">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">
            Available models
          </h2>
          <div className="space-y-4">
            <div className="p-3 bg-[var(--color-surface-sunken)] rounded-lg">
              <code className="font-mono text-[var(--color-pe-green)]">policyengine-uk</code>
              <p className="text-sm text-[var(--color-text-secondary)] mt-1">
                UK tax and benefit system including income tax, NI, benefits, and more.
              </p>
            </div>
            <div className="p-3 bg-[var(--color-surface-sunken)] rounded-lg">
              <code className="font-mono text-[var(--color-pe-green)]">policyengine-us</code>
              <p className="text-sm text-[var(--color-text-secondary)] mt-1">
                US federal and state tax system including income tax, payroll tax, SNAP, TANF, etc.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
