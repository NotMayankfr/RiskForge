# RiskForge

### AI-Assisted Credit Intelligence & Decision Support Platform

RiskForge is a modular credit-risk analytics platform that turns public financial statements into a structured view of leverage, liquidity, debt-servicing capacity, refinancing exposure, downside resilience, and early-warning signals.

The system combines deterministic financial analysis with scenario modelling and a grounded LLM layer that converts the analytical outputs into a structured credit memorandum.

> **Current application:** Defense & Aerospace corporate credit analysis
> **Architecture:** Designed as a modular decision-support pipeline rather than a single predictive model

---

## What RiskForge Does

A traditional credit review involves collecting financial statements, calculating ratios, checking risk thresholds, running downside cases, interpreting the results, and finally writing a credit memo.

RiskForge automates that workflow.

```text
                    Public Financial Data
                           │
                           ▼
                   ┌─────────────────┐
                   │   Data Ingestion│
                   │     yfinance    │
                   └────────┬────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Financial Normalizer │
                 │ & Ratio Engine       │
                 └──────────┬───────────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
       Early-Warning    Debt Capacity   Stress Engine
          Signals          Analysis       Scenarios
              │             │              │
              └─────────────┼──────────────┘
                            ▼
                 ┌──────────────────────┐
                 │ Credit Risk Framework│
                 └──────────┬───────────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
        Refinancing      Covenant       Cash-Flow
           Risk          Monitoring      Projections
              │             │              │
              └─────────────┼──────────────┘
                            ▼
                 ┌──────────────────────┐
                 │ Grounded LLM Layer   │
                 │   Gemini API         │
                 └──────────┬───────────┘
                            ▼
                 Structured Credit Memo
                            │
                            ▼
                 Dashboard / HTML Report
```

The key design decision is that **the financial analysis remains deterministic and separate from the LLM**. The model is used primarily for synthesis and communication rather than performing the underlying calculations.

---

## Core Capabilities

### 1. Financial Data Ingestion

RiskForge retrieves annual financial statements through `yfinance` and normalizes inconsistent field names across companies.

The pipeline works with:

* Income statements
* Balance sheets
* Cash-flow statements
* Multiple historical reporting periods

The ingestion layer also handles missing fields and uses fallback mappings for common variations in financial-statement labels.

---

### 2. Credit Ratio Engine

The ratio engine converts raw statements into a structured credit profile.

Key metrics include:

* Debt / EBITDA
* Net Debt / EBITDA
* Debt / Equity
* Debt / Assets
* EBIT Interest Coverage
* EBITDA Interest Coverage
* Current Ratio
* Quick Ratio
* Cash Ratio
* EBITDA Margin
* Net Margin
* FCF Margin
* ROCE
* Free Cash Flow
* Altman Z-Score

The engine explicitly tracks missing data and data-quality notes rather than silently treating unavailable information as zero.

Where EBITDA is unavailable, the implementation attempts to derive it from EBIT and depreciation before using an explicitly labelled illustrative fallback.

---

### 3. Early-Warning System

RiskForge looks beyond point-in-time ratios and identifies deteriorating trends.

The early-warning engine can flag:

* Excessive leverage
* Rising Debt / EBITDA
* Weak interest coverage
* Declining interest coverage
* Liquidity pressure
* Negative free cash flow
* Altman Z-Score distress conditions
* Other configurable threshold breaches

Each signal contains a severity, category, message, metric, and value so that downstream components can reason over structured risk information.

---

### 4. Debt-Capacity Analysis

The debt-capacity module estimates how much additional debt a company could theoretically sustain under configurable leverage assumptions.

It evaluates:

* Current gross leverage
* Current net leverage
* Illustrative sustainable debt capacity
* Leverage headroom
* Incremental debt capacity
* FCF-based deleveraging constraints

These figures are explicitly treated as **analytical estimates rather than lender-specific underwriting limits**.

---

### 5. Scenario Stress Testing

RiskForge tests the resilience of a company's capital structure under multiple downside scenarios.

Scenarios independently modify assumptions such as:

* Revenue growth / decline
* EBITDA margin
* Interest-rate shock

The engine then recalculates:

* Revenue
* EBITDA
* EBIT
* Interest expense
* Debt / EBITDA
* Net Debt / EBITDA
* EBIT interest coverage
* EBITDA interest coverage

