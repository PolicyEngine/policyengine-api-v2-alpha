-- Add simulation_modifier column to policies table
-- Stores Python code defining custom variable formulas for structural reforms

ALTER TABLE policies
ADD COLUMN IF NOT EXISTS simulation_modifier TEXT;

COMMENT ON COLUMN policies.simulation_modifier IS 'Python code defining custom variable formulas for structural reforms';
