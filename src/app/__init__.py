from __future__ import annotations

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

    # Optional: print filenames if something is missing
    if len(pharmacy_files) == 0:
        print("WARNING: no pharmacy CSV files found.")
    if len(claim_files) == 0:
        print("WARNING: no claims JSON files found.")
    if len(revert_files) == 0:
        print("WARNING: no reverts JSON files found.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
