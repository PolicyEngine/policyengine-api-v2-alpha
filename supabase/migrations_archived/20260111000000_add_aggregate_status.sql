-- Add status and error_message columns to aggregates table
ALTER TABLE aggregates
ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS error_message TEXT;

-- Add status and error_message columns to change_aggregates table
ALTER TABLE change_aggregates
ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS error_message TEXT;

-- Create indexes for status filtering
CREATE INDEX IF NOT EXISTS idx_aggregates_status ON aggregates(status);
CREATE INDEX IF NOT EXISTS idx_change_aggregates_status ON change_aggregates(status);
