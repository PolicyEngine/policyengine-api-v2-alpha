"""Download, convert, and upload state & congressional district datasets.

One-off script to migrate state/district datasets from GCS (old format)
to Supabase (new yearly entity-level format).

Downloads raw h5 files from GCS, converts them to yearly entity-level files
using policyengine's create_datasets(), uploads to Supabase, and creates
database records.

Usage:
    python import_state_datasets.py AL              # State + all AL districts
    python import_state_datasets.py CA NY TX        # Multiple states + districts
    python import_state_datasets.py --all           # All 51 states + 436 districts
    python import_state_datasets.py AL --state-only # State only, no districts
    python import_state_datasets.py --years 2025,2026
    python import_state_datasets.py --skip-upload   # Convert only

Must be run from the policyengine-api-v2-alpha project root (where .env lives).
"""

import argparse
import json
import logging
import subprocess
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.ERROR)
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

# Add src to path for policyengine_api imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from policyengine.countries.us.data import DISTRICT_COUNTS  # noqa: E402
from rich.console import Console  # noqa: E402
from sqlmodel import Session, create_engine, select  # noqa: E402

from policyengine_api.config.settings import settings  # noqa: E402
from policyengine_api.models import Dataset, TaxBenefitModel  # noqa: E402
from policyengine_api.services.storage import upload_dataset_for_seeding  # noqa: E402

console = Console()

GCS_BUCKET = "gs://policyengine-us-data"
TMP_DIR = Path("/tmp/pe_state_data")
DEFAULT_YEARS = list(range(2024, 2036))

ALL_STATES = list(DISTRICT_COUNTS.keys())


