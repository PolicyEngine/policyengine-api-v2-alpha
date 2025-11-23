"""Supabase storage service for datasets."""

from pathlib import Path

from policyengine_api.config.settings import settings
from supabase import Client, create_client


def get_supabase_client() -> Client:
    """Get Supabase client."""
    return create_client(settings.supabase_url, settings.supabase_key)


def get_service_role_client() -> Client:
    """Get Supabase client with service role key for admin operations."""
    return create_client(settings.supabase_url, settings.supabase_service_key)


def upload_dataset(file_path: str, object_name: str | None = None) -> str:
    """Upload dataset to Supabase storage.

    Args:
        file_path: Local path to dataset file
        object_name: Name to store in bucket (defaults to filename)

    Returns:
        Object name (key) in storage
    """
    supabase = get_supabase_client()

    if object_name is None:
        object_name = Path(file_path).name

    # Upload file using Supabase storage client
    with open(file_path, "rb") as f:
        supabase.storage.from_(settings.storage_bucket).upload(
            object_name,
            f,
            {"content-type": "application/octet-stream", "upsert": "true"},
        )

    return object_name


def upload_dataset_for_seeding(file_path: str, object_name: str | None = None) -> str:
    """Upload dataset using service role key (for seeding operations).

    Args:
        file_path: Local path to dataset file
        object_name: Name to store in bucket (defaults to filename)

    Returns:
        Object name (key) in storage
    """
    supabase = get_service_role_client()

    if object_name is None:
        object_name = Path(file_path).name

    # Upload file using service role client
    with open(file_path, "rb") as f:
        supabase.storage.from_(settings.storage_bucket).upload(
            object_name,
            f,
            {"content-type": "application/octet-stream", "upsert": "true"},
        )

    return object_name


def download_dataset(object_name: str, local_path: str) -> str:
    """Download dataset from Supabase storage.

    Args:
        object_name: Name in storage bucket
        local_path: Where to save locally

    Returns:
        Local file path
    """
    supabase = get_supabase_client()

    # Ensure parent directory exists
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)

    # Download file using Supabase storage client
    data = supabase.storage.from_(settings.storage_bucket).download(object_name)

    # Save locally
    with open(local_path, "wb") as f:
        f.write(data)

    return local_path


def get_dataset_url(object_name: str) -> str:
    """Get public URL for dataset.

    Args:
        object_name: Name in storage bucket

    Returns:
        Public URL
    """
    supabase = get_supabase_client()
    return supabase.storage.from_(settings.storage_bucket).get_public_url(object_name)


def list_datasets() -> list[dict]:
    """List all datasets in storage.

    Returns:
        List of file metadata
    """
    supabase = get_supabase_client()
    return supabase.storage.from_(settings.storage_bucket).list()
