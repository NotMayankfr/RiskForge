"""
intelligence_report.py
Formats trend analysis into institutional-grade credit intelligence reports.

Produces:
1. A structured markdown report (clean institutional typography, no emojis)
2. An optional AI-enhanced narrative prompt using Gemini
"""

from __future__ import annotations

import logging
from trend_detector import IntelligenceReport, METRIC_CONCERN_DIRECTION

logger = logging.getLogger(__name__)


def _fmt_val(metric: str, value: float | None) -> str:
    """Format a metric value for display."""
    if value is None:
        return "N/A"

    ratio_metrics = {
        "debt_ebitda", "net_debt_ebitda", "debt_equity", "debt_assets",
        "ebit_coverage", "ebitda_coverage",
        "current_ratio", "quick_ratio", "cash_ratio",
    }
    if metric in ratio_metrics:
        return f"{value:.2f}x"

    pct_metrics = {"ebitda_margin", "net_margin", "fcf_margin", "roce"}
    if metric in pct_metrics:
        return f"{value:.1f}%"

    if metric == "z_score":
        return f"{value:.2f}"

    if abs(value) >= 1e9:
        return f"${value/1e9:.2f}B"
    if abs(value) >= 1e6:
        return f"${value/1e6:.1f}M"

    return f"{value:.2f}"


def format_intelligence_report(report: IntelligenceReport) -> str:
    """
    Generate a structured markdown intelligence report from trend analysis.
    Clean institutional style without decorative emojis.
    """
    lines: list[str] = []

    lines.append(f"### Executive Trend Synthesis — {report.ticker}")
    lines.append(
        f"**Issuer:** {report.company_name} &nbsp;|&nbsp; "
        f"**Horizon:** {report.period_range} ({report.total_periods} annual periods) &nbsp;|&nbsp; "
        f"**Trajectory:** `{report.overall_trajectory}`"
    )
    lines.append("")
    lines.append(f"{report.summary}")
    lines.append("")

    if report.deteriorating:
        lines.append("#### Deteriorating Credit Metrics & Fundamental Drivers")
        lines.append("")
        lines.append("| Metric | Signal | Streak | Earliest | Latest | Total Change | Underlying Drivers |")
        lines.append("| :--- | :--- | :--- | ---: | ---: | ---: | :--- |")

        for alert in report.deteriorating:
            streak = f"{alert.consecutive_periods}Y consecutive" if alert.consecutive_periods > 0 else "Net multi-year"
            earliest_str = _fmt_val(alert.metric, alert.earliest_value)
            latest_str = _fmt_val(alert.metric, alert.latest_value)
            pct_str = f"{alert.total_change_pct:+.1f}%" if alert.total_change_pct is not None else "N/A"
            drivers_str = "; ".join(alert.drivers) if alert.drivers else "Ratio shift driven by combined numerator/denominator drift"
            lines.append(
                f"| **{alert.display_name}** | `{alert.severity}` | {streak} | "
                f"{earliest_str} | {latest_str} | {pct_str} | {drivers_str} |"
            )
        lines.append("")

    if report.improving:
        lines.append("#### Improving Credit Metrics")
        lines.append("")
        lines.append("| Metric | Periods Improved | Earliest | Latest | Total Change |")
        lines.append("| :--- | :--- | ---: | ---: | ---: |")
        for alert in report.improving:
            earliest_str = _fmt_val(alert.metric, alert.earliest_value)
            latest_str = _fmt_val(alert.metric, alert.latest_value)
            pct_str = f"{alert.total_change_pct:+.1f}%" if alert.total_change_pct is not None else "N/A"
            lines.append(
                f"| **{alert.display_name}** | {alert.consecutive_periods} periods | "
                f"{earliest_str} | {latest_str} | {pct_str} |"
            )
        lines.append("")

    if report.stable:
        lines.append(
            f"**Stable Metrics (<5% variance):** {', '.join(report.stable)}"
        )
        lines.append("")

    return "\n".join(lines)


def build_ai_intelligence_prompt(
    report: IntelligenceReport,
    existing_risk_rating: str,
) -> str:
    """
    Build a Gemini prompt that asks the AI to produce an enhanced
    intelligence narrative, incorporating the trend analysis results
    into the existing credit assessment.
    """
    det_summary = ""
    for a in report.deteriorating:
        det_summary += f"- [{a.severity}] {a.display_name}: {a.message}\n"
        if a.drivers:
            for d in a.drivers:
                det_summary += f"  Driver: {d}\n"

    imp_summary = ""
    for a in report.improving:
        imp_summary += f"- {a.display_name}: {a.message}\n"

    prompt = f"""You are a senior institutional credit analyst.

TASK: Write a concise 3-paragraph intelligence briefing about {report.company_name} ({report.ticker}) based STRICTLY on the trend analysis data provided below. Do not invent facts.

CURRENT POINT-IN-TIME RISK RATING: {existing_risk_rating}
TREND-ADJUSTED RISK RATING: {report.updated_risk_rating} ({report.risk_action})
OVERALL TRAJECTORY: {report.overall_trajectory}
PERIOD: {report.period_range} ({report.total_periods} annual periods)

DETERIORATING METRICS:
{det_summary if det_summary else "None detected."}

IMPROVING METRICS:
{imp_summary if imp_summary else "None detected."}

STABLE METRICS: {', '.join(report.stable) if report.stable else 'None'}

INSTRUCTIONS:
1. Paragraph 1: Summarize the overall financial trajectory and explain why the baseline risk rating of {existing_risk_rating} is {report.risk_action} to {report.updated_risk_rating}. Justify with specific metrics.
2. Paragraph 2: Focus on the most concerning deteriorating trends (if any). Explain the underlying drivers and their implications for creditworthiness.
3. Paragraph 3: Note any positive or stabilizing trends that offset concerns, and recommend specific monitoring actions.

Keep the tone professional, analytical, and evidence-based. Do not use bullet points or emojis. Maximum 300 words.
"""
    return prompt
