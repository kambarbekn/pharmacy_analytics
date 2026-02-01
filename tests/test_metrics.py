from app.input_output import Claim, Revert
from app.metrics import (
    compute_metrics_by_npi_ndc,
    compute_top_chains_per_drug,
    compute_most_common_quantity_per_drug,
)


def test_metrics_excludes_reverted_claims_from_pricing():
    # Two claims for same (npi, ndc), one reverted.
    claims_by_id = {
        "c1": Claim(claim_id="c1", npi="n1", ndc="d1", price=100.0, quantity=10.0, timestamp="t1"),
        "c2": Claim(claim_id="c2", npi="n1", ndc="d1", price=50.0, quantity=5.0, timestamp="t2"),
    }
    reverts = [Revert(revert_id="r1", claim_id="c2", timestamp="rt")]

    rows = compute_metrics_by_npi_ndc(claims_by_id, reverts)

    # Find our row
    row = next(r for r in rows if r.npi == "n1" and r.ndc == "d1")

    # fills counts all claims
    assert row.fills == 2
    # reverted counts revert events
    assert row.reverted == 1

    # Pricing excludes reverted claim c2:
    # unit price for c1: 100/10 = 10.0
    assert row.total_price == 100.0
    assert row.avg_price == 10.0


def test_top2_chains_per_drug_returns_cheapest_two():
    # Same drug, different chains via pharmacy_by_npi
    pharmacy_by_npi = {"n1": "health", "n2": "saint", "n3": "doctor"}

    claims_by_id = {
        "c1": Claim(claim_id="c1", npi="n1", ndc="d1", price=10.0, quantity=1.0, timestamp="t1"),  # unit 10
        "c2": Claim(claim_id="c2", npi="n2", ndc="d1", price=20.0, quantity=1.0, timestamp="t2"),  # unit 20
        "c3": Claim(claim_id="c3", npi="n3", ndc="d1", price=30.0, quantity=1.0, timestamp="t3"),  # unit 30
    }
    reverts = []

    out = compute_top_chains_per_drug(
        claims_by_id=claims_by_id,
        reverts=reverts,
        pharmacy_by_npi=pharmacy_by_npi,
        top_n=2,
    )

    # One ndc record
    assert len(out) == 1
    assert out[0]["ndc"] == "d1"

    chains = out[0]["chain"]
    assert len(chains) == 2

    # Cheapest two: health (10), saint (20)
    assert chains[0]["name"] == "health"
    assert chains[0]["avg_price"] == 10.0
    assert chains[1]["name"] == "saint"
    assert chains[1]["avg_price"] == 20.0


def test_most_common_quantity_per_drug_returns_ties_sorted():
    claims_by_id = {
        "c1": Claim(claim_id="c1", npi="n1", ndc="d1", price=10.0, quantity=5.0, timestamp="t1"),
        "c2": Claim(claim_id="c2", npi="n1", ndc="d1", price=10.0, quantity=5.0, timestamp="t2"),
        "c3": Claim(claim_id="c3", npi="n1", ndc="d1", price=10.0, quantity=10.0, timestamp="t3"),
        "c4": Claim(claim_id="c4", npi="n1", ndc="d1", price=10.0, quantity=10.0, timestamp="t4"),
        "c5": Claim(claim_id="c5", npi="n1", ndc="d1", price=10.0, quantity=2.0, timestamp="t5"),
    }

    out = compute_most_common_quantity_per_drug(claims_by_id)

    assert len(out) == 1
    assert out[0]["ndc"] == "d1"

    # quantities 5 and 10 both appear twice -> tie, sorted ascending
    assert out[0]["most_prescribed_quantity"] == [5.0, 10.0]
