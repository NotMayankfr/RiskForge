"""
config.py
Central configuration: company list, API keys, ratio thresholds,
debt-capacity assumptions, stress-test scenarios, covenant thresholds.

DISCLAIMER: All assumptions (leverage caps, coverage floors, stress
scenarios) are illustrative analytical parameters only. They do NOT
represent any institution's actual underwriting standards or policies.
"""

import os

# ── Gemini API ───────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
GEMINI_MODEL: str = "gemini-3.8-flash"

# ── Defense sector companies ─────────────────────────────────────────────────
COMPANIES: list[dict] = [
    {"name": "Raytheon Technologies",  "ticker": "RTX",    "country": "USA",    "exchange": "NYSE"},
    {"name": "Lockheed Martin",        "ticker": "LMT",    "country": "USA",    "exchange": "NYSE"},
    {"name": "Northrop Grumman",       "ticker": "NOC",    "country": "USA",    "exchange": "NYSE"},
    {"name": "General Dynamics",       "ticker": "GD",     "country": "USA",    "exchange": "NYSE"},
    {"name": "L3Harris Technologies",  "ticker": "LHX",    "country": "USA",    "exchange": "NYSE"},
    {"name": "Dassault Aviation",      "ticker": "AM.PA",  "country": "France", "exchange": "Euronext"},
    {"name": "BAE Systems",            "ticker": "BAESY",  "country": "UK",     "exchange": "OTC-ADR"},
    {"name": "Thales Group",           "ticker": "HO.PA",  "country": "France", "exchange": "Euronext"},
    {"name": "Hindustan Aeronautics",  "ticker": "HAL.NS", "country": "India",  "exchange": "NSE"},
    {"name": "Bharat Electronics",     "ticker": "BEL.NS", "country": "India",  "exchange": "NSE"},
]

# ── Early-warning / flag thresholds ─────────────────────────────────────────
THRESHOLDS: dict = {
    "debt_ebitda_high":             4.0,
    "debt_ebitda_elevated":         2.5,
    "net_debt_ebitda_high":         3.5,
    "debt_equity_high":             2.0,
    "interest_coverage_low":        3.0,
    "interest_coverage_critical":   1.5,
    "current_ratio_low":            1.0,
    "quick_ratio_low":              0.8,
    "z_score_distress":             1.81,
    "z_score_grey":                 2.99,
    "trend_years":                  2,
}

# ── Debt-capacity assumptions ─────────────────────────────────────────────────
# ILLUSTRATIVE ONLY — not any institution's actual underwriting criteria.
DEBT_CAPACITY: dict = {
    # Maximum sustainable Net Debt / EBITDA (illustrative leverage cap)
    "max_net_leverage":             4.0,    # x EBITDA
    # Minimum interest coverage required (illustrative floor)
    "min_interest_coverage":        3.0,    # x EBIT/Interest
    # Assumed long-run cost of debt for capacity calculations (illustrative)
    "assumed_cost_of_debt":         0.055,  # 5.5%
    # EBITDA haircut for stress-adjusted capacity
    "ebitda_downside_pct":          0.15,   # 15% EBITDA decline
    # Interest rate shock applied to existing debt for sensitivity
    "interest_rate_shock_bps":      200,    # +200 bps
}

# ── Stress-test scenarios ────────────────────────────────────────────────────
# ILLUSTRATIVE ONLY — user-defined; not actual forecasts.
STRESS_SCENARIOS: dict = {
    "base": {
        "label":                "Base Case",
        "revenue_change_pct":   0.0,
        "margin_change_ppt":    0.0,        # EBITDA margin change in percentage points
        "interest_rate_shock":  0.0,        # additional interest rate (absolute, e.g. 0.01 = +100bps)
    },
    "moderate": {
        "label":                "Moderate Downside",
        "revenue_change_pct":   -0.10,      # -10% revenue
        "margin_change_ppt":    -2.0,       # -200bps EBITDA margin
        "interest_rate_shock":  0.01,       # +100bps
    },
    "severe": {
        "label":                "Severe Downside",
        "revenue_change_pct":   -0.20,      # -20% revenue
        "margin_change_ppt":    -4.0,       # -400bps EBITDA margin
        "interest_rate_shock":  0.02,       # +200bps
    },
}

# ── Illustrative covenant thresholds ────────────────────────────────────────
# ILLUSTRATIVE ONLY — these are NOT the actual legal covenants of any company.
# Label all outputs "Illustrative Covenant Analysis".
COVENANT_THRESHOLDS: dict = {
    "max_net_debt_ebitda":    4.0,   # x — illustrative maintenance covenant
    "max_debt_ebitda":        4.5,   # x — illustrative gross leverage covenant
    "min_interest_coverage":  2.5,   # x — illustrative coverage covenant
    "min_current_ratio":      1.0,   # x — illustrative liquidity covenant
}

# ── Refinancing risk classification ─────────────────────────────────────────
REFINANCING_THRESHOLDS: dict = {
    # Debt / EBITDA bands
    "leverage_elevated":      3.5,   # above this → elevated concern
    "leverage_moderate":      2.0,   # above this → moderate concern
    # Debt / FCF bands
    "debt_fcf_elevated":      10.0,
    "debt_fcf_moderate":      6.0,
    # Interest burden (Interest Expense / EBITDA)
    "interest_burden_high":   0.30,  # 30% of EBITDA going to interest
    "interest_burden_moderate": 0.15,
    # Cash / Total Debt
    "cash_cover_low":         0.10,  # cash covers <10% of debt → risk
    "cash_cover_moderate":    0.25,
}

# ── Cash-flow projection assumptions ────────────────────────────────────────
PROJECTION_ASSUMPTIONS: dict = {
    "revenue_growth_pct":     0.05,   # 5% per year illustrative growth
    "ebitda_margin_pct":      None,   # None = use latest actual
    "capex_pct_revenue":      None,   # None = use latest actual ratio
    "projection_years":       3,
}

# ── Output directory ─────────────────────────────────────────────────────────
OUTPUT_DIR: str = "output"
