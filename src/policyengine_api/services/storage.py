"""Supabase storage service for datasets."""

import hashlib
from pathlib import Path

from policyengine_api.config.settings import settings
from supabase import Client, create_client

# Local cache directory for downloaded datasets
CACHE_DIR = Path("/tmp/policyengine_dataset_cache")


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


def get_cached_dataset_path(object_name: str) -> Path:
    """Get the local cache path for a dataset.

    Args:
        object_name: Name in storage bucket

    Returns:
        Path to cached file
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / object_name


def download_dataset(object_name: str, local_path: str | None = None) -> str:
    """Download dataset from Supabase storage with local caching.

    Args:
        object_name: Name in storage bucket
        local_path: Where to save locally (optional, uses cache if not provided)

    Returns:
        Local file path
    """
    # Check cache first
    cache_path = get_cached_dataset_path(object_name)

    if cache_path.exists():
        # If specific local_path requested, copy from cache
        if local_path and local_path != str(cache_path):
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy(cache_path, local_path)
            return local_path
        return str(cache_path)

    # Download from Supabase
    supabase = get_supabase_client()
    data = supabase.storage.from_(settings.storage_bucket).download(object_name)

    # Save to cache
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        f.write(data)

    # If specific local_path requested, copy from cache
    if local_path and local_path != str(cache_path):
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(cache_path, local_path)
        return local_path

    return str(cache_path)


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
