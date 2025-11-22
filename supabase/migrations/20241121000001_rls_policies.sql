-- Enable RLS on all application tables
ALTER TABLE datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE dataset_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE simulations ENABLE ROW LEVEL SECURITY;
ALTER TABLE policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE dynamics ENABLE ROW LEVEL SECURITY;
ALTER TABLE aggregates ENABLE ROW LEVEL SECURITY;
ALTER TABLE change_aggregates ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_benefit_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_benefit_model_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE variables ENABLE ROW LEVEL SECURITY;
ALTER TABLE parameters ENABLE ROW LEVEL SECURITY;
ALTER TABLE parameter_values ENABLE ROW LEVEL SECURITY;

-- Service role policies (full access to everything)
DO $$
BEGIN
    -- Datasets
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'datasets' AND policyname = 'Service role full access') THEN
        CREATE POLICY "Service role full access" ON datasets FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    -- Dataset versions
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'dataset_versions' AND policyname = 'Service role full access') THEN
        CREATE POLICY "Service role full access" ON dataset_versions FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    -- Simulations
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'simulations' AND policyname = 'Service role full access') THEN
        CREATE POLICY "Service role full access" ON simulations FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    -- Policies
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'policies' AND policyname = 'Service role full access') THEN
        CREATE POLICY "Service role full access" ON policies FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    -- Dynamics
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'dynamics' AND policyname = 'Service role full access') THEN
        CREATE POLICY "Service role full access" ON dynamics FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    -- Aggregates
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'aggregates' AND policyname = 'Service role full access') THEN
        CREATE POLICY "Service role full access" ON aggregates FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    -- Change aggregates
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'change_aggregates' AND policyname = 'Service role full access') THEN
        CREATE POLICY "Service role full access" ON change_aggregates FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    -- Tax benefit models
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'tax_benefit_models' AND policyname = 'Service role full access') THEN
        CREATE POLICY "Service role full access" ON tax_benefit_models FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    -- Tax benefit model versions
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'tax_benefit_model_versions' AND policyname = 'Service role full access') THEN
        CREATE POLICY "Service role full access" ON tax_benefit_model_versions FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    -- Variables
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'variables' AND policyname = 'Service role full access') THEN
        CREATE POLICY "Service role full access" ON variables FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    -- Parameters
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'parameters' AND policyname = 'Service role full access') THEN
        CREATE POLICY "Service role full access" ON parameters FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;

    -- Parameter values
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'parameter_values' AND policyname = 'Service role full access') THEN
        CREATE POLICY "Service role full access" ON parameter_values FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

-- Public read access for read-only tables
DO $$
BEGIN
    -- Tax benefit models (read-only for public)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'tax_benefit_models' AND policyname = 'Public read access') THEN
        CREATE POLICY "Public read access" ON tax_benefit_models FOR SELECT TO anon, authenticated USING (true);
    END IF;

    -- Tax benefit model versions (read-only for public)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'tax_benefit_model_versions' AND policyname = 'Public read access') THEN
        CREATE POLICY "Public read access" ON tax_benefit_model_versions FOR SELECT TO anon, authenticated USING (true);
    END IF;

    -- Variables (read-only for public)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'variables' AND policyname = 'Public read access') THEN
        CREATE POLICY "Public read access" ON variables FOR SELECT TO anon, authenticated USING (true);
    END IF;

    -- Parameters (read-only for public)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'parameters' AND policyname = 'Public read access') THEN
        CREATE POLICY "Public read access" ON parameters FOR SELECT TO anon, authenticated USING (true);
    END IF;

    -- Parameter values (read-only for public)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'parameter_values' AND policyname = 'Public read access') THEN
        CREATE POLICY "Public read access" ON parameter_values FOR SELECT TO anon, authenticated USING (true);
    END IF;

    -- Datasets (read-only for public)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'datasets' AND policyname = 'Public read access') THEN
        CREATE POLICY "Public read access" ON datasets FOR SELECT TO anon, authenticated USING (true);
    END IF;

    -- Dataset versions (read-only for public)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'dataset_versions' AND policyname = 'Public read access') THEN
        CREATE POLICY "Public read access" ON dataset_versions FOR SELECT TO anon, authenticated USING (true);
    END IF;
END $$;

-- User-created content policies
DO $$
BEGIN
    -- Simulations (users can create and read their own)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'simulations' AND policyname = 'Users can create simulations') THEN
        CREATE POLICY "Users can create simulations" ON simulations FOR INSERT TO anon, authenticated WITH CHECK (true);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'simulations' AND policyname = 'Users can read simulations') THEN
        CREATE POLICY "Users can read simulations" ON simulations FOR SELECT TO anon, authenticated USING (true);
    END IF;

    -- Policies (users can create and read their own)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'policies' AND policyname = 'Users can create policies') THEN
        CREATE POLICY "Users can create policies" ON policies FOR INSERT TO anon, authenticated WITH CHECK (true);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'policies' AND policyname = 'Users can read policies') THEN
        CREATE POLICY "Users can read policies" ON policies FOR SELECT TO anon, authenticated USING (true);
    END IF;

    -- Dynamics (users can create and read their own)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'dynamics' AND policyname = 'Users can create dynamics') THEN
        CREATE POLICY "Users can create dynamics" ON dynamics FOR INSERT TO anon, authenticated WITH CHECK (true);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'dynamics' AND policyname = 'Users can read dynamics') THEN
        CREATE POLICY "Users can read dynamics" ON dynamics FOR SELECT TO anon, authenticated USING (true);
    END IF;

    -- Aggregates (read access for all)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'aggregates' AND policyname = 'Users can read aggregates') THEN
        CREATE POLICY "Users can read aggregates" ON aggregates FOR SELECT TO anon, authenticated USING (true);
    END IF;

    -- Change aggregates (read access for all)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'change_aggregates' AND policyname = 'Users can read change aggregates') THEN
        CREATE POLICY "Users can read change aggregates" ON change_aggregates FOR SELECT TO anon, authenticated USING (true);
    END IF;
END $$;
