"""
covenant_monitor.py
Illustrative covenant monitoring module.
"""

from __future__ import annotations
import math

def analyze_covenants(period_ratios: dict, thresholds: dict) -> dict:
    if not period_ratios:
        return {}
        
    ordered = list(period_ratios.keys())
    latest = period_ratios[ordered[0]]
    
    covs = [
        ("max_net_debt_ebitda", "Net Debt / EBITDA", latest.get("net_debt_ebitda", math.nan), True),
        ("max_debt_ebitda", "Total Debt / EBITDA", latest.get("debt_ebitda", math.nan), True),
        ("min_interest_coverage", "EBIT Interest Coverage", latest.get("ebit_coverage", math.nan), False),
        ("min_current_ratio", "Current Ratio", latest.get("current_ratio", math.nan), False)
    ]
    
    covenants_list = []
    breaches = 0
    tight = 0
    ok = 0
    
    for key, name, val, is_max in covs:
        thr = thresholds.get(key, math.nan)
        if math.isnan(thr) or math.isnan(val):
            continue
            
        headroom = (thr - val) if is_max else (val - thr)
        headroom_pct = headroom / thr if thr > 0 else 0
        breach = headroom < 0
        
        status = "BREACH" if breach else "TIGHT" if headroom_pct < 0.1 else "OK"
        if status == "BREACH": breaches += 1
        elif status == "TIGHT": tight += 1
        else: ok += 1
        
        covenants_list.append({
            "metric": name,
            "current_value": val,
            "threshold": thr,
            "headroom": headroom,
            "headroom_pct": headroom_pct,
            "breach": breach,
            "status": status
        })
        
    return {
        "label": "Illustrative Covenant Analysis",
        "disclaimer": "These thresholds are illustrative analytical parameters only and do not represent actual legal covenants.",
        "covenants": covenants_list,
        "summary": {"total": len(covenants_list), "breaches": breaches, "tight": tight, "ok": ok},
        "thresholds_used": thresholds.copy()
    }