This allows the user to examine how quickly credit metrics deteriorate when operating or financing conditions worsen.

---

### 6. Refinancing-Risk Assessment

Because public data does not reliably provide complete legal debt maturity schedules, RiskForge does not fabricate them.

Instead, the refinancing module assesses point-in-time refinancing pressure through observable proxies:

* Net leverage
* Debt / FCF
* Interest burden
* Cash coverage

The output identifies the factors contributing to the resulting refinancing-risk classification.

---

### 7. Illustrative Covenant Monitoring

RiskForge can test financial ratios against configurable covenant thresholds.

It evaluates:

* Maximum Net Debt / EBITDA
* Maximum Debt / EBITDA
* Minimum Interest Coverage
* Minimum Current Ratio

For each metric it calculates:

* Current value
* Threshold
* Headroom
* Headroom percentage
* Breach / Tight / OK status

The thresholds are explicitly labelled **illustrative** and are not represented as actual legal covenants.

---

### 8. Cash-Flow Projection

The cash-flow model produces simplified forward projections using configurable assumptions for:

* Revenue growth
* EBITDA margin
* Capital-expenditure margin

It produces projected:

* Revenue
* EBITDA
* Capex
* Free cash flow

The model clearly distinguishes these outputs from historical financial statements and labels them as illustrative projections rather than forecasts.

---

### 9. Credit Assessment Framework

The credit framework synthesizes the outputs of the analytical modules into a structured assessment.

It identifies:

* Financial strengths
* Financial weaknesses
* Key risk indicators
* Credit-view classification
* Monitoring priorities

This intermediate structured representation is important because it gives the LLM a compact, machine-readable analytical context instead of asking it to infer financial conclusions directly from raw data.

---

## LLM Layer

RiskForge uses the Gemini API to generate structured credit memoranda from the outputs of the analytical engines.

The LLM is **not responsible for calculating financial ratios**.

Instead:

```text
Financial Statements
       ↓
Deterministic Calculations
       ↓
Risk / Stress Analysis
       ↓
Structured Analytical Outputs
       ↓
LLM
       ↓
Human-readable Credit Memo
```

The prompt layer is explicitly designed to reduce unsupported generation. It instructs the model to:

* Use only the supplied analytical data
* Avoid inventing financial facts
* Acknowledge unavailable information
* Distinguish assumptions from observed data
* Treat covenant thresholds and stress scenarios as illustrative
* Produce a structured professional credit memo

There is also a fallback path that produces a deterministic credit memo when the Gemini API is unavailable.

This separation makes the system easier to reason about: **the numerical layer determines the analytical facts; the LLM turns those facts into readable decision-support output.**

---

## Dashboard

The project provides two interfaces.

### Streamlit Application

`app.py` provides an interactive interface for:

* Selecting a company or sector
* Selecting markets
* Running comprehensive analysis
* Configuring analytical assumptions
* Generating AI-assisted credit output

### HTML Reporting Pipeline

`main.py` orchestrates the full analysis pipeline and produces a self-contained HTML report containing:

* Company-level credit summaries
* Risk classifications
* Financial metrics
* Stress scenarios
* Early-warning signals
* Credit analysis
* Visual reporting

---

## Project Structure

```text
RiskForge/
│
├── app.py                 # Streamlit application
├── main.py                # End-to-end pipeline orchestrator
│
├── data_fetcher.py        # Financial statement ingestion
├── ratio_engine.py        # Core financial and credit metrics
├── signal_flags.py        # Early-warning and trend detection
│
├── debt_capacity.py       # Debt capacity and leverage headroom
├── stress_engine.py       # Downside scenario analysis
├── refinancing_risk.py    # Refinancing-risk assessment
├── covenant_monitor.py    # Illustrative covenant testing
├── cashflow_model.py      # Forward cash-flow modelling
├── sector_overlay.py      # Sector-specific context
├── credit_framework.py    # Structured credit assessment
│
├── memo_generator.py      # Gemini-powered credit memo generation
├── report.py              # HTML dashboard/report generation
├── config.py              # Thresholds and modelling assumptions
│
├── requirements.txt       # Python dependencies
│
└── tests/
    └── test_modules.py    # Deterministic unit tests
```

