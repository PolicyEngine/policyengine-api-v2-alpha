-- Create user-household associations table for linking users to saved households.

CREATE TABLE IF NOT EXISTS user_household_associations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    country_id TEXT NOT NULL,
    label TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_user_household_assoc_user ON user_household_associations (user_id);
CREATE INDEX idx_user_household_assoc_household ON user_household_associations (household_id);
