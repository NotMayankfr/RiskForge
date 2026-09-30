"""
stress_engine.py
Scenario stress-test engine. ILLUSTRATIVE ONLY.
"""

from __future__ import annotations
import math

def _safe_div(n: float, d: float) -> float:
    if d == 0 or math.isnan(d) or math.isnan(n):
        return math.nan
    return n / d

def run_stress_scenarios(latest_ratios: dict, raw_data: dict, scenarios: dict) -> dict:
    results = {}
    
    # Get base values from latest ratios
    base_rev = latest_ratios.get("revenue", math.nan)
    base_ebitda = latest_ratios.get("ebitda", math.nan)
    base_ebit = latest_ratios.get("ebit", math.nan)
    base_debt = latest_ratios.get("total_debt", math.nan)
    base_net_debt = latest_ratios.get("net_debt", math.nan)
    base_interest = latest_ratios.get("interest_expense", math.nan)
    
    depreciation = base_ebitda - base_ebit if not (math.isnan(base_ebitda) or math.isnan(base_ebit)) else 0.0
    
    # Approx CFO/Rev ratio
    cfo = latest_ratios.get("cfo", math.nan)  # Assuming we add this later, or we can just fall back
    if math.isnan(cfo) and "cashflow" in raw_data:
        # try to get from raw_data
        pass

    for name, params in scenarios.items():
        rev_change = params.get("revenue_change_pct", 0.0)
        margin_change = params.get("margin_change_ppt", 0.0)
        rate_shock = params.get("interest_rate_shock", 0.0)
        
        s_rev = base_rev * (1 + rev_change)
        
        base_margin = (base_ebitda / base_rev * 100) if base_rev else 0.0
        s_margin = max(0.0, base_margin + margin_change)
        
        s_ebitda = s_rev * (s_margin / 100.0)
        s_ebit = s_ebitda - depreciation
        
        s_int = base_interest * (1 + rate_shock)
        
        s_de = _safe_div(base_debt, s_ebitda) if s_ebitda > 0 else math.nan
        s_nde = _safe_div(base_net_debt, s_ebitda) if s_ebitda > 0 else math.nan
        s_ebit_cov = _safe_div(s_ebit, s_int)
        s_ebitda_cov = _safe_div(s_ebitda, s_int)
        
        results[name] = {
            "label": params.get("label", name),
            "stressed_revenue": s_rev,
            "stressed_ebitda_margin": s_margin,
            "stressed_ebitda": s_ebitda,
            "stressed_ebit": s_ebit,
            "stressed_interest_expense": s_int,
            "stressed_debt_ebitda": s_de,
            "stressed_net_debt_ebitda": s_nde,
            "stressed_ebit_coverage": s_ebit_cov,
            "stressed_ebitda_coverage": s_ebitda_cov,
            "delta_vs_base_debt_ebitda": s_de - latest_ratios.get("debt_ebitda", math.nan),
            "delta_vs_base_ebit_coverage": s_ebit_cov - latest_ratios.get("ebit_coverage", math.nan),
            "assumptions_used": params.copy()
        }
        
    return results
