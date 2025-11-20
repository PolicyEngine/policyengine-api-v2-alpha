-- Initial schema for PolicyEngine API

-- Create storage bucket for datasets
INSERT INTO storage.buckets (id, name, public)
VALUES ('datasets', 'datasets', true)
ON CONFLICT (id) DO NOTHING;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Public read access for datasets" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated uploads for datasets" ON storage.objects;

-- Allow public read access to datasets bucket
CREATE POLICY "Public read access for datasets"
ON storage.objects FOR SELECT
USING (bucket_id = 'datasets');

-- Allow authenticated uploads to datasets bucket
CREATE POLICY "Authenticated uploads for datasets"
ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'datasets' AND auth.role() = 'authenticated');
