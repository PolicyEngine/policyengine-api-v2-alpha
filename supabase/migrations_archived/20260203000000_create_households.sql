-- Create stored households table for persisting household definitions.

CREATE TABLE IF NOT EXISTS households (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tax_benefit_model_name TEXT NOT NULL,
    year INTEGER NOT NULL,
    label TEXT,
    household_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_households_model_name ON households (tax_benefit_model_name);
CREATE INDEX idx_households_year ON households (year);
