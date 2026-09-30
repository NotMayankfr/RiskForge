"""
debt_capacity.py
================
Debt-capacity analysis module for the defense-sector credit analysis tool.

DISCLAIMER
----------
All outputs are ILLUSTRATIVE ONLY and do NOT represent any bank's, institution's,
or JPMorgan Chase's actual underwriting standards, credit policies, or opinions.
Results are produced solely for analytical / educational purposes.

Usage
-----
    from debt_capacity import compute_debt_capacity

    capacity = compute_debt_capacity(ratios_dict)

The `ratios_dict` should be the output produced by the ratio_engine module for a
company's TTM / Latest-FY period.  All monetary values are expected to be in the
same currency unit (e.g. USD millions).

Author : Defense Credit Tool – quantitative analytics layer
"""

from __future__ import annotations

import math
from typing import Any

import config


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(value: Any, default: float = math.nan) -> float:
    """Coerce *value* to float; return *default* on None / non-finite strings."""
    if value is None:
        return default
    try:
        f = float(value)
        return f
    except (TypeError, ValueError):
        return default


def _is_nan(v: float) -> bool:
    """Return True if *v* is NaN (avoids importing numpy)."""
    try:
        return math.isnan(v)
    except TypeError:
        return True


def _safe_div(numerator: float, denominator: float) -> float:
    """
    Divide two floats safely.

    Returns
    -------
    float
        ``numerator / denominator``, or ``math.nan`` when *denominator* is zero,
        either argument is NaN, or either argument is not a real number.
    """
    if _is_nan(numerator) or _is_nan(denominator):
        return math.nan
    if denominator == 0.0:
        return math.nan
    return numerator / denominator


