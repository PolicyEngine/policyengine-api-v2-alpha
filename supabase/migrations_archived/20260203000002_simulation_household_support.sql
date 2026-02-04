-- Add simulation_type as TEXT (SQLModel enum maps to text)
ALTER TABLE simulations ADD COLUMN simulation_type TEXT NOT NULL DEFAULT 'economy';

-- Make dataset_id nullable (was required)
ALTER TABLE simulations ALTER COLUMN dataset_id DROP NOT NULL;

-- Add household support columns
ALTER TABLE simulations ADD COLUMN household_id UUID REFERENCES households(id);
ALTER TABLE simulations ADD COLUMN household_result JSONB;

-- Indexes
CREATE INDEX idx_simulations_household ON simulations (household_id);
CREATE INDEX idx_simulations_type ON simulations (simulation_type);

-- Add report_type to reports
ALTER TABLE reports ADD COLUMN report_type TEXT;
