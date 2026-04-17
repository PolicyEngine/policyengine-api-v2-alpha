`settings.database_url` now raises `ValueError` for non-local Supabase URLs that lack `supabase_db_url` instead of silently synthesising a `postgres:postgres@...` string.
