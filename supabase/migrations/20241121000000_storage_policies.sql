-- Create storage policies for datasets bucket
-- Note: RLS is already enabled on storage.objects by default

-- Allow authenticated uploads to datasets bucket
CREATE POLICY IF NOT EXISTS "Allow authenticated uploads"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'datasets');

-- Allow authenticated to read from datasets bucket
CREATE POLICY IF NOT EXISTS "Allow authenticated downloads"
ON storage.objects FOR SELECT
TO authenticated
USING (bucket_id = 'datasets');

-- Allow service role full access
CREATE POLICY IF NOT EXISTS "Allow service role full access"
ON storage.objects FOR ALL
TO service_role
USING (bucket_id = 'datasets');
