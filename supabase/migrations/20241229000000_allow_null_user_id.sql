-- Allow null user_id in reports table for anonymous API-triggered reports
ALTER TABLE reports ALTER COLUMN user_id DROP NOT NULL;
