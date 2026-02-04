-- Add poverty and inequality tables for economic analysis

CREATE TABLE IF NOT EXISTS poverty (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    simulation_id UUID NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
    poverty_type VARCHAR NOT NULL,
    entity VARCHAR NOT NULL DEFAULT 'person',
    filter_variable VARCHAR,
    headcount FLOAT,
    total_population FLOAT,
    rate FLOAT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inequality (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    simulation_id UUID NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
    income_variable VARCHAR NOT NULL,
    entity VARCHAR NOT NULL DEFAULT 'household',
    gini FLOAT,
    top_10_share FLOAT,
    top_1_share FLOAT,
    bottom_50_share FLOAT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_poverty_simulation_id ON poverty(simulation_id);
CREATE INDEX IF NOT EXISTS idx_poverty_report_id ON poverty(report_id);
CREATE INDEX IF NOT EXISTS idx_inequality_simulation_id ON inequality(simulation_id);
CREATE INDEX IF NOT EXISTS idx_inequality_report_id ON inequality(report_id);
