"""
ratio_engine.py
Computes core financial ratios from raw yfinance data.
"""

from __future__ import annotations
import math
from typing import Any
import pandas as pd
from config import THRESHOLDS

FCC_NOTE = "Simplified proxy: EBIT / Interest Expense. True Fixed Charge Coverage would include lease payments, preferred dividends, and principal repayments, which are not reliably available from yfinance."
Z_SCORE_METHODOLOGY = "Altman (1968) original 5-factor model. X4 uses book equity as proxy for market capitalization where market data is unavailable. This proxy reduces reliability; treat Z-scores for non-US/non-manufacturing firms with caution."

def _div(num: float, den: float) -> float:
    if math.isnan(num) or math.isnan(den) or den == 0.0:
        return math.nan
    return num / den

def _safe_ratio(numerator: float, denominator: float, metric_name: str, ebitda: float = math.nan, net_debt: float = math.nan, data_quality_notes: list = None) -> float:
    if math.isnan(numerator) or math.isnan(denominator) or denominator == 0.0:
        return math.nan
    if not math.isnan(ebitda) and ebitda < 0 and "ebitda" in metric_name.lower():
        if data_quality_notes is not None:
            data_quality_notes.append(f"Negative EBITDA makes {metric_name} meaningless.")
        return math.nan
    if not math.isnan(net_debt) and net_debt < 0 and "net_debt" in metric_name.lower():
        return numerator / denominator  # Return negative leverage, but it's handled safely
    return numerator / denominator

def _altman_z(wc: float, re: float, ebit: float, eq: float, tl: float, rev: float, ta: float) -> float:
    if math.isnan(ta) or ta <= 0: return math.nan
    x1 = wc / ta
    x2 = re / ta
    x3 = ebit / ta
    x4 = eq / tl if (not math.isnan(tl) and tl > 0) else 0.0
    x5 = rev / ta
    return 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

def _get_val(data: dict, key: str, idx: int, default: float = math.nan) -> float:
    if key not in data:
        return default
    series = data[key]
    if idx < len(series):
        val = float(series.iloc[idx])
        if pd.isna(val): return default
        return val
    return default

