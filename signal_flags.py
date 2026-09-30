"""
signal_flags.py
Detects early-warning credit signals from multi-period ratio trends.
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field

from config import THRESHOLDS

logger = logging.getLogger(__name__)

SENTINEL = float("nan")


@dataclass
class CreditFlag:
    severity: str          # "CRITICAL", "WARNING", "INFO"
    category: str          # "LEVERAGE", "COVERAGE", "LIQUIDITY", "Z-SCORE"
    message: str
    metric: str
    value: float           # latest value that triggered the flag


def _trend_deteriorating(values: list[float], n: int = 2) -> bool:
    """
    Returns True if the metric has deteriorated for at least `n`
    consecutive periods (values ordered most-recent → oldest).
    Higher = worse for leverage; lower = worse for coverage/liquidity.
    """
    valid = [v for v in values if not math.isnan(v)]
    if len(valid) < n + 1:
        return False
    # Check most-recent n consecutive pairs
    for i in range(n):
        if valid[i] >= valid[i + 1]:  # should be decreasing = deteriorating coverage
            return False
    return True


def _trend_rising(values: list[float], n: int = 2) -> bool:
    """Returns True if metric has risen for at least n consecutive periods."""
    valid = [v for v in values if not math.isnan(v)]
    if len(valid) < n + 1:
        return False
    for i in range(n):
        if valid[i] <= valid[i + 1]:
            return False
    return True


def analyze_flags(period_ratios: dict[str, dict], company_name: str) -> list[CreditFlag]:
    """
    Run all early-warning checks on a company's multi-period ratios.

    Args:
        period_ratios: { "TTM": {...}, "2023": {...}, ... }
        company_name: For logging.

    Returns:
        List of CreditFlag objects, sorted by severity.
    """
    flags: list[CreditFlag] = []
    t = THRESHOLDS

    # Order: TTM first, then historical (most recent first)
    ordered_keys = list(period_ratios.keys())  # TTM, 2023, 2022, 2021

    def series(metric: str) -> list[float]:
        return [period_ratios[k].get(metric, SENTINEL) for k in ordered_keys]

    ttm = period_ratios.get("TTM", {})

    def get(key: str) -> float:
        return ttm.get(key, SENTINEL)

    # ── LEVERAGE FLAGS ───────────────────────────────────────────────────────

    de = get("debt_ebitda")
    if not math.isnan(de):
        if de > t["debt_ebitda_high"]:
            flags.append(CreditFlag(
                severity="CRITICAL", category="LEVERAGE",
                message=f"Debt/EBITDA of {de:.1f}x exceeds high-risk threshold ({t['debt_ebitda_high']}x).",
                metric="debt_ebitda", value=de,
            ))
        elif de > t["debt_ebitda_elevated"]:
            flags.append(CreditFlag(
                severity="WARNING", category="LEVERAGE",
                message=f"Debt/EBITDA of {de:.1f}x is elevated (>{t['debt_ebitda_elevated']}x).",
                metric="debt_ebitda", value=de,
            ))

    # Rising leverage trend
    de_series = series("debt_ebitda")
    if _trend_rising(de_series, n=t["trend_years"]):
        flags.append(CreditFlag(
            severity="WARNING", category="LEVERAGE",
            message=f"Debt/EBITDA rising for {t['trend_years']}+ consecutive years — leverage trend worsening.",
            metric="debt_ebitda_trend", value=de_series[0],
        ))

    # Debt/Equity
    deq = get("debt_equity")
    if not math.isnan(deq) and deq > t["debt_equity_high"]:
        flags.append(CreditFlag(
            severity="WARNING", category="LEVERAGE",
            message=f"Debt/Equity of {deq:.1f}x exceeds {t['debt_equity_high']}x — balance sheet stretched.",
            metric="debt_equity", value=deq,
        ))

    # ── COVERAGE FLAGS ───────────────────────────────────────────────────────

    ic = get("ebit_coverage")
    if not math.isnan(ic):
        if ic < t["interest_coverage_critical"]:
            flags.append(CreditFlag(
                severity="CRITICAL", category="COVERAGE",
                message=f"EBIT interest coverage of {ic:.1f}x is critically low (<{t['interest_coverage_critical']}x) — near inability to service debt.",
                metric="ebit_coverage", value=ic,
            ))
        elif ic < t["interest_coverage_low"]:
            flags.append(CreditFlag(
                severity="WARNING", category="COVERAGE",
                message=f"EBIT interest coverage of {ic:.1f}x is below comfort threshold ({t['interest_coverage_low']}x).",
                metric="ebit_coverage", value=ic,
            ))

    # Declining coverage trend (lower is worse → check if rising, i.e., recovery missing)
    ic_series = series("ebit_coverage")
    valid_ic = [v for v in ic_series if not math.isnan(v)]
    if len(valid_ic) >= 3:
        # Deterioration: coverage falling = values decreasing over time
        recent = valid_ic[:t["trend_years"] + 1]
        if all(recent[i] < recent[i + 1] for i in range(len(recent) - 1)):
            flags.append(CreditFlag(
                severity="WARNING", category="COVERAGE",
                message=f"Interest coverage declining for {t['trend_years']}+ consecutive years — deteriorating debt service capacity.",
                metric="ebit_coverage_trend", value=valid_ic[0],
            ))

    # ── LIQUIDITY FLAGS ──────────────────────────────────────────────────────

    cr = get("current_ratio")
    if not math.isnan(cr) and cr < t["current_ratio_low"]:
        flags.append(CreditFlag(
            severity="WARNING", category="LIQUIDITY",
            message=f"Current ratio of {cr:.2f}x below 1.0x — short-term obligations exceed current assets.",
            metric="current_ratio", value=cr,
        ))

    qr = get("quick_ratio")
    if not math.isnan(qr) and qr < t["quick_ratio_low"]:
        flags.append(CreditFlag(
            severity="WARNING", category="LIQUIDITY",
            message=f"Quick ratio of {qr:.2f}x below {t['quick_ratio_low']}x — tight near-term liquidity.",
            metric="quick_ratio", value=qr,
        ))

    # ── Z-SCORE FLAGS ────────────────────────────────────────────────────────

    z = get("z_score")
    if not math.isnan(z):
        if z < t["z_score_distress"]:
            flags.append(CreditFlag(
                severity="CRITICAL", category="Z-SCORE",
                message=f"Altman Z-Score of {z:.2f} is in DISTRESS zone (<{t['z_score_distress']}) — elevated bankruptcy probability.",
                metric="z_score", value=z,
            ))
        elif z < t["z_score_grey"]:
            flags.append(CreditFlag(
                severity="WARNING", category="Z-SCORE",
                message=f"Altman Z-Score of {z:.2f} is in GREY ZONE ({t['z_score_distress']}–{t['z_score_grey']}) — monitor closely.",
                metric="z_score", value=z,
            ))

    # ── NEGATIVE FCF ──────────────────────────────────────────────────────────

    fcf = get("fcf")
    if not math.isnan(fcf) and fcf < 0:
        flags.append(CreditFlag(
            severity="WARNING", category="CASHFLOW",
            message=f"Negative free cash flow (${fcf/1e9:.1f}B) — company is cash-consumptive; reliant on debt/equity financing.",
            metric="fcf", value=fcf,
        ))

    # Sort: CRITICAL → WARNING → INFO
    severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    flags.sort(key=lambda f: severity_order.get(f.severity, 9))

    logger.info("[%s] Generated %d credit flag(s).", company_name, len(flags))
    return flags


def overall_risk_rating(flags: list[CreditFlag], z_score: float) -> str:
    """
    Derive a simple overall credit risk rating:
      HIGH / ELEVATED / MODERATE / LOW
    """
    critical_count = sum(1 for f in flags if f.severity == "CRITICAL")
    warning_count  = sum(1 for f in flags if f.severity == "WARNING")

    if critical_count >= 2 or (not math.isnan(z_score) and z_score < 1.81):
        return "HIGH"
    if critical_count >= 1 or warning_count >= 3:
        return "ELEVATED"
    if warning_count >= 1:
        return "MODERATE"
    return "LOW"
