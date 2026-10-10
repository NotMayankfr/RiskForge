"""
intelligence_report.py
Formats trend analysis into human-readable intelligence reports.

Produces two outputs:
1. A structured markdown report (always available, no AI needed)
2. An optional AI-enhanced narrative using Gemini (when configured)
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
        return f"${value/1e9:.1f}B"
    if abs(value) >= 1e6:
        return f"${value/1e6:.0f}M"

    return f"{value:.2f}"


def format_intelligence_report(report: IntelligenceReport) -> str:
    """
    Generate a structured markdown intelligence report from trend analysis.
    """
    lines: list[str] = []

    lines.append(f"## 📊 Financial Intelligence Report — {report.ticker}")
    lines.append(f"**Company:** {report.company_name}")
    lines.append(
        f"**Analysis Period:** {report.period_range} "
        f"({report.total_periods} reporting periods)"
    )
    lines.append("")

    # Risk Assessment Update Banner
    lines.append("### 🛡️ Dynamic Risk Assessment Update")
    lines.append(
        f"- **Baseline Point-in-Time Risk:** `{report.baseline_risk_rating}`\n"
        f"- **Trend-Adjusted Risk Assessment:** `{report.updated_risk_rating}` ({report.risk_action})\n"
        f"- **Assessment Rationale:** {report.risk_update_rationale}"
    )
    lines.append("")

    trajectory_emoji = {
        "DETERIORATING": "🔴",
        "MIXED": "🟡",
        "STABLE": "🟢",
        "IMPROVING": "🟢",
    }
    emoji = trajectory_emoji.get(report.overall_trajectory, "⚪")
    lines.append(f"### Overall Financial Trajectory: {emoji} {report.overall_trajectory}")
    lines.append("")
    lines.append(f"*{report.summary}*")
    lines.append("")

    # Deteriorating metrics
    if report.deteriorating:
        lines.append("---")
        lines.append("### ⚠️ Deteriorating Metrics & Underlying Drivers")
        lines.append("")

        for alert in report.deteriorating:
            severity_icon = {
                "WARNING": "🔴",
                "CAUTION": "🟠",
                "WATCH": "🟡",
            }.get(alert.severity, "⚪")

            lines.append(
                f"**{severity_icon} [{alert.severity}] {alert.display_name}**"
            )
            lines.append(f"> {alert.message}")
            lines.append("")

            if alert.changes:
                lines.append("| Period | Value | Change | Direction |")
                lines.append("|--------|-------|--------|-----------|")

                first = alert.changes[0]
                if first.from_value is not None:
                    lines.append(
                        f"| {first.from_year} | {_fmt_val(first.metric, first.from_value)} | — | — |"
                    )

                for c in alert.changes:
                    if c.to_value is not None:
                        pct_str = f"{c.pct_change:+.1f}%" if c.pct_change is not None else "N/A"
                        dir_emoji = (
                            "📈" if c.direction == "deteriorated" and METRIC_CONCERN_DIRECTION.get(c.metric) == "rising"
                            else "📉" if c.direction == "deteriorated"
                            else "✅" if c.direction == "improved"
                            else "➡️"
                        )
                        lines.append(
                            f"| {c.to_year} | {_fmt_val(c.metric, c.to_value)} | {pct_str} | {dir_emoji} {c.direction.capitalize()} |"
                        )

                lines.append("")

            if alert.drivers:
                lines.append("**Identified Drivers:**")
                for d in alert.drivers:
                    lines.append(f"- {d}")
                lines.append("")

    # Improving metrics
    if report.improving:
        lines.append("---")
        lines.append("### ✅ Improving Metrics")
        lines.append("")

        for alert in report.improving:
            lines.append(f"**🟢 {alert.display_name}** — {alert.message}")

            if alert.earliest_value is not None and alert.latest_value is not None:
                lines.append(
                    f"> Moved from {_fmt_val(alert.metric, alert.earliest_value)} "
                    f"to {_fmt_val(alert.metric, alert.latest_value)}"
                )
                if alert.total_change_pct is not None:
                    lines.append(f"> Total change: {alert.total_change_pct:+.1f}%")
            lines.append("")

    # Stable metrics
    if report.stable:
        lines.append("---")
        lines.append("### ➡️ Stable Metrics")
        lines.append(
            f"The following metrics showed no material change: "
            f"{', '.join(report.stable)}"
        )
        lines.append("")

    lines.append("---")
    lines.append(
        "*Analysis powered by SQL-based historical data store (`ratio_snapshots`). "
        "All metrics computed from yfinance annual financial statements.*"
    )

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

    prompt = f"""You are a senior credit analyst at a major financial institution.

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

Keep the tone professional, analytical, and evidence-based. Do not use bullet points. Maximum 300 words.
"""
    return prompt
