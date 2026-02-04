-- Add indexes to parameter_values table for query optimization
-- This migration improves query performance for filtering by parameter_id and policy_id

-- Composite index for the most common query pattern (filtering by both)
CREATE INDEX IF NOT EXISTS idx_parameter_values_parameter_policy
ON parameter_values(parameter_id, policy_id);

-- Single index on policy_id for filtering by policy alone
CREATE INDEX IF NOT EXISTS idx_parameter_values_policy
ON parameter_values(policy_id);

-- Partial index for baseline values (policy_id IS NULL)
-- This optimizes the common "get current law values" query
CREATE INDEX IF NOT EXISTS idx_parameter_values_baseline
ON parameter_values(parameter_id)
WHERE policy_id IS NULL;