def compute_period_ratios(income: dict, balance: dict, cashflow: dict, idx: int, period_label: str) -> dict:
    notes = []

    # Income
    revenue = _get_val(income, "revenue", idx)
    ebit = _get_val(income, "ebit", idx)
    net_income = _get_val(income, "net_income", idx)
    
    interest_raw = _get_val(income, "interest_expense", idx)
    interest = abs(interest_raw) if not math.isnan(interest_raw) else math.nan

    # EBITDA fallback logic
    ebitda = _get_val(income, "ebitda", idx)
    ebitda_is_estimated = False
    if math.isnan(ebitda):
        da = _get_val(income, "depreciation", idx, _get_val(cashflow, "depreciation", idx))
        if not math.isnan(ebit) and not math.isnan(da):
            ebitda = ebit + da
        elif not math.isnan(revenue) and revenue > 0:
            ebitda = revenue * 0.10
            ebitda_is_estimated = True
            notes.append("EBITDA estimated as 10% of Revenue.")
            
    negative_ebitda = (ebitda < 0) if not math.isnan(ebitda) else False
    if not math.isnan(interest) and not math.isnan(ebitda) and interest > abs(ebitda) * 2:
        notes.append(f"Interest expense ({interest}) seems abnormally large compared to EBITDA.")

    # Balance Sheet
    total_debt = _get_val(balance, "total_debt", idx)
    cash = _get_val(balance, "cash", idx)
    if math.isnan(total_debt):
        ltd = _get_val(balance, "long_term_debt", idx, 0.0)
        std = _get_val(balance, "short_term_debt", idx, 0.0)
        total_debt = ltd + std
        if total_debt == 0.0: total_debt = math.nan
        
    net_debt = total_debt - cash if (not math.isnan(total_debt) and not math.isnan(cash)) else math.nan
    net_cash_position = (net_debt < 0) if not math.isnan(net_debt) else False

    total_assets = _get_val(balance, "total_assets", idx)
    total_liabilities = _get_val(balance, "total_liabilities", idx, _get_val(balance, "total_debt", idx))
    total_equity = _get_val(balance, "total_equity", idx)
    cur_assets = _get_val(balance, "current_assets", idx)
    cur_liab = _get_val(balance, "current_liabilities", idx)
    inventory = _get_val(balance, "inventory", idx, 0.0)
    working_capital = _get_val(balance, "working_capital", idx, cur_assets - cur_liab)
    ret_earnings = _get_val(balance, "retained_earnings", idx)

    # Cashflow
    cfo = _get_val(cashflow, "cfo", idx)
    capex = abs(_get_val(cashflow, "capex", idx, 0.0))
    fcf = _get_val(cashflow, "fcf", idx, cfo - capex if not math.isnan(cfo) else math.nan)

    # Ratios
    debt_ebitda = _safe_ratio(total_debt, ebitda, "debt_ebitda", ebitda, net_debt, notes)
    net_debt_ebitda = _safe_ratio(net_debt, ebitda, "net_debt_ebitda", ebitda, net_debt, notes)
    debt_equity = _div(total_debt, total_equity)
    debt_assets = _div(total_debt, total_assets)

    ebit_coverage = _div(ebit, interest)
    ebitda_coverage = _div(ebitda, interest)
    fcc_proxy = ebit_coverage

    current_ratio = _div(cur_assets, cur_liab)
    quick_ratio = _div(cur_assets - inventory, cur_liab)
    cash_ratio = _div(cash, cur_liab)

    ebitda_margin = _div(ebitda, revenue) * 100
    net_margin = _div(net_income, revenue) * 100
    fcf_margin = _div(fcf, revenue) * 100
    roce = _div(ebit, (total_assets - cur_liab)) * 100

    z_score = _altman_z(
        wc=working_capital if not math.isnan(working_capital) else 0.0,
        re=ret_earnings if not math.isnan(ret_earnings) else 0.0,
        ebit=ebit if not math.isnan(ebit) else 0.0,
        eq=total_equity if not math.isnan(total_equity) else 0.0,
        tl=total_liabilities if not math.isnan(total_liabilities) else 1.0,
        rev=revenue if not math.isnan(revenue) else 0.0,
        ta=total_assets
    )
    
    z_score_zone = "DISTRESS" if z_score < THRESHOLDS["z_score_distress"] else "GREY ZONE" if z_score < THRESHOLDS["z_score_grey"] else "SAFE" if not math.isnan(z_score) else "N/A"

    result = {
        "revenue": revenue, "ebit": ebit, "ebitda": ebitda, "net_income": net_income,
        "total_debt": total_debt, "net_debt": net_debt, "cash": cash, "total_equity": total_equity,
        "total_assets": total_assets, "interest_expense": interest, "fcf": fcf, "cfo": cfo,
        "debt_ebitda": debt_ebitda, "net_debt_ebitda": net_debt_ebitda, "debt_equity": debt_equity,
        "debt_assets": debt_assets, "ebit_coverage": ebit_coverage, "ebitda_coverage": ebitda_coverage,
        "fcc_proxy": fcc_proxy, "fcc": fcc_proxy, "current_ratio": current_ratio, "quick_ratio": quick_ratio,
        "cash_ratio": cash_ratio, "ebitda_margin": ebitda_margin, "net_margin": net_margin,
        "fcf_margin": fcf_margin, "roce": roce, "z_score": z_score, "z_score_zone": z_score_zone,
        
        "period_label": period_label,
        "net_cash_position": net_cash_position,
        "negative_ebitda": negative_ebitda,
        "ebitda_is_estimated": ebitda_is_estimated,
        "fcc_note": FCC_NOTE,
        "z_score_methodology": Z_SCORE_METHODOLOGY,
        "data_quality_notes": notes,
    }
    
    numeric_keys = [k for k, v in result.items() if isinstance(v, float)]
    result["data_available_fields"] = sorted([k for k in numeric_keys if not math.isnan(result[k])])
    result["data_missing_fields"] = sorted([k for k in numeric_keys if math.isnan(result[k])])
    
    return result

def compute_all_ratios(raw_data: dict, periods: list[str]) -> dict:
    income = raw_data.get("income", {})
    balance = raw_data.get("balance", {})
    cashflow = raw_data.get("cashflow", {})
    
    period_ratios = {}
    for idx, period in enumerate(periods):
        year_str = str(period)[:4]
        label = f"Latest FY ({year_str})" if idx == 0 else year_str
        period_ratios[label] = compute_period_ratios(income, balance, cashflow, idx, label)
        
    return period_ratios

def z_score_label(z: float) -> str:
    if math.isnan(z): return "N/A"
    if z < THRESHOLDS["z_score_distress"]: return "DISTRESS"
    if z < THRESHOLDS["z_score_grey"]: return "GREY ZONE"
    return "SAFE"
