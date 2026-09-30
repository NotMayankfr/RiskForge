"""
credit_framework.py
Structured credit assessment framework synthesizing all modules.
"""

from __future__ import annotations
import math

def build_credit_assessment(
    company: dict,
    period_ratios: dict,
    flags: list,
    debt_capacity: dict,
    stress_results: dict,
    refinancing: dict,
    covenants: dict,
    cashflow: dict,
    sector_info: dict
) -> dict:
    
    ordered = list(period_ratios.keys())
    ttm = period_ratios.get(ordered[0], {}) if ordered else {}
    
    # Analyze strengths
    strengths = []
    if ttm.get("ebit_coverage", 0) > 8: strengths.append(f"Very strong EBIT interest coverage ({ttm['ebit_coverage']:.1f}x)")
    elif ttm.get("ebit_coverage", 0) > 4: strengths.append(f"Solid EBIT interest coverage ({ttm['ebit_coverage']:.1f}x)")
    
    if ttm.get("net_debt_ebitda", 99) < 1.5: strengths.append(f"Conservative net leverage ({ttm['net_debt_ebitda']:.1f}x)")
    
    if ttm.get("fcf", 0) > 0 and ttm.get("fcf_margin", 0) > 5: strengths.append(f"Positive free cash flow generation ({ttm['fcf_margin']:.1f}% margin)")
    
    if sector_info.get("revenue_visibility") == "HIGH": strengths.append("High revenue visibility backed by government contracts")
        
    # Analyze weaknesses
    weaknesses = []
    if ttm.get("ebit_coverage", 99) < 3: weaknesses.append(f"Weak interest coverage ({ttm['ebit_coverage']:.1f}x)")
    if ttm.get("net_debt_ebitda", 0) > 4: weaknesses.append(f"Elevated net leverage ({ttm['net_debt_ebitda']:.1f}x)")
    if ttm.get("fcf", 0) < 0: weaknesses.append("Negative free cash flow")
    if ttm.get("current_ratio", 99) < 1.0: weaknesses.append(f"Tight liquidity with current ratio {ttm['current_ratio']:.2f}x")
    
    # Flags mapping
    warning_count = sum(1 for f in flags if f.severity == "WARNING")
    crit_count = sum(1 for f in flags if f.severity == "CRITICAL")
    
    # Overall view (simple heuristic based on flags and leverage)
    if crit_count > 0 or ttm.get("net_debt_ebitda", 0) > 4.5 or ttm.get("ebit_coverage", 99) < 2.0:
        view = "HIGH YIELD PROFILE (Elevated Risk)"
    elif warning_count > 2 or ttm.get("net_debt_ebitda", 0) > 3.0:
        view = "CROSSOVER PROFILE (Moderate Risk)"
    else:
        view = "INVESTMENT GRADE PROFILE (Low Risk)"
        
    return {
        "financial_strengths": {"items": strengths, "summary": f"{len(strengths)} key strengths identified"},
        "financial_weaknesses": {"items": weaknesses, "summary": f"{len(weaknesses)} key weaknesses identified"},
        "overall_credit_view": view,
        "monitoring_items": [
            "Monitor quarterly cash flow generation",
            "Track defense budget appropriations in primary market",
            "Monitor leverage trend against illustrative covenant caps"
        ]
    }
