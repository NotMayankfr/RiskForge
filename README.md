# Defense Sector Credit Analytics Tool

An advanced Python-based corporate credit risk analysis pipeline tailored for the defense sector.

## Overview
This tool automates the process of pulling financial statements, computing rigorous credit metrics, stress testing, assessing debt capacity, and drafting one-page credit memos using the Gemini API.

## Workflow
1. **Data Ingestion:** Fetches historical financial statements via `yfinance` for defense companies (e.g., LMT, RTX).
2. **Ratio Engine:** Calculates leverage, coverage, liquidity, and Altman Z-Scores.
3. **Early Warning System:** Flags critical credit risks (e.g., negative EBITDA, breaching thresholds).
4. **Advanced Analytics:**
   - **Debt Capacity:** Computes illustrative maximum sustainable leverage, headroom, and FCF paydown constraints.
   - **Stress Testing:** Runs Base, Moderate, and Severe downside scenarios adjusting margins and revenue.
   - **Refinancing Risk:** Analyzes leverage, debt-to-FCF, and cash coverage to classify refinancing risk.
   - **Covenant Monitoring:** Tests ratios against illustrative configurable covenant thresholds.
   - **Cash Flow Projections:** Models 3-year forward FCF based on margin assumptions.
   - **Sector Overlay:** Adds qualitative defense sector context (e.g., revenue visibility, contract cyclicality).
5. **AI Credit Memo:** Ingests all quantitative outputs to generate a professional, zero-hallucination structured credit memo using `models/gemini-3.8-flash` (with built-in fallback to `gemini-3.1-flash-lite`).
6. **Dashboard:** Renders a self-contained HTML dashboard (`output/defense_credit_dashboard.html`) featuring interactive tabs, Chart.js visualizations, and comprehensive portfolio summaries.

## Data Limitations
All data is sourced from publicly available annual reports via `yfinance`.
- Debt maturities and actual legal covenant terms are not provided by `yfinance`.
- Forward projections and stress tests are **illustrative model outputs**, not verified forecasts.
- This tool is for educational/analytical purposes and does not reflect actual underwriting criteria.

## Requirements
- Python 3.10+
- `yfinance`
- `pandas`
- `google-genai`

## Usage
Set your Gemini API key and run the pipeline:
```powershell
$env:GEMINI_API_KEY = "your-api-key"
python main.py
```
Open `output/defense_credit_dashboard.html` to view the full interactive report.

## Testing
Run the deterministic unit test suite:
```powershell
python -m unittest tests/test_modules.py
```
