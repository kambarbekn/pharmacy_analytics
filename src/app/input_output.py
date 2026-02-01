from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoadStats:
    total_rows: int
    valid_rows: int
    skipped_rows: int


def find_single_csv(files: list[Path]) -> Path:
    csv_files = [f for f in files if f.suffix.lower() == ".csv"]
    if len(csv_files) == 0:
        raise FileNotFoundError("No pharmacy CSV file found.")
    if len(csv_files) > 1:
        raise ValueError(f"Expected 1 pharmacy CSV file, found {len(csv_files)}: {csv_files}")
    return csv_files[0]


def load_pharmacies(csv_path: Path) -> tuple[dict[str, str], LoadStats]:
    """
    Loads pharmacy reference data from a CSV.
    Accepts either:
      - columns: id, chain
      - columns: npi, chain
      - columns: chain, npi  (your screenshot looked like this)
    Returns:
      - mapping: npi -> chain
      - stats: total/valid/skipped rows
    """
    mapping: dict[str, str] = {}

    total = valid = skipped = 0

    with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {csv_path}")

        # Normalize header names to lowercase for flexible matching
        fieldnames = [h.strip().lower() for h in reader.fieldnames]

        def get_value(row: dict[str, str], *keys: str) -> str | None:
            for k in keys:
                # try exact key and lowercase key
                if k in row and row[k] is not None:
                    return str(row[k]).strip()
                lk = k.lower()
                for actual_key in row.keys():
                    if actual_key.strip().lower() == lk:
                        v = row[actual_key]
                        return None if v is None else str(v).strip()
            return None

        for row in reader:
            total += 1

            # Support common variants
            npi = get_value(row, "npi", "id")
            chain = get_value(row, "chain")

            # If CSV is chain,npi (like your screenshot), npi might be under a different header
            # but DictReader already uses the header names; this mainly covers id vs npi.

            if not npi or not chain:
                skipped += 1
                continue

            mapping[npi] = chain
            valid += 1

    return mapping, LoadStats(total_rows=total, valid_rows=valid, skipped_rows=skipped)

@dataclass(frozen=True)
class Claim:
    claim_id: str
    npi: str
    ndc: str
    price: float
    quantity: float
    timestamp: str


