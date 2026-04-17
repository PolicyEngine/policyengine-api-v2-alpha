List endpoints (`/parameters`, `/parameter-values`, `/outputs/aggregates`, `/outputs/change-aggregates`) now enforce `limit <= 500` and reject non-positive values to prevent full-table scans.