def _non_negative(v: float) -> float:
    """Return *v* floored at 0.0; propagates NaN."""
    if _is_nan(v):
        return math.nan
    return max(0.0, v)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def compute_debt_capacity(ratios: dict[str, Any]) -> dict[str, Any]:
    """
    Compute illustrative debt-capacity metrics for a single company period.

    Parameters
    ----------
    ratios : dict
        Output dict from the ratio_engine module for one company / one period.
        Expected keys (all optional — missing values degrade gracefully):

        * ``ebitda``            – Earnings Before Interest, Tax, D&A (USD M)
        * ``ebit``              – Earnings Before Interest & Tax (USD M)
        * ``net_debt``          – Total Debt minus Cash & equivalents (USD M)
        * ``total_debt``        – Gross financial debt (USD M)
        * ``interest_expense``  – Cash interest paid / accrued (USD M)
        * ``fcf``               – Free Cash Flow (USD M)
        * ``revenue``           – Net Revenue / Turnover (USD M)
        * ``cash``              – Cash & short-term investments (USD M)
        * ``total_equity``      – Book equity (USD M)
        * ``total_assets``      – Total assets on balance sheet (USD M)

    Returns
    -------
    dict
        Dictionary containing the following keys:

        Leverage metrics
        ~~~~~~~~~~~~~~~~
        ``current_net_leverage``
            Net Debt / EBITDA.  NaN when EBITDA <= 0.
        ``current_gross_leverage``
            Total Debt / EBITDA.  NaN when EBITDA <= 0.

        Capacity estimates (illustrative)
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ``max_sustainable_debt``
            max_net_leverage × EBITDA (config-driven cap).
        ``leverage_headroom``
            max_sustainable_debt − Net Debt.  Can be negative.
        ``incremental_debt_capacity``
            max(0, leverage_headroom) — floored at zero.
        ``coverage_constraint_max_debt``
            Maximum debt implied by the interest-coverage constraint:
            (EBIT / min_interest_coverage) / assumed_cost_of_debt.
        ``binding_constraint``
            'leverage', 'coverage', or 'N/A' — whichever cap is more restrictive.

        Stress metrics
        ~~~~~~~~~~~~~~
        ``stress_ebitda``
            EBITDA × (1 − ebitda_downside_pct).
        ``stress_net_leverage``
            Net Debt / stress_ebitda.
        ``stress_incremental_capacity``
            max(0, max_net_leverage × stress_ebitda − net_debt).
        ``interest_rate_shock_cost``
            Additional annual interest cost from +interest_rate_shock_bps shock
            applied to total_debt (USD M).

        FCF-based paydown metrics
        ~~~~~~~~~~~~~~~~~~~~~~~~~
        ``fcf_paydown_years``
            Total Debt / FCF — years to pay off gross debt from FCF.
            NaN when FCF <= 0.
        ``fcf_paydown_pct``
            FCF / Total Debt × 100 — annual debt paydown as % of gross debt.
            NaN when total_debt <= 0 or FCF <= 0.

        Metadata
        ~~~~~~~~
        ``assumptions``
            Copy of ``config.DEBT_CAPACITY`` used for this run.
        ``data_quality_notes``
            List of strings describing any missing inputs or fallback assumptions.

    Notes
    -----
    * All monetary outputs are in the same unit as the inputs (typically USD M).
    * Negative EBITDA causes leverage ratios to become NaN to avoid
      misleading sign-flip artefacts.
    * This module never raises on bad data; edge cases are NaN / noted.
    """
    # ── Pull assumptions from config ──────────────────────────────────────────
    cfg: dict[str, float] = dict(config.DEBT_CAPACITY)
    max_net_lev: float      = float(cfg["max_net_leverage"])
    min_cov: float          = float(cfg["min_interest_coverage"])
    cost_of_debt: float     = float(cfg["assumed_cost_of_debt"])
    ebitda_haircut: float   = float(cfg["ebitda_downside_pct"])
    shock_bps: float        = float(cfg["interest_rate_shock_bps"])

    # ── Extract inputs safely ─────────────────────────────────────────────────
    ebitda:           float = _safe(ratios.get("ebitda"))
    ebit:             float = _safe(ratios.get("ebit"))
    net_debt:         float = _safe(ratios.get("net_debt"))
    total_debt:       float = _safe(ratios.get("total_debt"))
    interest_expense: float = _safe(ratios.get("interest_expense"))
    fcf:              float = _safe(ratios.get("fcf"))
    cash:             float = _safe(ratios.get("cash"))          # noqa: F841 (available for callers)
    total_equity:     float = _safe(ratios.get("total_equity"))  # noqa: F841
    total_assets:     float = _safe(ratios.get("total_assets"))  # noqa: F841
    revenue:          float = _safe(ratios.get("revenue"))       # noqa: F841

    notes: list[str] = []

    # ── Helper: EBITDA validity ───────────────────────────────────────────────
    # Leverage ratios are meaningless / misleading when EBITDA is negative.
    ebitda_positive: bool = (not _is_nan(ebitda)) and (ebitda > 0.0)

    if _is_nan(ebitda):
        notes.append("EBITDA not available; leverage and capacity metrics set to NaN.")
    elif not ebitda_positive:
        notes.append(
            f"EBITDA is non-positive ({ebitda:.1f}); leverage ratios set to NaN "
            "to avoid misleading sign-flip artefacts."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Current leverage
    # ─────────────────────────────────────────────────────────────────────────
    current_net_leverage: float = (
        _safe_div(net_debt, ebitda) if ebitda_positive else math.nan
    )
    current_gross_leverage: float = (
        _safe_div(total_debt, ebitda) if ebitda_positive else math.nan
    )

    if _is_nan(net_debt):
        notes.append("net_debt not available; net leverage set to NaN.")
    if _is_nan(total_debt):
        notes.append("total_debt not available; gross leverage set to NaN.")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Max sustainable debt (leverage constraint)
    # ─────────────────────────────────────────────────────────────────────────
    max_sustainable_debt: float = (
        max_net_lev * ebitda if ebitda_positive else math.nan
    )

    # leverage_headroom can be negative (company already above cap)
    leverage_headroom: float
    if _is_nan(max_sustainable_debt) or _is_nan(net_debt):
        leverage_headroom = math.nan
    else:
        leverage_headroom = max_sustainable_debt - net_debt

    incremental_debt_capacity: float = _non_negative(leverage_headroom)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Coverage-constraint max debt
    # ─────────────────────────────────────────────────────────────────────────
    # Maximum interest EBIT can support at the minimum coverage ratio:
    #   max_interest = EBIT / min_interest_coverage
    # Maximum debt that service implies (at assumed cost of debt):
    #   max_debt = max_interest / assumed_cost_of_debt
    coverage_constraint_max_debt: float

    if _is_nan(ebit):
        coverage_constraint_max_debt = math.nan
        notes.append(
            "EBIT not available; coverage-constraint capacity set to NaN."
        )
    elif cost_of_debt <= 0.0:
        coverage_constraint_max_debt = math.nan
        notes.append(
            "assumed_cost_of_debt is zero or negative in config; "
            "coverage-constraint capacity set to NaN."
        )
    else:
        max_supportable_interest = ebit / min_cov
        coverage_constraint_max_debt = max_supportable_interest / cost_of_debt

    if _is_nan(interest_expense):
        notes.append(
            "interest_expense not available; coverage adequacy check skipped. "
            "coverage_constraint_max_debt derived solely from EBIT."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Binding constraint
    # ─────────────────────────────────────────────────────────────────────────
    binding_constraint: str
    lev_cap_available = not _is_nan(incremental_debt_capacity)
    cov_cap_available = not _is_nan(coverage_constraint_max_debt)

    if not lev_cap_available and not cov_cap_available:
        binding_constraint = "N/A"
    elif not cov_cap_available:
        binding_constraint = "leverage"
    elif not lev_cap_available:
        binding_constraint = "coverage"
    else:
        # Whichever cap yields the LOWER permissible debt is binding.
        # Coverage cap = coverage_constraint_max_debt (absolute USD)
        # Leverage cap = max_sustainable_debt (absolute USD)
        # Compare apples-to-apples.
        if coverage_constraint_max_debt <= max_sustainable_debt:
            binding_constraint = "coverage"
        else:
            binding_constraint = "leverage"

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Stress analysis
    # ─────────────────────────────────────────────────────────────────────────
    stress_ebitda: float = (
        ebitda * (1.0 - ebitda_haircut) if ebitda_positive else math.nan
    )
    if not _is_nan(ebitda) and ebitda <= 0.0:
        # Still compute stress from a negative base — but note it
        stress_ebitda = ebitda * (1.0 - ebitda_haircut)
        notes.append(
            "Stress EBITDA computed from a non-positive base; "
            "stress leverage ratios will be NaN."
        )

    stress_ebitda_positive: bool = (not _is_nan(stress_ebitda)) and (stress_ebitda > 0.0)

    stress_net_leverage: float = (
        _safe_div(net_debt, stress_ebitda) if stress_ebitda_positive else math.nan
    )

    stress_incremental_capacity: float
    if stress_ebitda_positive and not _is_nan(net_debt):
        stress_incremental_capacity = _non_negative(
            max_net_lev * stress_ebitda - net_debt
        )
    else:
        stress_incremental_capacity = math.nan

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Interest rate shock
    # ─────────────────────────────────────────────────────────────────────────
    # Additional annual interest cost from the rate shock on EXISTING debt.
    interest_rate_shock_cost: float
    if _is_nan(total_debt):
        interest_rate_shock_cost = math.nan
        notes.append(
            "total_debt not available; interest_rate_shock_cost set to NaN."
        )
    else:
        interest_rate_shock_cost = total_debt * shock_bps / 10_000.0

    # ─────────────────────────────────────────────────────────────────────────
    # 7. FCF-based paydown metrics
    # ─────────────────────────────────────────────────────────────────────────
    fcf_paydown_years: float
    fcf_paydown_pct: float

    if _is_nan(fcf):
        fcf_paydown_years = math.nan
        fcf_paydown_pct = math.nan
        notes.append("FCF not available; FCF paydown metrics set to NaN.")
    elif fcf <= 0.0:
        fcf_paydown_years = math.nan
        fcf_paydown_pct   = math.nan
        notes.append(
            f"FCF is non-positive ({fcf:.1f}); "
            "FCF paydown metrics set to NaN (elevated liquidity risk)."
        )
    else:
        if _is_nan(total_debt) or total_debt <= 0.0:
            fcf_paydown_years = math.nan
            fcf_paydown_pct   = math.nan
            notes.append(
                "total_debt is zero or missing; FCF paydown metrics set to NaN."
            )
        else:
            fcf_paydown_years = total_debt / fcf
            fcf_paydown_pct   = (fcf / total_debt) * 100.0

    # ─────────────────────────────────────────────────────────────────────────
    # Assemble output
    # ─────────────────────────────────────────────────────────────────────────
    return {
        # Current leverage
        "current_net_leverage":          current_net_leverage,
        "current_gross_leverage":        current_gross_leverage,
        # Capacity (leverage constraint)
        "max_sustainable_debt":          max_sustainable_debt,
        "leverage_headroom":             leverage_headroom,
        "incremental_debt_capacity":     incremental_debt_capacity,
        # Capacity (coverage constraint)
        "coverage_constraint_max_debt":  coverage_constraint_max_debt,
        # Binding constraint flag
        "binding_constraint":            binding_constraint,
        # Stress analysis
        "stress_ebitda":                 stress_ebitda,
        "stress_net_leverage":           stress_net_leverage,
        "stress_incremental_capacity":   stress_incremental_capacity,
        # Rate shock sensitivity
        "interest_rate_shock_cost":      interest_rate_shock_cost,
        # FCF paydown
        "fcf_paydown_years":             fcf_paydown_years,
        "fcf_paydown_pct":               fcf_paydown_pct,
        # Metadata
        "assumptions":                   cfg,
        "data_quality_notes":            notes,
    }