def _to_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def load_claims(
    json_files: list[Path],
    pharmacy_by_npi: dict[str, str],
) -> tuple[dict[str, Claim], LoadStats, dict[str, int]]:
    """
    Loads claim events from JSON files and filters to in-scope pharmacies.

    Returns:
      - claims_by_id: claim_id -> Claim (last occurrence wins)
      - stats: total/valid/skipped rows (total = total parsed events)
      - extra counters: dict with keys:
          - skipped_invalid_schema
          - skipped_unknown_npi
          - overwritten_duplicates
    """
    claims_by_id: dict[str, Claim] = {}

    total = valid = skipped = 0
    skipped_invalid_schema = 0
    skipped_unknown_npi = 0
    overwritten_duplicates = 0

    def process_event(evt: dict) -> None:
        nonlocal total, valid, skipped
        nonlocal skipped_invalid_schema, skipped_unknown_npi, overwritten_duplicates

        total += 1

        claim_id = evt.get("id")
        npi = evt.get("npi")
        ndc = evt.get("ndc")
        price = _to_float(evt.get("price"))
        quantity = _to_float(evt.get("quantity"))
        ts = evt.get("timestamp")

        # basic schema validation
        if not isinstance(claim_id, str) or not claim_id.strip():
            skipped += 1
            skipped_invalid_schema += 1
            return
        if not isinstance(npi, str) or not npi.strip():
            skipped += 1
            skipped_invalid_schema += 1
            return
        if not isinstance(ndc, str) or not ndc.strip():
            skipped += 1
            skipped_invalid_schema += 1
            return
        if price is None or quantity is None or quantity <= 0:
            skipped += 1
            skipped_invalid_schema += 1
            return
        if not isinstance(ts, str) or not ts.strip():
            skipped += 1
            skipped_invalid_schema += 1
            return

        # scope filter: only pharmacies in reference map
        if npi not in pharmacy_by_npi:
            skipped += 1
            skipped_unknown_npi += 1
            return

        # keep last occurrence if duplicates appear
        if claim_id in claims_by_id:
            overwritten_duplicates += 1

        claims_by_id[claim_id] = Claim(
            claim_id=claim_id.strip(),
            npi=npi.strip(),
            ndc=ndc.strip(),
            price=float(price),
            quantity=float(quantity),
            timestamp=ts.strip(),
        )
        valid += 1

    for path in json_files:
        # supports either:
        # - JSON array of objects: [ {...}, {...} ]
        # - single JSON object: { ... }
        with path.open("r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                # whole file invalid JSON
                # count as 1 skipped "row" for visibility
                total += 1
                skipped += 1
                skipped_invalid_schema += 1
                continue

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    process_event(item)
                else:
                    total += 1
                    skipped += 1
                    skipped_invalid_schema += 1
        elif isinstance(data, dict):
            process_event(data)
        else:
            total += 1
            skipped += 1
            skipped_invalid_schema += 1

    stats = LoadStats(total_rows=total, valid_rows=valid, skipped_rows=skipped)
    extra = {
        "skipped_invalid_schema": skipped_invalid_schema,
        "skipped_unknown_npi": skipped_unknown_npi,
        "overwritten_duplicates": overwritten_duplicates,
    }
    return claims_by_id, stats, extra

@dataclass(frozen=True)
class Revert:
    revert_id: str
    claim_id: str
    timestamp: str

def load_reverts(
    json_files: list[Path],
    claims_by_id: dict[str, Claim],
) -> tuple[list[Revert], LoadStats, dict[str, int]]:
    """
    Loads revert events from JSON files and keeps only those that reference known claim IDs.

    Returns:
      - reverts: list of in-scope Revert events
      - stats: total/valid/skipped rows (total = total parsed events)
      - extra counters:
          - skipped_invalid_schema
          - skipped_unknown_claim
    """

    reverts: list[Revert] = []
    total = valid = skipped = 0
    skipped_invalid_schema = 0
    skipped_unknown_claim = 0

    def process_event(evt: dict) -> None:
        nonlocal total, valid, skipped, skipped_invalid_schema, skipped_unknown_claim

        total += 1

        revert_id = evt.get("id")
        claim_id = evt.get("claim_id")
        ts = evt.get("timestamp")

        if not isinstance(revert_id, str) or not revert_id.strip():
            skipped += 1
            skipped_invalid_schema += 1
            return
        if not isinstance(claim_id, str) or not claim_id.strip():
            skipped += 1
            skipped_invalid_schema += 1
            return
        if not isinstance(ts, str) or not ts.strip():
            skipped += 1
            skipped_invalid_schema += 1
            return

        if claim_id not in claims_by_id:
            skipped += 1
            skipped_unknown_claim += 1
            return

        reverts.append(Revert(revert_id=revert_id.strip(), claim_id=claim_id.strip(), timestamp=ts.strip()))
        valid += 1

    for path in json_files:
        with path.open("r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                total += 1
                skipped += 1
                skipped_invalid_schema += 1
                continue

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    process_event(item)
                else:
                    total += 1
                    skipped += 1
                    skipped_invalid_schema += 1
        elif isinstance(data, dict):
            process_event(data)
        else:
            total += 1
            skipped += 1
            skipped_invalid_schema += 1

    stats = LoadStats(total_rows=total, valid_rows=valid, skipped_rows=skipped)
    extra = {
        "skipped_invalid_schema": skipped_invalid_schema,
        "skipped_unknown_claim": skipped_unknown_claim,
    }
    return reverts, stats, extra
