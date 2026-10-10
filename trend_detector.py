"""
trend_detector.py
Detects deteriorating financial trends from historical ratio snapshots.

Uses the SQL data store (db_manager.py) to identify:
- Metrics worsening period-over-period
- Consecutive deterioration streaks
- Inflection points (metric was improving, now declining)
- Underlying drivers behind each deterioration
- Dynamic updates to the existing credit risk assessment
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import db_manager

logger = logging.getLogger(__name__)


# ── Deterioration direction rules ───────────────────────────────────────────
METRIC_CONCERN_DIRECTION: dict[str, str] = {
    # Leverage — rising is worse
    "debt_ebitda":      "rising",
    "net_debt_ebitda":  "rising",
    "debt_equity":      "rising",
    "debt_assets":      "rising",
    "total_debt":       "rising",
    "interest_expense": "rising",

    # Coverage & profitability — falling is worse
    "ebit_coverage":    "falling",
    "ebitda_coverage":  "falling",
    "current_ratio":    "falling",
    "quick_ratio":      "falling",
    "cash_ratio":       "falling",
    "ebitda_margin":    "falling",
    "net_margin":       "falling",
    "fcf_margin":       "falling",
    "roce":             "falling",
    "z_score":          "falling",
    "revenue":          "falling",
    "ebit":             "falling",
    "ebitda":           "falling",
    "net_income":       "falling",
    "fcf":              "falling",
    "cfo":              "falling",
    "cash":             "falling",
    "total_equity":     "falling",
}

# Metrics where a negative latest value (< 0) indicates distress and must never be labeled "Strengthening"
NEGATIVE_DISTRESS_METRICS = {
    "ebit_coverage",
    "ebitda_coverage",
    "ebitda_margin",
    "net_margin",
    "fcf_margin",
    "roce",
}

# Human-readable display names
METRIC_DISPLAY_NAMES: dict[str, str] = {
    "debt_ebitda":      "Debt / EBITDA",
    "net_debt_ebitda":  "Net Debt / EBITDA",
    "debt_equity":      "Debt / Equity",
    "debt_assets":      "Debt / Assets",
    "ebit_coverage":    "EBIT Interest Coverage",
    "ebitda_coverage":  "EBITDA Interest Coverage",
    "current_ratio":    "Current Ratio",
    "quick_ratio":      "Quick Ratio",
    "cash_ratio":       "Cash Ratio",
    "ebitda_margin":    "EBITDA Margin",
    "net_margin":       "Net Margin",
    "fcf_margin":       "FCF Margin",
    "roce":             "ROCE",
    "z_score":          "Altman Z-Score",
    "revenue":          "Revenue",
    "ebit":             "EBIT",
    "ebitda":           "EBITDA",
    "net_income":       "Net Income",
    "total_debt":       "Total Debt",
    "net_debt":         "Net Debt",
    "interest_expense": "Interest Expense",
    "fcf":              "Free Cash Flow",
    "cfo":              "Operating Cash Flow",
    "cash":             "Cash & Equivalents",
    "total_equity":     "Total Equity",
    "total_assets":     "Total Assets",
}

# Driver mapping: for each ratio, what underlying metrics drive it
RATIO_DRIVERS: dict[str, list[tuple[str, str]]] = {
    "debt_ebitda": [
        ("total_debt", "Total debt changed"),
        ("ebitda", "EBITDA changed"),
    ],
    "net_debt_ebitda": [
        ("net_debt", "Net debt changed"),
        ("ebitda", "EBITDA changed"),
    ],
    "debt_equity": [
        ("total_debt", "Total debt changed"),
        ("total_equity", "Total equity changed"),
    ],
    "ebit_coverage": [
        ("ebit", "EBIT changed"),
        ("interest_expense", "Interest expense changed"),
    ],
    "ebitda_coverage": [
        ("ebitda", "EBITDA changed"),
        ("interest_expense", "Interest expense changed"),
    ],
    "current_ratio": [
        ("cash", "Cash position changed"),
        ("total_debt", "Debt level changed"),
    ],
    "quick_ratio": [
        ("cash", "Cash position changed"),
        ("total_debt", "Debt level changed"),
    ],
    "ebitda_margin": [
        ("ebitda", "EBITDA changed"),
        ("revenue", "Revenue changed"),
    ],
    "net_margin": [
        ("net_income", "Net income changed"),
        ("revenue", "Revenue changed"),
    ],
    "fcf_margin": [
        ("fcf", "Free cash flow changed"),
        ("revenue", "Revenue changed"),
    ],
    "roce": [
        ("ebit", "EBIT changed"),
        ("total_assets", "Total assets changed"),
    ],
    "z_score": [
        ("ebit", "EBIT (profitability) changed"),
        ("total_debt", "Debt (leverage) changed"),
        ("revenue", "Revenue (activity) changed"),
        ("total_equity", "Equity changed"),
    ],
}

RISK_LADDER = ["LOW", "MODERATE", "ELEVATED", "HIGH"]


# ── Data classes ────────────────────────────────────────────────────────────

@dataclass
class PeriodChange:
    """Represents a change in a metric between two consecutive periods."""
    metric: str
    display_name: str
    from_year: int
    to_year: int
    from_value: float | None
    to_value: float | None
    absolute_change: float | None
    pct_change: float | None
    direction: str          # "improved", "deteriorated", "stable", "insufficient_data"


@dataclass
class TrendAlert:
    """A detected deterioration trend for a specific metric."""
    metric: str
    display_name: str
    severity: str           # "WARNING", "CAUTION", "WATCH", "POSITIVE"
    consecutive_periods: int
    latest_value: float | None
    earliest_value: float | None
    total_change_pct: float | None
    changes: list[PeriodChange]
    drivers: list[str]      # Human-readable driver explanations
    message: str            # Summary message


@dataclass
class IntelligenceReport:
    """Complete trend analysis output for a single company."""
    ticker: str
    company_name: str
    total_periods: int
    period_range: str               # e.g. "2021 → 2024"
    deteriorating: list[TrendAlert]
    improving: list[TrendAlert]
    stable: list[str]               # metric names that didn't change materially
    overall_trajectory: str         # "IMPROVING", "STABLE", "DETERIORATING", "MIXED"
    summary: str                    # 2-3 sentence plain-English summary
    baseline_risk_rating: str = "MODERATE"
    updated_risk_rating: str = "MODERATE"
    risk_action: str = "MAINTAINED"  # "ESCALATED", "IMPROVED", "MAINTAINED"
    risk_update_rationale: str = ""


# ── Core analysis engine ────────────────────────────────────────────────────

def _pct_change(old: float | None, new: float | None) -> float | None:
    """Calculate percentage change, handling None and zero denominators."""
    if old is None or new is None:
        return None
    if old == 0:
        return None
    return ((new - old) / abs(old)) * 100


def _classify_change(
    metric: str,
    old_val: float | None,
    new_val: float | None,
    threshold_pct: float = 5.0,
) -> str:
    """
    Classify a period-over-period change as improved, deteriorated, or stable.
    """
    if old_val is None or new_val is None:
        return "insufficient_data"

    pct = _pct_change(old_val, new_val)
    if pct is None:
        return "insufficient_data"

    direction = METRIC_CONCERN_DIRECTION.get(metric, "falling")

    if abs(pct) < threshold_pct:
        return "stable"

    if direction == "rising":
        return "deteriorated" if new_val > old_val else "improved"
    else:
        return "deteriorated" if new_val < old_val else "improved"


def _identify_drivers(
    metric: str,
    history: list[dict],
    from_idx: int,
    to_idx: int,
) -> list[str]:
    """
    For a deteriorating ratio, identify which underlying metrics moved
    to cause the change.
    """
    drivers = []
    driver_defs = RATIO_DRIVERS.get(metric, [])

    if not driver_defs:
        return drivers

    old_row = history[from_idx]
    new_row = history[to_idx]

    for driver_metric, _description in driver_defs:
        old_val = old_row.get(driver_metric)
        new_val = new_row.get(driver_metric)

        if old_val is None or new_val is None:
            continue

        pct = _pct_change(old_val, new_val)
        if pct is None:
            continue

        if abs(pct) > 3.0:
            direction = "increased" if new_val > old_val else "decreased"
            display = METRIC_DISPLAY_NAMES.get(driver_metric, driver_metric)

            if abs(old_val) > 1e9:
                old_fmt = f"${old_val/1e9:.1f}B"
                new_fmt = f"${new_val/1e9:.1f}B"
            elif abs(old_val) > 1e6:
                old_fmt = f"${old_val/1e6:.0f}M"
                new_fmt = f"${new_val/1e6:.0f}M"
            else:
                old_fmt = f"{old_val:.2f}"
                new_fmt = f"{new_val:.2f}"

            drivers.append(
                f"{display} {direction} from {old_fmt} to {new_fmt} "
                f"({pct:+.1f}%)"
            )

    return drivers


def _compute_updated_risk_assessment(
    baseline_risk: str,
    trajectory: str,
    deteriorating: list[TrendAlert],
    improving: list[TrendAlert],
) -> tuple[str, str, str]:
    """
    Update the existing point-in-time risk rating based on multi-period
    SQL trend intelligence.

    Returns (updated_risk_rating, risk_action, risk_update_rationale).
    """
    base = baseline_risk if baseline_risk in RISK_LADDER else "MODERATE"
    idx = RISK_LADDER.index(base)

    warn_alerts = [a for a in deteriorating if a.severity == "WARNING"]
    caution_alerts = [a for a in deteriorating if a.severity == "CAUTION"]

    if trajectory == "DETERIORATING" and len(warn_alerts) >= 2:
        new_idx = min(len(RISK_LADDER) - 1, idx + 1)
        updated = RISK_LADDER[new_idx]
        names = ", ".join(a.display_name for a in warn_alerts[:3])
        if new_idx > idx:
            return (
                updated,
                "ESCALATED",
                f"Risk assessment escalated from {base} to {updated} due to multi-period deterioration in {names}.",
            )
        return (
            updated,
            "MAINTAINED (NEGATIVE WATCH)",
            f"Risk rating remains at {updated} (highest tier) with continued multi-period deterioration in {names}.",
        )

    if trajectory == "DETERIORATING" or (len(warn_alerts) == 1 and len(caution_alerts) >= 2):
        names = ", ".join(a.display_name for a in (warn_alerts + caution_alerts)[:3])
        return (
            base,
            "MAINTAINED (NEGATIVE WATCH)",
            f"Baseline {base} rating placed on Negative Watch due to deteriorating trends in {names}.",
        )

    if trajectory == "IMPROVING" and len(improving) >= 3 and len(warn_alerts) == 0:
        new_idx = max(0, idx - 1)
        updated = RISK_LADDER[new_idx]
        names = ", ".join(a.display_name for a in improving[:3])
        if new_idx < idx:
            return (
                updated,
                "IMPROVED",
                f"Risk assessment improved from {base} to {updated} supported by sustained multi-period strengthening in {names}.",
            )
        return (
            updated,
            "MAINTAINED (POSITIVE OUTLOOK)",
            f"Baseline {base} rating maintained with Positive Outlook supported by strengthening in {names}.",
        )

    return (
        base,
        "MAINTAINED",
        f"Baseline {base} risk assessment maintained; historical metric evolution does not warrant a rating migration.",
    )


def analyze_ticker(
    ticker: str,
    db_path: str = db_manager.DB_PATH,
    materiality_threshold_pct: float = 5.0,
) -> IntelligenceReport | None:
    """
    Run full trend analysis for a single ticker.

    Reads historical snapshots from the SQL database, filters out empty stub
    periods, computes period-over-period changes for all tracked metrics,
    detects deterioration streaks, identifies drivers, and updates the
    existing risk assessment.
    """
    raw_history = db_manager.get_ticker_history(ticker, db_path)

    # Filter out completely empty yfinance stub rows where core financials are all NULL
    history = [
        h for h in raw_history
        if any(h.get(k) is not None for k in ("revenue", "ebitda", "total_assets", "total_debt"))
    ]

    if len(history) < 2:
        logger.warning("[%s] Fewer than 2 valid periods — cannot analyze trends.", ticker)
        return None

    company_name = history[0].get("company_name", ticker)
    baseline_risk = history[-1].get("risk_rating") or "MODERATE"
    years = [h["period_year"] for h in history if h.get("period_year")]
    period_range = f"{min(years)} → {max(years)}" if years else "N/A"

    deteriorating_alerts: list[TrendAlert] = []
    improving_alerts: list[TrendAlert] = []
    stable_metrics: list[str] = []

    KEY_RATIOS = [
        "debt_ebitda", "net_debt_ebitda", "debt_equity",
        "ebit_coverage", "ebitda_coverage",
        "current_ratio", "quick_ratio",
        "ebitda_margin", "net_margin", "fcf_margin",
        "z_score", "roce",
    ]

    for metric in KEY_RATIOS:
        # Only evaluate across periods where this metric actually has non-null data
        valid_entries = [(idx_h, h) for idx_h, h in enumerate(history) if h.get(metric) is not None]
        if len(valid_entries) < 2:
            # Skip metrics that lack at least 2 valid periods (do not misclassify as stable)
            continue

        changes: list[PeriodChange] = []
        for i in range(len(valid_entries) - 1):
            _, old_row = valid_entries[i]
            _, new_row = valid_entries[i + 1]
            old_val = old_row.get(metric)
            new_val = new_row.get(metric)

            classification = _classify_change(
                metric, old_val, new_val, materiality_threshold_pct
            )

            changes.append(PeriodChange(
                metric=metric,
                display_name=METRIC_DISPLAY_NAMES.get(metric, metric),
                from_year=old_row.get("period_year", 0),
                to_year=new_row.get("period_year", 0),
                from_value=old_val,
                to_value=new_val,
                absolute_change=(new_val - old_val) if old_val is not None and new_val is not None else None,
                pct_change=_pct_change(old_val, new_val),
                direction=classification,
            ))

        consecutive_det = 0
        for c in reversed(changes):
            if c.direction == "deteriorated":
                consecutive_det += 1
            else:
                break

        total_det = sum(1 for c in changes if c.direction == "deteriorated")
        total_imp = sum(1 for c in changes if c.direction == "improved")

        display = METRIC_DISPLAY_NAMES.get(metric, metric)
        first_idx, first_row = valid_entries[0]
        last_idx, last_row = valid_entries[-1]
        prev_idx, _ = valid_entries[-2]

        earliest_val = first_row.get(metric)
        latest_val = last_row.get(metric)
        total_pct = _pct_change(earliest_val, latest_val)

        # Guard: if a coverage or profitability metric is negative in the latest period,
        # it is in distress and must never be classified as "Improving" or "Stable".
        is_negative_distress = (
            metric in NEGATIVE_DISTRESS_METRICS
            and latest_val is not None
            and latest_val < 0
        )

        if consecutive_det >= 2:
            severity = "WARNING"
            drivers = _identify_drivers(metric, history, prev_idx, last_idx)
            msg = (
                f"{display} has deteriorated for {consecutive_det} consecutive "
                f"periods ({period_range}). "
            )
            if total_pct is not None:
                msg += f"Total change: {total_pct:+.1f}%. "
            if drivers:
                msg += "Drivers: " + "; ".join(drivers) + "."

            deteriorating_alerts.append(TrendAlert(
                metric=metric,
                display_name=display,
                severity=severity,
                consecutive_periods=consecutive_det,
                latest_value=latest_val,
                earliest_value=earliest_val,
                total_change_pct=total_pct,
                changes=changes,
                drivers=drivers,
                message=msg,
            ))

        elif consecutive_det == 1:
            drivers = _identify_drivers(metric, history, prev_idx, last_idx)
            msg = f"{display} deteriorated in the latest period. "
            if drivers:
                msg += "Driven by: " + "; ".join(drivers) + "."

            deteriorating_alerts.append(TrendAlert(
                metric=metric,
                display_name=display,
                severity="CAUTION",
                consecutive_periods=1,
                latest_value=latest_val,
                earliest_value=earliest_val,
                total_change_pct=total_pct,
                changes=changes,
                drivers=drivers,
                message=msg,
            ))

        elif is_negative_distress:
            drivers = _identify_drivers(metric, history, first_idx, last_idx)
            msg = f"{display} remains negative in the latest period ({latest_val:.2f}), indicating operating/coverage strain."
            deteriorating_alerts.append(TrendAlert(
                metric=metric,
                display_name=display,
                severity="CAUTION",
                consecutive_periods=1,
                latest_value=latest_val,
                earliest_value=earliest_val,
                total_change_pct=total_pct,
                changes=changes,
                drivers=drivers,
                message=msg,
            ))

        elif total_det > 0 and total_det > total_imp:
            drivers = _identify_drivers(metric, history, first_idx, last_idx)
            msg = (
                f"{display} has shown a net deteriorating trend over the "
                f"analysis period ({total_det} deteriorations vs "
                f"{total_imp} improvements)."
            )
            deteriorating_alerts.append(TrendAlert(
                metric=metric,
                display_name=display,
                severity="WATCH",
                consecutive_periods=0,
                latest_value=latest_val,
                earliest_value=earliest_val,
                total_change_pct=total_pct,
                changes=changes,
                drivers=drivers,
                message=msg,
            ))

        elif total_imp > total_det and total_imp >= 2:
            drivers = _identify_drivers(metric, history, first_idx, last_idx)
            msg = f"{display} has been improving over {total_imp} periods."

            improving_alerts.append(TrendAlert(
                metric=metric,
                display_name=display,
                severity="POSITIVE",
                consecutive_periods=total_imp,
                latest_value=latest_val,
                earliest_value=earliest_val,
                total_change_pct=total_pct,
                changes=changes,
                drivers=drivers,
                message=msg,
            ))

        else:
            stable_metrics.append(display)

    severity_order = {"WARNING": 0, "CAUTION": 1, "WATCH": 2}
    deteriorating_alerts.sort(key=lambda a: severity_order.get(a.severity, 99))

    warn_count = sum(1 for a in deteriorating_alerts if a.severity == "WARNING")
    caution_count = sum(1 for a in deteriorating_alerts if a.severity == "CAUTION")
    improving_count = len(improving_alerts)

    if warn_count >= 3 or (warn_count + caution_count >= 4 and improving_count == 0):
        trajectory = "DETERIORATING"
    elif warn_count >= 1 and improving_count <= warn_count:
        trajectory = "DETERIORATING"
    elif improving_count >= 3 and warn_count == 0 and caution_count == 0:
        trajectory = "IMPROVING"
    elif len(deteriorating_alerts) == 0 and improving_count == 0:
        trajectory = "STABLE"
    else:
        trajectory = "MIXED"

    updated_risk, risk_action, risk_rationale = _compute_updated_risk_assessment(
        baseline_risk, trajectory, deteriorating_alerts, improving_alerts
    )

    summary_parts = []
    if trajectory == "DETERIORATING":
        summary_parts.append(
            f"{company_name}'s financial health is deteriorating. "
            f"{len(deteriorating_alerts)} key metrics show negative trends or operating strain."
        )
    elif trajectory == "IMPROVING":
        summary_parts.append(
            f"{company_name}'s financial position is strengthening. "
            f"{improving_count} key metrics are trending positively."
        )
    elif trajectory == "MIXED":
        summary_parts.append(
            f"{company_name} shows a mixed financial trajectory. "
            f"{len(deteriorating_alerts)} metrics are under pressure while "
            f"{improving_count} are improving."
        )
    else:
        summary_parts.append(
            f"{company_name}'s financial metrics are broadly stable "
            f"across the analysis period."
        )

    if deteriorating_alerts:
        worst = deteriorating_alerts[0]
        summary_parts.append(
            f"Primary concern: {worst.display_name} ({worst.severity})."
        )

    summary_parts.append(risk_rationale)

    return IntelligenceReport(
        ticker=ticker,
        company_name=company_name,
        total_periods=len(history),
        period_range=period_range,
        deteriorating=deteriorating_alerts,
        improving=improving_alerts,
        stable=stable_metrics,
        overall_trajectory=trajectory,
        summary=" ".join(summary_parts),
        baseline_risk_rating=baseline_risk,
        updated_risk_rating=updated_risk,
        risk_action=risk_action,
        risk_update_rationale=risk_rationale,
    )
