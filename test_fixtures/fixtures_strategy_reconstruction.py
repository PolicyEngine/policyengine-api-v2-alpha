"""Fixtures and constants for strategy reconstruction tests."""

# -----------------------------------------------------------------------------
# Filter Strategy Constants
# -----------------------------------------------------------------------------

FILTER_STRATEGIES = {
    "ROW_FILTER": "row_filter",
    "WEIGHT_REPLACEMENT": "weight_replacement",
}

# -----------------------------------------------------------------------------
# Region Type Constants
# -----------------------------------------------------------------------------

REGION_TYPES = {
    "CONSTITUENCY": "constituency",
    "LOCAL_AUTHORITY": "local_authority",
    "COUNTRY": "country",
    "STATE": "state",
    "NATIONAL": "national",
}

# -----------------------------------------------------------------------------
# Filter Field / Value Constants
# -----------------------------------------------------------------------------

FILTER_FIELDS = {
    "COUNTRY": "country",
    "STATE_CODE": "state_code",
    "PLACE_FIPS": "place_fips",
}

FILTER_VALUES = {
    "ENGLAND": "ENGLAND",
    "SCOTLAND": "SCOTLAND",
    "CALIFORNIA": "CA",
    "SHEFFIELD_CENTRAL": "E14001551",
    "MANCHESTER": "E09000003",
}

# -----------------------------------------------------------------------------
# GCS Config Constants (expected in WEIGHT_MATRIX_CONFIG)
# -----------------------------------------------------------------------------

EXPECTED_CONSTITUENCY_CONFIG = {
    "weight_matrix_bucket": "policyengine-uk-data-private",
    "weight_matrix_key": "parliamentary_constituency_weights.h5",
    "lookup_csv_bucket": "policyengine-uk-data-private",
    "lookup_csv_key": "constituencies_2024.csv",
}

EXPECTED_LOCAL_AUTHORITY_CONFIG = {
    "weight_matrix_bucket": "policyengine-uk-data-private",
    "weight_matrix_key": "local_authority_weights.h5",
    "lookup_csv_bucket": "policyengine-uk-data-private",
    "lookup_csv_key": "local_authorities_2021.csv",
}