---

## Engineering Decisions

### Deterministic core, probabilistic interface

Financial calculations are implemented in Python rather than delegated to the language model. This makes core outputs reproducible and testable.

The LLM is placed at the interpretation layer, where natural-language generation provides value without becoming the source of truth for numerical calculations.

### Graceful handling of incomplete data

Public financial datasets are not perfectly standardized. RiskForge therefore:

* Uses alias-based field matching
* Tracks unavailable metrics
* Propagates `NaN` instead of silently inventing values
* Records data-quality notes
* Provides explicit methodology notes for proxy calculations

### Modular architecture

Each analytical function is separated into an independent module.

This makes individual components replaceable without redesigning the entire system. For example, the same credit-analysis framework can accept a different data source or domain-specific input layer without requiring the stress-testing or reporting engines to be rewritten.

### Testable analytical logic

The core analytical modules have deterministic unit tests covering financial calculations and risk logic.

Run:

```bash
python -m unittest tests/test_modules.py
```

---

## Data & Modelling Limitations

RiskForge is a **decision-support and analytical prototype**, not a production underwriting system.

Important limitations include:

* Data is retrieved from public financial information through `yfinance`.
* `yfinance` does not reliably expose complete legal debt maturity schedules.
* Actual loan agreements and legal covenant definitions are unavailable.
* Covenant thresholds used by the application are illustrative.
* Forward projections are assumption-driven scenarios, not forecasts.
* Some financial metrics may use proxy methodologies when source data is unavailable.
* The original Altman Z-Score implementation uses a book-equity proxy where market capitalization is unavailable, which can reduce comparability across firms and industries.
* The current sector overlay is configured for Defense & Aerospace companies.
* Results should be independently validated before being used for a real lending or investment decision.

---

## Installation

### 1. Clone the repository

```bash
git clone git@github.com:NotMayankfr/RiskForge.git
cd RiskForge
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Configuration

RiskForge uses the Gemini API for AI-assisted memo generation.

Set the API key as an environment variable:

```bash
export GEMINI_API_KEY="your-api-key"
```

On Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="your-api-key"
```

The application also supports entering the API key through the Streamlit interface.

**Never commit API keys or credentials to the repository.**

---

## Running the Project

### Interactive application

```bash
streamlit run app.py
```

### Full command-line pipeline

```bash
python main.py
```

To run the analytical pipeline without LLM memo generation:

```bash
python main.py --no-memo
```

---

## Example Workflow

For a selected company, RiskForge approximately follows:

```text
Ticker
  ↓
Annual Financial Statements
  ↓
Financial Normalization
  ↓
Historical Ratios
  ↓
Trend & Early-Warning Analysis
  ↓
Debt Capacity
  ↓
Stress Scenarios
  ↓
Refinancing Risk
  ↓
Covenant Monitoring
  ↓
Cash-Flow Projection
  ↓
Credit Framework
  ↓
Gemini-Assisted Credit Memo
  ↓
Interactive Report
```

The resulting output is intended to answer questions such as:

> How leveraged is the company?

> How well can operating earnings service interest?

> Is liquidity deteriorating?

> How much illustrative leverage headroom exists?

> What happens to credit metrics under a downside scenario?

> Which indicators warrant further monitoring?

> Can the analytical findings be communicated as a structured credit memo?

---

## Why I Built It

Credit analysis is often presented as a collection of financial ratios. RiskForge approaches it as a **workflow and systems problem**.

The objective was to connect data ingestion, financial reasoning, scenario analysis, risk detection, and AI-assisted communication into one reproducible pipeline.

The result is a system where each stage has a defined responsibility:

**data is collected → metrics are calculated → risks are surfaced → scenarios are tested → evidence is synthesized → conclusions are communicated.**

That architecture is intentionally more important than any single metric or model.

---

## Tech Stack

**Language:** Python

**Data & Analytics:** Pandas, yfinance

**Application:** Streamlit

**AI:** Google Gemini API

**Reporting:** HTML, JavaScript / Chart.js

**Testing:** Python `unittest`

**Architecture:** Modular pipeline with deterministic analytical engines and an LLM synthesis layer

---

## License

This project is intended for educational, research, and analytical use.
