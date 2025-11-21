-- Create storage policies for datasets bucket
-- Note: RLS is already enabled on storage.objects by default

DO $$
BEGIN
    -- Allow authenticated uploads to datasets bucket
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'storage'
        AND tablename = 'objects'
        AND policyname = 'Allow authenticated uploads'
    ) THEN
        CREATE POLICY "Allow authenticated uploads"
        ON storage.objects FOR INSERT
        TO authenticated
        WITH CHECK (bucket_id = 'datasets');
    END IF;

    -- Allow authenticated to read from datasets bucket
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'storage'
        AND tablename = 'objects'
        AND policyname = 'Allow authenticated downloads'
    ) THEN
        CREATE POLICY "Allow authenticated downloads"
        ON storage.objects FOR SELECT
        TO authenticated
        USING (bucket_id = 'datasets');
    END IF;

    -- Allow service role full access
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'storage'
        AND tablename = 'objects'
        AND policyname = 'Allow service role full access'
    ) THEN
        CREATE POLICY "Allow service role full access"
        ON storage.objects FOR ALL
        TO service_role
        USING (bucket_id = 'datasets');
    END IF;
END $$;
