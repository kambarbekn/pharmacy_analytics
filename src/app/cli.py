from __future__ import annotations
from app.input_output import find_single_csv, load_pharmacies, load_claims, load_reverts
from app.metrics import compute_metrics_by_npi_ndc, metric_rows_to_jsonable, compute_top_chains_per_drug, compute_most_common_quantity_per_drug


import json
import argparse
from pathlib import Path
import sys


def _existing_dirs(paths: list[str]) -> list[Path]:
    dirs: list[Path] = []
    for p in paths:
        d = Path(p)
        if not d.exists() or not d.is_dir():
            raise FileNotFoundError(f"Directory not found: {d}")
        dirs.append(d)
    return dirs


def _find_files(dirs: list[Path], patterns: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for d in dirs:
        for pat in patterns:
            files.extend(sorted(d.glob(pat)))
    # keep only files (glob can return dirs in some cases)
    return [f for f in files if f.is_file()]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pharmacy-claims-analytics",
        description="Dry-run CLI: discovers input files and prepares output directory.",
    )

    parser.add_argument(
        "--pharmacy-dirs",
        nargs="+",
        required=True,
        help="One or more directories containing pharmacy CSV files.",
    )
    parser.add_argument(
        "--claims-dirs",
        nargs="+",
        required=True,
        help="One or more directories containing claims JSON files.",
    )
    parser.add_argument(
        "--reverts-dirs",
        nargs="+",
        required=True,
        help="One or more directories containing reverts JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where output JSON files will be written.",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    pharmacy_dirs = _existing_dirs(args.pharmacy_dirs)
    claims_dirs = _existing_dirs(args.claims_dirs)
    reverts_dirs = _existing_dirs(args.reverts_dirs)

    pharmacy_files = _find_files(pharmacy_dirs, ("*.csv",))
    claim_files = _find_files(claims_dirs, ("*.json",))
    revert_files = _find_files(reverts_dirs, ("*.json",))

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== Input discovery (dry run) ===")
    print(f"Pharmacy dirs : {[str(d) for d in pharmacy_dirs]}")
    print(f"Claims dirs   : {[str(d) for d in claims_dirs]}")
    print(f"Reverts dirs  : {[str(d) for d in reverts_dirs]}")
    print("")
    print(f"Pharmacy files found: {len(pharmacy_files)}")
    print(f"Claims files found  : {len(claim_files)}")
    print(f"Reverts files found : {len(revert_files)}")
    print("")
    print(f"Output dir: {out_dir.resolve()}")

    # Load pharmacy reference data
    csv_path = find_single_csv(pharmacy_files)
    pharmacy_map, stats = load_pharmacies(csv_path)

    print("")
    print(f"Loaded pharmacies: {len(pharmacy_map)} (rows: {stats.total_rows}, skipped: {stats.skipped_rows})")

    # Load claims
    claims_by_id, claims_stats, claims_extra = load_claims(claim_files, pharmacy_map)

    print(f"Loaded claims: {len(claims_by_id)} "
        f"(events: {claims_stats.total_rows}, skipped: {claims_stats.skipped_rows})")
    print(f"  - skipped_invalid_schema: {claims_extra['skipped_invalid_schema']}")
    print(f"  - skipped_unknown_npi    : {claims_extra['skipped_unknown_npi']}")
    print(f"  - overwritten_duplicates : {claims_extra['overwritten_duplicates']}")

    # Load reverts
    reverts, reverts_stats, reverts_extra = load_reverts(revert_files, claims_by_id)

    reverted_claim_ids = {r.claim_id for r in reverts}

    print(f"Loaded reverts: {len(reverts)} "
        f"(events: {reverts_stats.total_rows}, skipped: {reverts_stats.skipped_rows})")
    print(f"  - unique reverted claims : {len(reverted_claim_ids)}")
    print(f"  - skipped_invalid_schema : {reverts_extra['skipped_invalid_schema']}")
    print(f"  - skipped_unknown_claim  : {reverts_extra['skipped_unknown_claim']}")

    # Metrics by (npi, ndc)
    metrics_rows = compute_metrics_by_npi_ndc(claims_by_id, reverts)
    metrics_out = metric_rows_to_jsonable(metrics_rows)

    metrics_path = out_dir / "metrics_by_npi_ndc.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(metrics_out, f, indent=4)

    print("")
    print(f"Wrote metrics: {metrics_path}")

    # Top 2 cheapest chains per drug
    top_chains = compute_top_chains_per_drug(
        claims_by_id=claims_by_id,
        reverts=reverts,
        pharmacy_by_npi=pharmacy_map,
        top_n=2,
    )

    top_chains_path = out_dir / "top_chains_per_drug.json"
    with top_chains_path.open("w", encoding="utf-8") as f:
        json.dump(top_chains, f, indent=4)

    print(f"Wrote top chains per drug: {top_chains_path}")

    # Most common quantity per drug
    common_quantities = compute_most_common_quantity_per_drug(claims_by_id)

    common_qty_path = out_dir / "most_common_quantity_per_drug.json"
    with common_qty_path.open("w", encoding="utf-8") as f:
        json.dump(common_quantities, f, indent=4)

    print(f"Wrote most common quantity per drug: {common_qty_path}")



    return 0


if __name__ == "__main__":
    raise SystemExit(main())
