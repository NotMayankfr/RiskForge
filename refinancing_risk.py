"""
refinancing_risk.py
Refinancing risk assessment module.
"""

from __future__ import annotations
import math
from config import REFINANCING_THRESHOLDS

def assess_refinancing_risk(latest_ratios: dict) -> dict:
    factors = []
    
    nde = latest_ratios.get("net_debt_ebitda", math.nan)
    if not math.isnan(nde):
        if nde > REFINANCING_THRESHOLDS["leverage_elevated"]:
            factors.append({"name": "Leverage", "status": "ELEVATED", "reason": f"Net leverage {nde:.1f}x > {REFINANCING_THRESHOLDS['leverage_elevated']}x"})
        elif nde > REFINANCING_THRESHOLDS["leverage_moderate"]:
            factors.append({"name": "Leverage", "status": "MODERATE", "reason": f"Net leverage {nde:.1f}x > {REFINANCING_THRESHOLDS['leverage_moderate']}x"})
        else:
            factors.append({"name": "Leverage", "status": "LOW", "reason": f"Net leverage {nde:.1f}x is low"})
            
    fcf = latest_ratios.get("fcf", math.nan)
    debt = latest_ratios.get("total_debt", math.nan)
    if not math.isnan(fcf) and not math.isnan(debt):
        if fcf <= 0:
            factors.append({"name": "Debt/FCF", "status": "ELEVATED", "reason": "Negative FCF - elevated risk"})
        else:
            dfcf = debt / fcf
            if dfcf > REFINANCING_THRESHOLDS["debt_fcf_elevated"]:
                factors.append({"name": "Debt/FCF", "status": "ELEVATED", "reason": f"Debt/FCF {dfcf:.1f}x > {REFINANCING_THRESHOLDS['debt_fcf_elevated']}x"})
            elif dfcf > REFINANCING_THRESHOLDS["debt_fcf_moderate"]:
                factors.append({"name": "Debt/FCF", "status": "MODERATE", "reason": f"Debt/FCF {dfcf:.1f}x > {REFINANCING_THRESHOLDS['debt_fcf_moderate']}x"})
            else:
                factors.append({"name": "Debt/FCF", "status": "LOW", "reason": f"Strong FCF coverage of debt ({dfcf:.1f}x)"})
                
    int_exp = latest_ratios.get("interest_expense", math.nan)
    ebitda = latest_ratios.get("ebitda", math.nan)
    if ebitda > 0 and not math.isnan(int_exp):
        burden = int_exp / ebitda
        if burden > REFINANCING_THRESHOLDS["interest_burden_high"]:
            factors.append({"name": "Interest Burden", "status": "ELEVATED", "reason": f"Interest consumes {burden*100:.1f}% of EBITDA"})
        elif burden > REFINANCING_THRESHOLDS["interest_burden_moderate"]:
            factors.append({"name": "Interest Burden", "status": "MODERATE", "reason": f"Interest consumes {burden*100:.1f}% of EBITDA"})
        else:
            factors.append({"name": "Interest Burden", "status": "LOW", "reason": f"Low interest burden ({burden*100:.1f}%)"})
            
    cash = latest_ratios.get("cash", math.nan)
    if debt > 0 and not math.isnan(cash):
        cover = cash / debt
        if cover < REFINANCING_THRESHOLDS["cash_cover_low"]:
            factors.append({"name": "Cash Coverage", "status": "ELEVATED", "reason": f"Cash covers only {cover*100:.1f}% of debt"})
        elif cover < REFINANCING_THRESHOLDS["cash_cover_moderate"]:
            factors.append({"name": "Cash Coverage", "status": "MODERATE", "reason": f"Cash covers {cover*100:.1f}% of debt"})
        else:
            factors.append({"name": "Cash Coverage", "status": "LOW", "reason": f"Strong cash coverage ({cover*100:.1f}%)"})

    n_elevated = sum(1 for f in factors if f["status"] == "ELEVATED")
    n_moderate = sum(1 for f in factors if f["status"] == "MODERATE")
    
    if n_elevated >= 2:
        cls = "ELEVATED"
    elif n_elevated == 1 or n_moderate >= 2:
        cls = "MODERATE"
    else:
        cls = "LOW"
        
    return {
        "classification": cls,
        "factors": factors,
        "maturity_note": "Debt maturity schedule not available from yfinance; point-in-time refinancing risk assessed from leverage, coverage, and cash metrics only.",
        "overall_reason": f"Overall {cls} risk driven by {n_elevated} elevated and {n_moderate} moderate factors."
    }
