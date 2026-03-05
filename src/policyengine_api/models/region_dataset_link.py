"""Link table for many-to-many relationship between regions and datasets."""

from uuid import UUID

from sqlmodel import Field, SQLModel


class RegionDatasetLink(SQLModel, table=True):
    """Join table linking regions to their available datasets.

    Each region can have multiple datasets (one per year), and each
    dataset can be shared across multiple regions (e.g., a state dataset
    used by both the state region and its place/city regions).
    """

    __tablename__ = "region_datasets"

    region_id: UUID = Field(foreign_key="regions.id", primary_key=True)
    dataset_id: UUID = Field(foreign_key="datasets.id", primary_key=True)
