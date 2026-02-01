from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.input_output import Claim, Revert


@dataclass
class MetricRow:
    npi: str
    ndc: str
    fills: int
    reverted: int
    avg_price: float
    total_price: float


def compute_metrics_by_npi_ndc(
    claims_by_id: dict[str, Claim],
    reverts: list[Revert],
) -> list[MetricRow]:
    # Count reverts by claim_id (events, not unique claims)
    reverts_by_claim_id: dict[str, int] = {}
    for r in reverts:
        reverts_by_claim_id[r.claim_id] = reverts_by_claim_id.get(r.claim_id, 0) + 1

    # A claim is reverted if it appears in the revert list at least once
    reverted_claim_ids = set(reverts_by_claim_id.keys())

    # Aggregations per (npi, ndc)
    fills: dict[tuple[str, str], int] = {}
    reverted: dict[tuple[str, str], int] = {}
    total_price: dict[tuple[str, str], float] = {}
    unit_price_sum: dict[tuple[str, str], float] = {}
    unit_price_cnt: dict[tuple[str, str], int] = {}

    # First pass: claims
    for claim_id, c in claims_by_id.items():
        key = (c.npi, c.ndc)

        fills[key] = fills.get(key, 0) + 1

        is_reverted = claim_id in reverted_claim_ids
        if not is_reverted:
            total_price[key] = total_price.get(key, 0.0) + c.price
            unit = c.price / c.quantity
            unit_price_sum[key] = unit_price_sum.get(key, 0.0) + unit
            unit_price_cnt[key] = unit_price_cnt.get(key, 0) + 1

    # Second pass: reverts -> attribute to (npi, ndc) using claim_id join
    for r in reverts:
        c = claims_by_id.get(r.claim_id)
        if c is None:
            continue
        key = (c.npi, c.ndc)
        reverted[key] = reverted.get(key, 0) + 1

    # Build rows
    keys = set(fills.keys()) | set(reverted.keys()) | set(total_price.keys()) | set(unit_price_cnt.keys())

    rows: list[MetricRow] = []
    for npi, ndc in sorted(keys):
        cnt = unit_price_cnt.get((npi, ndc), 0)
        avg = (unit_price_sum.get((npi, ndc), 0.0) / cnt) if cnt > 0 else 0.0

        rows.append(
            MetricRow(
                npi=npi,
                ndc=ndc,
                fills=fills.get((npi, ndc), 0),
                reverted=reverted.get((npi, ndc), 0),
                avg_price=round(avg, 2),
                total_price=round(total_price.get((npi, ndc), 0.0), 2),
            )
        )

    return rows


def metric_rows_to_jsonable(rows: Iterable[MetricRow]) -> list[dict]:
    return [
        {
            "npi": r.npi,
            "ndc": r.ndc,
            "fills": r.fills,
            "reverted": r.reverted,
            "avg_price": r.avg_price,
            "total_price": r.total_price,
        }
        for r in rows
    ]

def compute_top_chains_per_drug(
    claims_by_id: dict[str, Claim],
    reverts: list[Revert],
    pharmacy_by_npi: dict[str, str],
    top_n: int = 2,
) -> list[dict]:
    # claims that were reverted at least once
    reverted_claim_ids = {r.claim_id for r in reverts}

    # (ndc, chain) -> sum(unit_price), count
    unit_sum: dict[tuple[str, str], float] = {}
    unit_cnt: dict[tuple[str, str], int] = {}

    for claim_id, c in claims_by_id.items():
        if claim_id in reverted_claim_ids:
            continue

        chain = pharmacy_by_npi.get(c.npi)
        if chain is None:
            continue

        key = (c.ndc, chain)
        unit = c.price / c.quantity

        unit_sum[key] = unit_sum.get(key, 0.0) + unit
        unit_cnt[key] = unit_cnt.get(key, 0) + 1

    # ndc -> list of (chain, avg_price)
    by_ndc: dict[str, list[tuple[str, float]]] = {}

    for (ndc, chain), total in unit_sum.items():
        cnt = unit_cnt[(ndc, chain)]
        avg = total / cnt
        by_ndc.setdefault(ndc, []).append((chain, round(avg, 2)))

    # build final output
    result: list[dict] = []
    for ndc, chain_prices in sorted(by_ndc.items()):
        cheapest = sorted(chain_prices, key=lambda x: x[1])[:top_n]
        result.append(
            {
                "ndc": ndc,
                "chain": [
                    {"name": chain, "avg_price": price}
                    for chain, price in cheapest
                ],
            }
        )

    return result

def compute_most_common_quantity_per_drug(
    claims_by_id: dict[str, Claim],
) -> list[dict]:
    # ndc -> quantity -> count
    freq: dict[str, dict[float, int]] = {}

    for c in claims_by_id.values():
        freq.setdefault(c.ndc, {})
        freq[c.ndc][c.quantity] = freq[c.ndc].get(c.quantity, 0) + 1

    result: list[dict] = []

    for ndc, qty_counts in sorted(freq.items()):
        max_count = max(qty_counts.values())
        most_common = sorted(
            [qty for qty, cnt in qty_counts.items() if cnt == max_count]
        )

        result.append(
            {
                "ndc": ndc,
                "most_prescribed_quantity": most_common,
            }
        )

    return result
