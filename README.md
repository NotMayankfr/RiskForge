# RiskForge Financial Intelligence

### Corporate Credit Risk Analytics, Historical SQL Data Store & AI Decision Support Platform

[![Live App](https://img.shields.io/badge/Live%20Demo-Streamlit%20Cloud-FF4B4B?logo=streamlit&logoColor=white)](https://riskforgeai.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Database](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![AI Engine](https://img.shields.io/badge/AI-Google%20Gemini%20API-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)

**RiskForge** is an institutional-grade corporate credit analytics and financial intelligence platform. It converts public financial filings into structured assessments of capital structure, liquidity, debt service capacity, refinancing risk, downside stress resilience, and multi-period risk deterioration.

The platform bridges **deterministic quantitative finance**, **embedded SQL historical analytics**, and **grounded generative AI** to automate credit research workflows from statement ingestion to committee-ready credit memorandums.

> **Live Application:** [riskforgeai.streamlit.app](https://riskforgeai.streamlit.app/)  
> **Architecture Principle:** Deterministic financial calculations and database-driven analytics remain strictly separate from the generative layer. Numerical facts are computed in code and stored in SQL; the LLM is restricted to evidence-grounded synthesis and memo generation.

---

## What RiskForge Does

A standard institutional credit underwriting workflow requires collecting multi-year filings, normalizing inconsistent financial statement line items, calculating coverage and leverage metrics, checking credit covenants, stress-testing downside cash flows, evaluating period-over-period metric deterioration, attributing root drivers, and drafting an underwriting credit memo.

RiskForge automates this entire pipeline:

```text
                     Public Financial Filings (yfinance)
                                     │
                                     ▼
                     ┌───────────────────────────────┐
                     │ Data Ingestion & Normalizer   │
                     │ (Balance Sheet, Income, Cash) │
                     └───────────────┬───────────────┘
                                     │
                                     ▼
                     ┌───────────────────────────────┐
                     │ Multi-Period Ratio Engine     │
                     │ (26 Core Credit Metrics & Z)  │
                     └───────────────┬───────────────┘
                                     │
                                     ▼
       ┌───────────────────────────────────────────────────────────┐
       │ SQL Historical Financial Data Store (SQLite / db_manager) │
       │ (ratio_snapshots: Indexed by ticker & period_year)       │
       └─────────────────────────────┬─────────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│ Risk Deterioration│      │ Capital Structure│       │ Scenario Stress  │
│ & Driver Engine  │       │ & Debt Capacity  │       │ Engine (Downside)│
│ (trend_detector) │       │ (debt_capacity)  │       │ (stress_engine)  │
└───────┬──────────┘       └─────────┬────────┘       └─────────┬────────┘
        │                            │                          │
        └────────────────────────────┼──────────────────────────┘
                                     ▼
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│ Refinancing Risk │       │ Covenant Monitor │       │ Cash Flow Model  │
│ Assessment       │       │ (Illustrative)   │       │ (3Y Projections) │
│(refinancing_risk)│       │(covenant_monitor)│       │ (cashflow_model) │
└───────┬──────────┘       └─────────┬────────┘       └─────────┬────────┘
        │                            │                          │
        └────────────────────────────┼──────────────────────────┘
                                     ▼
                     ┌───────────────────────────────┐
                     │ Credit Assessment Framework   │
                     │ (credit_framework.py)         │
                     └───────────────┬───────────────┘
                                     │
                                     ▼
                     ┌───────────────────────────────┐
                     │ Grounded AI Synthesis Layer   │
                     │ (Gemini 3.5 Flash API Guarded)│
                     └───────────────┬───────────────┘
                                     │
                                     ▼
          ┌─────────────────────────────────────────────────────┐
          │ Institutional Terminal Dashboard / Interactive View │
          │ (Streamlit App / SQL Analytics Workbench)           │
          └─────────────────────────────────────────────────────┘
```

---

## Core Analytical Capabilities

### 1. Multi-Period SQL Historical Data Store (`db_manager.py`)
RiskForge includes an embedded SQLite analytical database (`ratio_snapshots`) optimized with compound indexes on `(ticker, period_year)`:
* **26 Tracked Financial Metrics**: Stores balance-sheet items (Total Debt, Net Debt, Cash, Equity, Assets), income-statement metrics (Revenue, EBIT, EBITDA, Net Income, Interest Expense), cash flows (Operating Cash Flow, Free Cash Flow), and computed ratios (Debt/EBITDA, Interest Coverage, Liquidity Ratios, Margins, ROCE, Altman Z-Score).
* **Idempotent Upsert Storage**: Re-evaluating a company updates existing snapshot records using `INSERT OR REPLACE` to eliminate duplicate filings.
* **Analytical Query Layer**: Provides optimized SQL helper methods for single-ticker timelines (`get_ticker_history`), time-series metric extraction (`get_metric_timeseries`), peer group cross-sectional comparisons (`get_peer_comparison`), and custom read-only SQL queries (`run_custom_query`).

### 2. Risk Deterioration & Root-Cause Driver Engine (`trend_detector.py`)
Rather than relying solely on static point-in-time metrics, RiskForge analyzes multi-year trajectory across reporting periods:
* **Streak & Deterioration Detection**: Identifies metrics experiencing consecutive periods of negative deterioration (`WARNING`), single-period downturns (`CAUTION`), or multi-year structural drift (`WATCH`).
* **Directional Logic**: Intelligently classifies risk based on metric concern direction (e.g., rising Debt/EBITDA is negative; falling Interest Coverage or Margins is negative).
* **Underlying Driver Attribution**: When a ratio worsens, the engine isolates the underlying mathematical driver from the SQL store (e.g., *"Total Debt increased from \$20.3B to \$21.7B (+7.1%)"*, *"Interest Expense increased from \$1.0B to \$1.1B (+7.9%)"*).
* **Negative Distress Protection**: Ensures distressed negative metrics (e.g., negative EBITDA margins or negative interest coverage) are never misclassified as "strengthening" even if losses nominally narrow.
* **Dynamic Credit Risk Rating Migration**: Automatically evaluates if sustained multi-period deterioration warrants rating migration (e.g., escalating a point-in-time `ELEVATED` rating to `HIGH (ESCALATED)`, or assigning a `NEGATIVE WATCH` / `POSITIVE OUTLOOK`).

### 3. Credit Ratio Engine (`ratio_engine.py`)
Converts raw, normalized multi-period financial statements into a standardized credit risk profile:
* **Leverage Metrics**: Gross Debt / EBITDA, Net Debt / EBITDA, Debt / Equity, Debt / Total Assets.
* **Coverage Metrics**: EBIT Interest Coverage, EBITDA Interest Coverage.
* **Liquidity & Solvency**: Current Ratio, Quick Ratio, Cash Ratio, Working Capital.
* **Profitability & Cash Flow**: EBITDA Margin, Net Profit Margin, FCF Margin, Return on Capital Employed (ROCE), Operating Cash Flow, Free Cash Flow.
* **Bankruptcy Risk**: Altman Z-Score with automatic zone categorization (Distress, Grey, Safe).

### 4. Early-Warning System & Point-in-Time Flags (`signal_flags.py`)
Monitors multi-period trends and point-in-time ratio thresholds to raise structured risk flags:
* Severe leverage threshold breaches (`> 4.5x` High Risk, `> 3.5x` Elevated).
* Critically low interest coverage (`< 1.5x` Critical, `< 2.5x` Low).
* Sub-1.0x liquidity shortfalls (Current Ratio `< 1.0x`, Quick Ratio `< 0.8x`).
* Cash-burn conditions (negative Free Cash Flow).
* Altman Z-Score distress triggers (`< 1.81` Distress Zone, `1.81 - 2.99` Grey Zone).

### 5. Illustrative Debt Capacity Analysis (`debt_capacity.py`)
Evaluates borrowing capacity and capital structure flexibility under configurable policy caps:
* Maximum sustainable debt capacity based on user-defined Net Debt / EBITDA constraints.
* Incremental leverage headroom and unutilized debt capacity.
* Free cash flow deleveraging constraints and estimated years to retire debt from internal cash generation.

### 6. Downside Scenario Stress Engine (`stress_engine.py`)
Simulates corporate resilience against macro shocks:
* **Scenarios**: Base Case, Moderate Downside (-10% Revenue, -200 bps EBITDA Margin, +150 bps Interest Rate), and Severe Stress (-20% Revenue, -400 bps EBITDA Margin, +300 bps Interest Rate).
* Recomputes stressed earnings, coverage, and leverage to identify whether liquidity buffers survive adverse cycles.

### 7. Refinancing & Rollover Exposure (`refinancing_risk.py`)
Identifies near-term debt refinancing vulnerability using observable balance sheet proxies:
* Debt / Free Cash Flow coverage.
* Cash-to-debt ratios.
* Interest expense burden relative to operating cash flows.

### 8. Illustrative Covenant Compliance (`covenant_monitor.py`)
Tests period ratios against standard institutional debt covenants (e.g., Net Leverage `<= 3.75x`, Interest Coverage `>= 3.0x`, Current Ratio `>= 1.1x`):
* Calculates headroom, percentage cushion to default, and compliance status (`OK`, `TIGHT`, `BREACH`).

### 9. Multi-Market & Global Coverage
Out of the box, RiskForge supports both single-ticker custom deep dives and 10-company Sector Cohort benchmarks across multiple global equity markets:
* **United States (NYSE/NASDAQ)**: Defense & Aerospace, Technology, Financials, Healthcare.
* **India (NSE/BSE)**: Defense & Aerospace, Technology (IT), Financials, Healthcare/Pharma.
* **United Kingdom (LSE)**: Defense & Aerospace, Financials, Healthcare/Pharma.
* **Europe (Euronext)**: Defense & Aerospace, Technology, Financials.
* **Japan (TSE)**: Defense & Aerospace, Technology, Financials.
* **Custom Issuers**: Accepts any valid global ticker accessible via Yahoo Finance (e.g., `LMT`, `AAPL`, `HAL.NS`, `RR.L`, `ASML.AS`).

---

## Grounded AI Synthesis & Demo Safety

RiskForge utilizes the Google Gemini API (`gemini-3.5-flash`) to generate professional, institutional credit memorandums:
1. **Zero Hallucination Grounding**: The LLM does not compute ratios or perform arithmetic. It receives a strictly structured, verified JSON payload containing pre-computed ratios, stress outcomes, SQL trend alerts, and covenant statuses.
2. **Deterministic Fallback**: If an API key is missing or quotas are exhausted, RiskForge automatically produces a rule-based credit memorandum so the user experience never breaks.
3. **Enterprise Rate Limiting & Demo Protection**:
   * **Per-Session Quota**: Capped at 3 AI memo generations per browser session.
   * **Global Rate Limiter**: Thread-safe instance-wide hourly budget cap (20 calls/hour).
   * **SHA-256 Memo Cache**: Identical analysis payloads return instant cached memos without consuming API quota.
   * **Exponential Backoff**: Resilient retry mechanism for API rate limits (`429`) and service outages (`503`).

---

## Institutional Terminal UI

The Streamlit interface ([app.py](app.py)) is designed to evoke an institutional credit workstation (Bloomberg / S&P Capital IQ style):
* **Custom Typography**: Clean typography pairing `Inter` for UI elements and `IBM Plex Mono` for numerical precision and status indicators.
* **Terminal Masthead & Live Telemetry**: Live status indicators for the active SQLite data store and AI engine quota.
* **5-Card Credit Scorecard Strip**:
  1. *Point-in-Time Risk*: Rating derived from the latest financial filing.
  2. *Trend-Adjusted Risk*: Dynamic rating migration (e.g., `ELEVATED → HIGH (ESCALATED)`).
  3. *Historical Trajectory*: Multi-year trajectory status (`DETERIORATING`, `MIXED`, `STABLE`, `IMPROVING`).
  4. *Refinancing Risk*: Categorization of maturity and service risk.
  5. *Altman Z-Score*: Numerical score with credit zone categorization.
* **Tabbed Credit Dossier**:
  * **Financial Intelligence & SQL**: Deteriorating metrics table with driver attribution, multi-period ratio history, interactive time-series chart, and an embedded **SQL Analytics Workbench** with pre-configured query templates.
  * **Executive Credit Memo**: AI-generated structured credit memorandum.
  * **Fundamentals & Warnings**: Credit strengths/weaknesses and early-warning signal badges.
  * **Debt Capacity & Covenants**: Leverage headroom calculators and covenant headroom tables.
  * **Refinancing & Stress Testing**: Downside stress matrices and rollover risk factors.
* **State Persistence**: Full session-state caching ensures custom SQL queries, template selections, and chart customizations maintain their state across interactions without resetting the page.

---

## Project Structure

```text
RiskForge/
│
├── app.py                   # Institutional Streamlit terminal application
├── main.py                  # CLI pipeline & standalone HTML report generator
├── config.py                # Central thresholds, covenant definitions & assumptions
├── requirements.txt         # Core dependencies
│
├── db_manager.py            # SQLite historical financial data store & query layer
├── trend_detector.py        # Multi-period deterioration detection & driver attribution
├── intelligence_report.py   # Trend intelligence report formatting & prompt building
│
├── data_fetcher.py          # Yahoo Finance statement ingestion & alias normalization
├── ratio_engine.py          # 26 credit ratios, margins & Altman Z-Score calculations
├── signal_flags.py          # Early-warning signal flags & baseline risk ratings
│
├── debt_capacity.py         # Debt capacity limits & deleveraging capacity
├── stress_engine.py         # Macro scenario stress testing (Base / Moderate / Severe)
├── refinancing_risk.py      # Refinancing risk & rollover vulnerability assessment
├── covenant_monitor.py      # Illustrative covenant headroom & breach analysis
├── cashflow_model.py        # 3-year cash flow and operating projections
├── sector_overlay.py        # Sector context & peer categorization
├── credit_framework.py      # Consolidated structured credit assessment model
│
├── memo_generator.py        # Guarded Gemini API integration & fallback credit memo
├── report.py                # Standalone HTML/JavaScript report generator
│
└── tests/
    └── test_modules.py      # Unit test suite for deterministic calculation engines
```

---

## Getting Started

### 1. Prerequisites
* Python 3.10, 3.11, or 3.12+
* Git

### 2. Installation

```bash
# Clone the repository
git clone git@github.com:NotMayankfr/RiskForge.git
cd RiskForge

# Create and activate virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Gemini API (Optional)
To enable AI-synthesized credit memos, obtain an API key from Google AI Studio and configure it:

**Option A — Environment Variable:**
```bash
# Linux/macOS:
export GEMINI_API_KEY="your-api-key-here"

# Windows PowerShell:
$env:GEMINI_API_KEY="your-api-key-here"
```

**Option B — Streamlit Secrets (`.streamlit/secrets.toml`):**
```toml
GEMINI_API_KEY = "your-api-key-here"
```
*(If no API key is provided, the platform automatically utilizes deterministic rule-based credit memos.)*

### 4. Running the Application

**Launch the Interactive Web Application:**
```bash
streamlit run app.py
```

**Generate Standalone Offline HTML Report (CLI):**
```bash
# With AI Memo generation:
python main.py

# Without LLM calls (deterministic only):
python main.py --no-memo
```

---

## SQL Analytics Workbench Examples

The built-in SQLite data store enables custom financial analytics. Here are sample queries you can execute directly within the dashboard's SQL Workbench:

#### Multi-Year Leverage & Coverage Evolution
```sql
SELECT 
    period_year,
    ROUND(revenue / 1e9, 2) AS revenue_bn,
    ROUND(ebitda / 1e9, 2) AS ebitda_bn,
    ROUND(total_debt / 1e9, 2) AS debt_bn,
    ROUND(debt_ebitda, 2) AS debt_ebitda,
    ROUND(ebit_coverage, 2) AS interest_coverage,
    ROUND(z_score, 2) AS altman_z
FROM ratio_snapshots
WHERE ticker = 'LMT'
ORDER BY period_year ASC;
```

#### Year-over-Year Deterioration Delta
```sql
SELECT 
    cur.period_year AS year,
    ROUND(prev.debt_ebitda, 2) AS prior_leverage,
    ROUND(cur.debt_ebitda, 2) AS current_leverage,
    ROUND(cur.debt_ebitda - prev.debt_ebitda, 2) AS leverage_delta,
    ROUND(cur.ebit_coverage - prev.ebit_coverage, 2) AS coverage_delta
FROM ratio_snapshots cur
JOIN ratio_snapshots prev 
  ON cur.ticker = prev.ticker AND cur.period_year = prev.period_year + 1
WHERE cur.ticker = 'LMT'
ORDER BY cur.period_year ASC;
```

#### Cross-Company Leverage Ranking
```sql
SELECT 
    ticker,
    company_name,
    sector,
    period_year,
    ROUND(debt_ebitda, 2) AS debt_ebitda,
    ROUND(ebit_coverage, 2) AS ebit_coverage,
    ROUND(z_score, 2) AS z_score,
    risk_rating
FROM ratio_snapshots r1
WHERE period_year = (SELECT MAX(period_year) FROM ratio_snapshots r2 WHERE r2.ticker = r1.ticker)
ORDER BY debt_ebitda DESC;
```

---

## Running Automated Tests

Run the test suite to verify the deterministic financial calculation modules and risk logic:

```bash
python -m unittest tests/test_modules.py
```

---

## Limitations & Disclaimers

* **Decision-Support Prototype**: RiskForge is designed as an analytical decision-support prototype, not a certified credit rating agency or production underwriting system.
* **Public Data Fidelity**: Financial data is sourced from public filings via `yfinance`. Certain proprietary line items (e.g., exact legal debt maturity schedules, off-balance-sheet commitments, bilateral bank covenants) may be unavailable in standardized public disclosures.
* **Illustrative Policies**: Debt capacity limits and covenant thresholds represent standard institutional rules of thumb and do not reflect specific legal credit agreements.
* **Independent Due Diligence**: Any outputs or simulated stress outcomes must be verified against primary audited financial statements before making lending or investment decisions.

---

## License

This project is licensed for educational, research, and institutional decision-support prototyping.
