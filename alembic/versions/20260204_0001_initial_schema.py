"""Initial schema (main branch state)

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-04

This migration creates all base tables for the PolicyEngine API as they
exist on the main branch, BEFORE the household CRUD changes.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables as they exist on main branch."""
    # ========================================================================
    # TIER 1: Tables with no foreign key dependencies
    # ========================================================================

    # Tax benefit models (e.g., "uk", "us")
    op.create_table(
        "tax_benefit_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # Policies (reform definitions)
    op.create_table(
        "policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Dynamics (behavioral response definitions)
    op.create_table(
        "dynamics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ========================================================================
    # TIER 2: Tables depending on tier 1
    # ========================================================================

    # Tax benefit model versions
    op.create_table(
        "tax_benefit_model_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["model_id"], ["tax_benefit_models.id"]),
    )

    # Datasets (h5 files in storage)
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("filepath", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("is_output_dataset", sa.Boolean(), nullable=False, default=False),
        sa.Column("tax_benefit_model_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tax_benefit_model_id"], ["tax_benefit_models.id"]),
    )

    # ========================================================================
    # TIER 3: Tables depending on tier 2
    # ========================================================================

    # Parameters (tax-benefit system parameters)
    op.create_table(
        "parameters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("data_type", sa.String(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("tax_benefit_model_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tax_benefit_model_version_id"], ["tax_benefit_model_versions.id"]
        ),
    )

    # Variables (tax-benefit system variables)
    op.create_table(
        "variables",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("data_type", sa.String(), nullable=True),
        sa.Column("possible_values", sa.JSON(), nullable=True),
        sa.Column("tax_benefit_model_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tax_benefit_model_version_id"], ["tax_benefit_model_versions.id"]
        ),
    )

    # Dataset versions
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("tax_benefit_model_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.ForeignKeyConstraint(["tax_benefit_model_id"], ["tax_benefit_models.id"]),
    )

    # ========================================================================
    # TIER 4: Tables depending on tier 3
    # ========================================================================

    # Parameter values (policy/dynamic parameter modifications)
    op.create_table(
        "parameter_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parameter_id", sa.Uuid(), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_id", sa.Uuid(), nullable=True),
        sa.Column("dynamic_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parameter_id"], ["parameters.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.ForeignKeyConstraint(["dynamic_id"], ["dynamics.id"]),
    )

    # Simulations (economy calculations) - NOTE: No household support yet
    op.create_table(
        "simulations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),  # Required in main
        sa.Column("policy_id", sa.Uuid(), nullable=True),
        sa.Column("dynamic_id", sa.Uuid(), nullable=True),
        sa.Column("tax_benefit_model_version_id", sa.Uuid(), nullable=False),
        sa.Column("output_dataset_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, default="pending"),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.ForeignKeyConstraint(["dynamic_id"], ["dynamics.id"]),
        sa.ForeignKeyConstraint(
            ["tax_benefit_model_version_id"], ["tax_benefit_model_versions.id"]
        ),
        sa.ForeignKeyConstraint(["output_dataset_id"], ["datasets.id"]),
    )

    # Household jobs (async household calculations) - legacy approach
    op.create_table(
        "household_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tax_benefit_model_name", sa.String(), nullable=False),
        sa.Column("request_data", sa.JSON(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=True),
        sa.Column("dynamic_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, default="pending"),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.ForeignKeyConstraint(["dynamic_id"], ["dynamics.id"]),
    )

    # ========================================================================
    # TIER 5: Tables depending on simulations
    # ========================================================================

    # Reports (analysis reports) - NOTE: No report_type yet
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("markdown", sa.Text(), nullable=True),
        sa.Column("parent_report_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, default="pending"),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("baseline_simulation_id", sa.Uuid(), nullable=True),
        sa.Column("reform_simulation_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["parent_report_id"], ["reports.id"]),
        sa.ForeignKeyConstraint(["baseline_simulation_id"], ["simulations.id"]),
        sa.ForeignKeyConstraint(["reform_simulation_id"], ["simulations.id"]),
    )

    # Aggregates (single-simulation aggregate outputs)
    op.create_table(
        "aggregates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("simulation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("variable", sa.String(), nullable=False),
        sa.Column("aggregate_type", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=True),
        sa.Column("filter_config", sa.JSON(), nullable=False, default={}),
        sa.Column("status", sa.String(), nullable=False, default="pending"),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("result", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
    )

    # Change aggregates (baseline vs reform comparison)
    op.create_table(
        "change_aggregates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("baseline_simulation_id", sa.Uuid(), nullable=False),
        sa.Column("reform_simulation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("variable", sa.String(), nullable=False),
        sa.Column("aggregate_type", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=True),
        sa.Column("filter_config", sa.JSON(), nullable=False, default={}),
        sa.Column("change_geq", sa.Float(), nullable=True),
        sa.Column("change_leq", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, default="pending"),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("result", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["baseline_simulation_id"], ["simulations.id"]),
        sa.ForeignKeyConstraint(["reform_simulation_id"], ["simulations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
    )

    # Decile impacts
    op.create_table(
        "decile_impacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("baseline_simulation_id", sa.Uuid(), nullable=False),
        sa.Column("reform_simulation_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("income_variable", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=True),
        sa.Column("decile", sa.Integer(), nullable=False),
        sa.Column("quantiles", sa.Integer(), nullable=False, default=10),
        sa.Column("baseline_mean", sa.Float(), nullable=True),
        sa.Column("reform_mean", sa.Float(), nullable=True),
        sa.Column("absolute_change", sa.Float(), nullable=True),
        sa.Column("relative_change", sa.Float(), nullable=True),
        sa.Column("count_better_off", sa.Float(), nullable=True),
        sa.Column("count_worse_off", sa.Float(), nullable=True),
        sa.Column("count_no_change", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["baseline_simulation_id"], ["simulations.id"]),
        sa.ForeignKeyConstraint(["reform_simulation_id"], ["simulations.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
    )

    # Program statistics
    op.create_table(
        "program_statistics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("baseline_simulation_id", sa.Uuid(), nullable=False),
        sa.Column("reform_simulation_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("program_name", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False),
        sa.Column("is_tax", sa.Boolean(), nullable=False, default=False),
        sa.Column("baseline_total", sa.Float(), nullable=True),
        sa.Column("reform_total", sa.Float(), nullable=True),
        sa.Column("change", sa.Float(), nullable=True),
        sa.Column("baseline_count", sa.Float(), nullable=True),
        sa.Column("reform_count", sa.Float(), nullable=True),
        sa.Column("winners", sa.Float(), nullable=True),
        sa.Column("losers", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["baseline_simulation_id"], ["simulations.id"]),
        sa.ForeignKeyConstraint(["reform_simulation_id"], ["simulations.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
    )

    # Poverty
    op.create_table(
        "poverty",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("simulation_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("poverty_type", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False, default="person"),
        sa.Column("filter_variable", sa.String(), nullable=True),
        sa.Column("headcount", sa.Float(), nullable=True),
        sa.Column("total_population", sa.Float(), nullable=True),
        sa.Column("rate", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["simulation_id"], ["simulations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_poverty_simulation_id", "poverty", ["simulation_id"])
    op.create_index("idx_poverty_report_id", "poverty", ["report_id"])

    # Inequality
    op.create_table(
        "inequality",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("simulation_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("income_variable", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False, default="household"),
        sa.Column("gini", sa.Float(), nullable=True),
        sa.Column("top_10_share", sa.Float(), nullable=True),
        sa.Column("top_1_share", sa.Float(), nullable=True),
        sa.Column("bottom_50_share", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["simulation_id"], ["simulations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_inequality_simulation_id", "inequality", ["simulation_id"])
    op.create_index("idx_inequality_report_id", "inequality", ["report_id"])


def downgrade() -> None:
    """Drop all tables in reverse order."""
    # Tier 5
    op.drop_index("idx_inequality_report_id", "inequality")
    op.drop_index("idx_inequality_simulation_id", "inequality")
    op.drop_table("inequality")
    op.drop_index("idx_poverty_report_id", "poverty")
    op.drop_index("idx_poverty_simulation_id", "poverty")
    op.drop_table("poverty")
    op.drop_table("program_statistics")
    op.drop_table("decile_impacts")
    op.drop_table("change_aggregates")
    op.drop_table("aggregates")
    op.drop_table("reports")

    # Tier 4
    op.drop_table("household_jobs")
    op.drop_table("simulations")
    op.drop_table("parameter_values")

    # Tier 3
    op.drop_table("dataset_versions")
    op.drop_table("variables")
    op.drop_table("parameters")

    # Tier 2
    op.drop_table("datasets")
    op.drop_table("tax_benefit_model_versions")

    # Tier 1
    op.drop_table("dynamics")
    op.drop_table("policies")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
    op.drop_table("tax_benefit_models")
