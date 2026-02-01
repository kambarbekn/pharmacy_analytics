# Pharmacy Claims Analytics

## Overview
This project reads pharmacy reference data (CSV) and claim/revert event data (JSON files) and produces analytics outputs:
1) Metrics by (npi, ndc)
2) Top 2 cheapest chains per drug (ndc)
3) Most common prescribed quantities per drug (ndc)

## Input data

### Pharmacy (CSV)
Columns:
- npi (string): pharmacy identifier
- chain (string): chain name

### Claims (JSON)
Each claim event:
- id (string): claim UUID
- npi (string): pharmacy identifier
- ndc (string): drug identifier
- price (float): total price for the fill
- quantity (number): quantity filled
- timestamp (datetime): when the claim was filled

### Reverts (JSON)
Each revert event:
- id (string): revert UUID
- claim_id (string): claim UUID being reverted
- timestamp (datetime): when the claim was reverted

## Outputs

### 1) Metrics by (npi, ndc)
File: `outputs/metrics_by_npi_ndc.json`

Fields:
- npi
- ndc
- fills
- reverted
- avg_price (average unit price)
- total_price

### 2) Top 2 chains per drug (ndc)
File: `outputs/top2_chains_per_ndc.json`

Fields:
- ndc
- chain: list of 2 items (name, avg_price)

### 3) Most common quantity per drug (ndc)
File: `outputs/most_common_quantity_per_ndc.json`

Fields:
- ndc
- most_prescribed_quantity: list of quantities

## How to run

### Tests

```powershell
$env:PYTHONPATH="src"
python -m pytest -q

### Prerequisites
- Python 3.10+ (tested on Windows)
- Git

### Install dependencies
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

## Execute command

$env:PYTHONPATH="src"
python -m app.cli --pharmacy-dirs data\pharmacies --claims-dirs data\claims --reverts-dirs data\reverts --output-dir outputs
