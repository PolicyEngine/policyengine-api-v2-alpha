-- Base schema for PolicyEngine API v2
-- This migration creates all tables required by SQLModel definitions

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

CREATE TYPE householdjobstatus AS ENUM ('pending', 'running', 'completed', 'failed');
CREATE TYPE simulationstatus AS ENUM ('pending', 'running', 'completed', 'failed');
CREATE TYPE reportstatus AS ENUM ('pending', 'running', 'completed', 'failed');
CREATE TYPE aggregatetype AS ENUM ('sum', 'mean', 'count');
CREATE TYPE aggregatestatus AS ENUM ('pending', 'running', 'completed', 'failed');
CREATE TYPE changeaggregatetype AS ENUM ('sum', 'mean', 'count');
CREATE TYPE changeaggregatestatus AS ENUM ('pending', 'running', 'completed', 'failed');

-- ============================================================================
-- TABLES (in dependency order - parents before children)
-- ============================================================================

-- Independent tables (no foreign keys)

CREATE TABLE dynamics (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE tax_benefit_models (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE users (
    id UUID PRIMARY KEY,
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

-- Tables with single foreign key dependency

CREATE TABLE datasets (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR,
    filepath VARCHAR NOT NULL,
    year INTEGER NOT NULL,
    is_output_dataset BOOLEAN NOT NULL,
    tax_benefit_model_id UUID NOT NULL REFERENCES tax_benefit_models(id),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE policies (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR,
    tax_benefit_model_id UUID NOT NULL REFERENCES tax_benefit_models(id),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE INDEX ix_policies_tax_benefit_model_id ON policies (tax_benefit_model_id);

CREATE TABLE tax_benefit_model_versions (
    id UUID PRIMARY KEY,
    model_id UUID NOT NULL REFERENCES tax_benefit_models(id),
    version VARCHAR NOT NULL,
    description VARCHAR,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

-- Tables with multiple foreign key dependencies

CREATE TABLE dataset_versions (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    dataset_id UUID NOT NULL REFERENCES datasets(id),
    tax_benefit_model_id UUID NOT NULL REFERENCES tax_benefit_models(id),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE household_jobs (
    id UUID PRIMARY KEY,
    tax_benefit_model_name VARCHAR NOT NULL,
    request_data JSON,
    policy_id UUID REFERENCES policies(id),
    dynamic_id UUID REFERENCES dynamics(id),
    status householdjobstatus NOT NULL,
    error_message VARCHAR,
    result JSON,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE parameters (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    label VARCHAR,
    description VARCHAR,
    data_type VARCHAR,
    unit VARCHAR,
    tax_benefit_model_version_id UUID NOT NULL REFERENCES tax_benefit_model_versions(id),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE simulations (
    id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL REFERENCES datasets(id),
    policy_id UUID REFERENCES policies(id),
    dynamic_id UUID REFERENCES dynamics(id),
    tax_benefit_model_version_id UUID NOT NULL REFERENCES tax_benefit_model_versions(id),
    output_dataset_id UUID REFERENCES datasets(id),
    status simulationstatus NOT NULL,
    error_message VARCHAR,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE user_policies (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    policy_id UUID NOT NULL REFERENCES policies(id),
    label VARCHAR,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE INDEX ix_user_policies_user_id ON user_policies (user_id);
CREATE INDEX ix_user_policies_policy_id ON user_policies (policy_id);

CREATE TABLE variables (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    entity VARCHAR NOT NULL,
    description VARCHAR,
    data_type VARCHAR,
    possible_values JSON,
    tax_benefit_model_version_id UUID NOT NULL REFERENCES tax_benefit_model_versions(id),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE parameter_values (
    id UUID PRIMARY KEY,
    parameter_id UUID NOT NULL REFERENCES parameters(id),
    value_json JSON,
    start_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    end_date TIMESTAMP WITHOUT TIME ZONE,
    policy_id UUID REFERENCES policies(id),
    dynamic_id UUID REFERENCES dynamics(id),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE reports (
    id UUID PRIMARY KEY,
    label VARCHAR NOT NULL,
    description VARCHAR,
    user_id UUID REFERENCES users(id),
    markdown TEXT,
    parent_report_id UUID REFERENCES reports(id),
    status reportstatus NOT NULL,
    error_message VARCHAR,
    baseline_simulation_id UUID REFERENCES simulations(id),
    reform_simulation_id UUID REFERENCES simulations(id),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE aggregates (
    id UUID PRIMARY KEY,
    simulation_id UUID NOT NULL REFERENCES simulations(id),
    user_id UUID REFERENCES users(id),
    report_id UUID REFERENCES reports(id),
    variable VARCHAR NOT NULL,
    aggregate_type aggregatetype NOT NULL,
    entity VARCHAR,
    filter_config JSON,
    status aggregatestatus NOT NULL,
    error_message VARCHAR,
    result FLOAT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE change_aggregates (
    id UUID PRIMARY KEY,
    baseline_simulation_id UUID NOT NULL REFERENCES simulations(id),
    reform_simulation_id UUID NOT NULL REFERENCES simulations(id),
    user_id UUID REFERENCES users(id),
    report_id UUID REFERENCES reports(id),
    variable VARCHAR NOT NULL,
    aggregate_type changeaggregatetype NOT NULL,
    entity VARCHAR,
    filter_config JSON,
    change_geq FLOAT,
    change_leq FLOAT,
    status changeaggregatestatus NOT NULL,
    error_message VARCHAR,
    result FLOAT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE decile_impacts (
    id UUID PRIMARY KEY,
    baseline_simulation_id UUID NOT NULL REFERENCES simulations(id),
    reform_simulation_id UUID NOT NULL REFERENCES simulations(id),
    report_id UUID REFERENCES reports(id),
    income_variable VARCHAR NOT NULL,
    entity VARCHAR,
    decile INTEGER NOT NULL,
    quantiles INTEGER NOT NULL,
    baseline_mean FLOAT,
    reform_mean FLOAT,
    absolute_change FLOAT,
    relative_change FLOAT,
    count_better_off FLOAT,
    count_worse_off FLOAT,
    count_no_change FLOAT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE inequality (
    id UUID PRIMARY KEY,
    simulation_id UUID NOT NULL REFERENCES simulations(id),
    report_id UUID REFERENCES reports(id),
    income_variable VARCHAR NOT NULL,
    entity VARCHAR NOT NULL,
    gini FLOAT,
    top_10_share FLOAT,
    top_1_share FLOAT,
    bottom_50_share FLOAT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE poverty (
    id UUID PRIMARY KEY,
    simulation_id UUID NOT NULL REFERENCES simulations(id),
    report_id UUID REFERENCES reports(id),
    poverty_type VARCHAR NOT NULL,
    entity VARCHAR NOT NULL,
    filter_variable VARCHAR,
    headcount FLOAT,
    total_population FLOAT,
    rate FLOAT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE program_statistics (
    id UUID PRIMARY KEY,
    baseline_simulation_id UUID NOT NULL REFERENCES simulations(id),
    reform_simulation_id UUID NOT NULL REFERENCES simulations(id),
    report_id UUID REFERENCES reports(id),
    program_name VARCHAR NOT NULL,
    entity VARCHAR NOT NULL,
    is_tax BOOLEAN NOT NULL,
    baseline_total FLOAT,
    reform_total FLOAT,
    change FLOAT,
    baseline_count FLOAT,
    reform_count FLOAT,
    winners FLOAT,
    losers FLOAT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);
