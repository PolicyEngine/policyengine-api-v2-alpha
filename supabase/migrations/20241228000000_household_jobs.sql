-- Create household_jobs table for async household calculations

CREATE TABLE IF NOT EXISTS household_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tax_benefit_model_name TEXT NOT NULL,
    request_data JSONB NOT NULL,
    policy_id UUID REFERENCES policies(id),
    dynamic_id UUID REFERENCES dynamics(id),
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Index for polling by status
CREATE INDEX IF NOT EXISTS idx_household_jobs_status ON household_jobs(status);

-- Index for looking up by id
CREATE INDEX IF NOT EXISTS idx_household_jobs_id ON household_jobs(id);

-- Enable RLS
ALTER TABLE household_jobs ENABLE ROW LEVEL SECURITY;

-- Allow public read access (jobs are not sensitive)
CREATE POLICY "Allow public read access to household_jobs"
    ON household_jobs
    FOR SELECT
    USING (true);

-- Allow public insert (anyone can create a job)
CREATE POLICY "Allow public insert to household_jobs"
    ON household_jobs
    FOR INSERT
    WITH CHECK (true);

-- Allow service role to update (for Modal functions)
CREATE POLICY "Allow service role to update household_jobs"
    ON household_jobs
    FOR UPDATE
    USING (true);