def fmt_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs:.0f}s"
    hours = int(minutes // 60)
    mins = minutes % 60
    return f"{hours}h {mins}m {secs:.0f}s"


def get_session() -> Session:
    engine = create_engine(settings.database_url, echo=False)
    return Session(engine)


def download_from_gcs(gcs_path: str, local_path: Path) -> bool:
    """Download a file from GCS using gsutil. Skips if already exists locally."""
    if local_path.exists() and local_path.stat().st_size > 0:
        return True
    local_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["gsutil", "cp", gcs_path, str(local_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print(f"  [red]gsutil error: {result.stderr.strip()}[/red]")
        return False
    return True


def convert_dataset(raw_h5_path: str, output_folder: str, years: list[int]) -> dict:
    """Convert a raw h5 file to yearly entity-level h5 files.

    Skips conversion if all yearly output files already exist.
    Returns dict mapping dataset_key -> PolicyEngineUSDataset.
    """
    from policyengine.tax_benefit_models.us.datasets import (
        create_datasets,
        load_datasets,
    )

    stem = Path(raw_h5_path).stem
    all_exist = all(
        Path(f"{output_folder}/{stem}_year_{year}.h5").exists() for year in years
    )
    if all_exist:
        return load_datasets(
            datasets=[raw_h5_path],
            years=years,
            data_folder=output_folder,
        )

    return create_datasets(
        datasets=[raw_h5_path],
        years=years,
        data_folder=output_folder,
    )


def process_file(
    file_info: dict,
    years: list[int],
    data_folder: Path,
    skip_upload: bool,
    session,
    us_model,
    file_index: int,
    total_files: int,
) -> tuple[int, int, int, dict]:
    """Process a single raw h5 file (state or district).

    Returns (datasets_created, datasets_skipped, errors, timing).
    Region-to-dataset wiring is handled by seed_regions.py, not here.
    """
    code = file_info["code"]
    prefix = f"  [{file_index}/{total_files}] {code}"
    datasets_created = 0
    datasets_skipped = 0
    errors = 0
    timing = {"code": code, "type": file_info["type"]}

    # Step 1: Download
    t0 = time.time()
    console.print(f"{prefix}: downloading from GCS...")
    if not download_from_gcs(file_info["gcs_path"], file_info["local_path"]):
        console.print(f"{prefix}: [red]download failed, skipping[/red]")
        timing["status"] = "download_failed"
        return 0, 0, 1, timing
    dl_time = time.time() - t0
    size_mb = file_info["local_path"].stat().st_size / (1024 * 1024)
    timing["download_seconds"] = round(dl_time, 2)
    timing["raw_size_mb"] = round(size_mb, 1)
    console.print(f"{prefix}: downloaded ({size_mb:.1f} MB, {fmt_duration(dl_time)})")

    # Step 2: Convert
    t0 = time.time()
    console.print(f"{prefix}: converting to {len(years)} yearly datasets...")
    output_folder = str(data_folder / file_info["output_subfolder"])
    try:
        converted = convert_dataset(str(file_info["local_path"]), output_folder, years)
    except Exception as e:
        console.print(f"{prefix}: [red]conversion failed: {e}[/red]")
        timing["status"] = "conversion_failed"
        timing["error"] = str(e)
        return 0, 0, 1, timing
    conv_time = time.time() - t0
    timing["conversion_seconds"] = round(conv_time, 2)
    timing["datasets_converted"] = len(converted)
    console.print(
        f"{prefix}: converted {len(converted)} datasets ({fmt_duration(conv_time)})"
    )

    # Step 3: Upload + create DB records
    if skip_upload:
        datasets_skipped += len(converted)
        timing["upload_seconds"] = 0
        timing["status"] = "upload_skipped"
        console.print(f"{prefix}: [yellow]upload skipped[/yellow]")
    else:
        t0 = time.time()
        console.print(f"{prefix}: uploading to Supabase...")
        for _, pe_dataset in converted.items():
            existing = session.exec(
                select(Dataset).where(Dataset.name == pe_dataset.name)
            ).first()

            if existing:
                datasets_skipped += 1
                continue

            object_name = f"{file_info['supabase_prefix']}/{pe_dataset.name}.h5"

            try:
                upload_dataset_for_seeding(pe_dataset.filepath, object_name=object_name)
            except Exception as e:
                console.print(
                    f"{prefix}: [red]upload failed for {pe_dataset.name}: {e}[/red]"
                )
                errors += 1
                continue

            db_dataset = Dataset(
                name=pe_dataset.name,
                description=pe_dataset.description,
                filepath=object_name,
                year=pe_dataset.year,
                tax_benefit_model_id=us_model.id,
            )
            session.add(db_dataset)
            session.commit()
            session.refresh(db_dataset)
            datasets_created += 1

        upload_time = time.time() - t0
        timing["upload_seconds"] = round(upload_time, 2)
        console.print(
            f"{prefix}: uploaded {datasets_created} datasets, "
            f"{datasets_skipped} already existed ({fmt_duration(upload_time)})"
        )

    timing["datasets_created"] = datasets_created
    timing["datasets_skipped"] = datasets_skipped
    timing["errors"] = errors
    timing["status"] = timing.get("status", "ok")

    return datasets_created, datasets_skipped, errors, timing


def process_state(
    state_code: str,
    years: list[int],
    data_folder: Path,
    skip_upload: bool,
    state_only: bool,
    session,
    us_model,
) -> tuple[int, int, int, list[dict]]:
    """Process one state: its state-level file and all district files.

    Returns (created, skipped, errors, file_timings).
    Region-to-dataset wiring is handled by seed_regions.py, not here.
    """
    district_count = DISTRICT_COUNTS.get(state_code, 0)

    files_to_process = []

    # State file
    files_to_process.append(
        {
            "type": "state",
            "code": state_code,
            "gcs_path": f"{GCS_BUCKET}/states/{state_code}.h5",
            "local_path": TMP_DIR / "states" / f"{state_code}.h5",
            "output_subfolder": "states",
            "supabase_prefix": f"states/{state_code}",
        }
    )

    # District files
    if not state_only:
        for i in range(1, district_count + 1):
            district_code = f"{state_code}-{i:02d}"
            files_to_process.append(
                {
                    "type": "district",
                    "code": district_code,
                    "gcs_path": f"{GCS_BUCKET}/districts/{district_code}.h5",
                    "local_path": TMP_DIR / "districts" / f"{district_code}.h5",
                    "output_subfolder": "districts",
                    "supabase_prefix": f"districts/{district_code}",
                }
            )

    total_files = len(files_to_process)
    total_created = 0
    total_skipped = 0
    total_errors = 0
    file_timings = []

    for i, file_info in enumerate(files_to_process, 1):
        created, skipped, errs, timing = process_file(
            file_info=file_info,
            years=years,
            data_folder=data_folder,
            skip_upload=skip_upload,
            session=session,
            us_model=us_model,
            file_index=i,
            total_files=total_files,
        )
        total_created += created
        total_skipped += skipped
        total_errors += errs
        file_timings.append(timing)

    return total_created, total_skipped, total_errors, file_timings


def main():
    parser = argparse.ArgumentParser(
        description="Import state & district datasets from GCS to Supabase"
    )
    parser.add_argument(
        "states",
        nargs="*",
        help="State codes (e.g., CA NY TX). Uppercase 2-letter codes.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_states",
        help="Process all 51 states + DC",
    )
    parser.add_argument(
        "--state-only",
        action="store_true",
        help="Skip district processing, only do state-level datasets",
    )
    parser.add_argument(
        "--years",
        type=str,
        default=None,
        help="Comma-separated years (default: 2024,2025,2026,2027,2028)",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Convert locally without uploading to Supabase or creating DB records",
    )
    parser.add_argument(
        "--data-folder",
        type=str,
        default=None,
        help="Local directory for converted files (default: ./data)",
    )
    args = parser.parse_args()

    # Determine which states to process
    if args.all_states:
        states = ALL_STATES
    elif args.states:
        states = [s.upper() for s in args.states]
    else:
        parser.error("Provide state codes or use --all")
        return

    # Validate state codes
    invalid = [s for s in states if s not in DISTRICT_COUNTS]
    if invalid:
        console.print(f"[red]Invalid state codes: {', '.join(invalid)}[/red]")
        sys.exit(1)

    years = DEFAULT_YEARS
    if args.years:
        years = [int(y.strip()) for y in args.years.split(",")]

    data_folder = (
        Path(args.data_folder) if args.data_folder else Path(__file__).parent / "data"
    )

    total_districts = (
        sum(DISTRICT_COUNTS[s] for s in states) if not args.state_only else 0
    )
    total_files = len(states) + total_districts
    total_yearly = total_files * len(years)

    console.print()
    console.print("[bold green]State & District Dataset Import[/bold green]")
    console.print(f"  States: {len(states)} ({', '.join(states)})")
    if not args.state_only:
        console.print(f"  Districts: {total_districts}")
    console.print(f"  Years: {years}")
    console.print(f"  Raw files to process: {total_files}")
    console.print(f"  Yearly datasets to produce: {total_yearly}")
    if args.skip_upload:
        console.print("  [yellow]Upload skipped (--skip-upload)[/yellow]")
    console.print()

    grand_created = 0
    grand_skipped = 0
    grand_errors = 0

    session = None
    us_model = None

    if not args.skip_upload:
        session = get_session()
        us_model = session.exec(
            select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-us")
        ).first()
        if not us_model:
            console.print(
                "[red]Error: US model not found. Run seed_models.py first.[/red]"
            )
            sys.exit(1)

    script_start = time.time()
    timing_report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "args": {
            "states": states,
            "years": years,
            "state_only": args.state_only,
            "skip_upload": args.skip_upload,
            "data_folder": str(data_folder),
        },
        "states": [],
    }

    for state_idx, state_code in enumerate(states, 1):
        district_count = DISTRICT_COUNTS[state_code]
        file_count = 1 + (district_count if not args.state_only else 0)
        console.print(
            f"[bold]({state_idx}/{len(states)}) Processing {state_code} "
            f"({file_count} files)[/bold]"
        )

        state_start = time.time()

        created, skipped, errs, file_timings = process_state(
            state_code=state_code,
            years=years,
            data_folder=data_folder,
            skip_upload=args.skip_upload,
            state_only=args.state_only,
            session=session,
            us_model=us_model,
        )

        state_time = time.time() - state_start
        console.print(
            f"[bold]({state_idx}/{len(states)}) {state_code} complete: "
            f"{created} created, {skipped} skipped"
            f"{f', {errs} errors' if errs else ''} "
            f"({fmt_duration(state_time)})[/bold]"
        )
        console.print()

        timing_report["states"].append(
            {
                "state": state_code,
                "total_seconds": round(state_time, 2),
                "datasets_created": created,
                "datasets_skipped": skipped,
                "errors": errs,
                "files": file_timings,
            }
        )

        # Write timing file after each state so partial results are preserved
        timing_path = data_folder / "import_timing.json"
        timing_path.parent.mkdir(parents=True, exist_ok=True)
        timing_path.write_text(json.dumps(timing_report, indent=2))

        grand_created += created
        grand_skipped += skipped
        grand_errors += errs

    if session:
        session.close()

    total_time = time.time() - script_start

    # Write final timing report
    timing_report["finished_at"] = datetime.now(timezone.utc).isoformat()
    timing_report["total_seconds"] = round(total_time, 2)
    timing_report["totals"] = {
        "datasets_created": grand_created,
        "datasets_skipped": grand_skipped,
        "errors": grand_errors,
    }
    timing_path = data_folder / "import_timing.json"
    timing_path.write_text(json.dumps(timing_report, indent=2))

    console.print(
        f"[bold green]Import complete ({fmt_duration(total_time)})[/bold green]"
    )
    console.print(f"  Datasets created: {grand_created}")
    console.print(f"  Datasets skipped (already exist): {grand_skipped}")
    if grand_errors:
        console.print(f"  [red]Errors: {grand_errors}[/red]")
    console.print(f"  Timing report: {timing_path}")


if __name__ == "__main__":
    main()
