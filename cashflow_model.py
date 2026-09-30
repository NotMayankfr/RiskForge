"""
cashflow_model.py
Cash flow analysis and simple forward projection module.
"""

from __future__ import annotations
import math

def model_cashflows(raw_data: dict, periods: list[str], assumptions: dict) -> dict:
    historical = []
    
    inc = raw_data.get("income", {})
    cf = raw_data.get("cashflow", {})
    bal = raw_data.get("balance", {})
    
    for p in periods:
        revenue = inc.get(p, {}).get("Total Revenue", math.nan)
        ebitda = inc.get(p, {}).get("EBITDA", math.nan)
        
        cfo = cf.get(p, {}).get("Operating Cash Flow", math.nan)
        capex = abs(cf.get(p, {}).get("Capital Expenditure", 0.0))
        fcf = cf.get(p, {}).get("Free Cash Flow", cfo - capex)
        
        debt = bal.get(p, {}).get("Total Debt", math.nan)
        
        hist_entry = {
            "period": p,
            "cfo": cfo,
            "capex": capex,
            "fcf": fcf,
            "revenue": revenue,
            "ebitda": ebitda,
            "cfo_margin": cfo / revenue * 100 if revenue > 0 else math.nan,
            "fcf_margin": fcf / revenue * 100 if revenue > 0 else math.nan,
            "fcf_conversion": fcf / ebitda * 100 if ebitda > 0 else math.nan,
            "debt_paydown_capacity": (fcf / debt * 100) if debt > 0 and fcf > 0 else math.nan,
            "debt_to_fcf": (debt / fcf) if fcf > 0 else math.nan
        }
        historical.append(hist_entry)
        
    projections = []
    if historical:
        latest = historical[0]
        base_rev = latest["revenue"]
        
        g = assumptions.get("revenue_growth_pct", 0.0)
        ebitda_m = assumptions.get("ebitda_margin_pct")
        if ebitda_m is None and latest["revenue"] > 0:
            ebitda_m = latest["ebitda"] / latest["revenue"]
        elif ebitda_m is None:
            ebitda_m = 0.15 # fallback
            
        capex_m = assumptions.get("capex_pct_revenue")
        if capex_m is None and latest["revenue"] > 0:
            capex_m = latest["capex"] / latest["revenue"]
        elif capex_m is None:
            capex_m = 0.05 # fallback
            
        proj_rev = base_rev
        for y in range(1, assumptions.get("projection_years", 3) + 1):
            if not math.isnan(proj_rev):
                proj_rev = proj_rev * (1 + g)
                p_ebitda = proj_rev * ebitda_m
                p_capex = proj_rev * capex_m
                p_fcf = p_ebitda - p_capex # simplified
            else:
                p_ebitda = p_capex = p_fcf = math.nan
                
            projections.append({
                "year": f"Year {y}",
                "projected_revenue": proj_rev,
                "projected_ebitda": p_ebitda,
                "projected_capex": p_capex,
                "projected_fcf": p_fcf,
                "assumptions_used": {"growth": g, "ebitda_margin": ebitda_m, "capex_margin": capex_m}
            })
            
    return {
        "historical": historical,
        "projection": projections,
        "projection_disclaimer": "Forward projections are illustrative model outputs based on user-defined assumptions. They are not forecasts."
    }
