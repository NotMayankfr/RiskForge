"""
data_fetcher.py
Pulls balance sheet, income statement, and cash flow data from yfinance.
Returns cleaned DataFrames for each company.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ── Field name aliases ───────────────────────────────────────────────────────
# yfinance uses slightly different field names across tickers / periods.
# We try multiple aliases and take the first non-null hit.

_INCOME_ALIASES: dict[str, list[str]] = {
    "revenue":           ["Total Revenue", "Revenue", "TotalRevenue"],
    "ebit":              ["EBIT", "Operating Income", "OperatingIncome"],
    "ebitda":            ["EBITDA", "NormalizedEBITDA"],
    "interest_expense":  ["Interest Expense", "InterestExpense"],
    "net_income":        ["Net Income", "NetIncome"],
    "depreciation":      [
        "Depreciation And Amortization",
        "DepreciationAndAmortization",
        "Reconciled Depreciation",
        "ReconciledDepreciation",
    ],
    "tax_expense":       ["Tax Provision", "TaxProvision", "IncomeTax Expense"],
    "pretax_income":     ["Pretax Income", "PretaxIncome"],
}

_BALANCE_ALIASES: dict[str, list[str]] = {
    "total_assets":      ["Total Assets", "TotalAssets"],
    "total_equity":      ["Total Equity Gross Minority Interest",
                          "Stockholders Equity", "StockholdersEquity",
                          "Common Stock Equity", "CommonStockEquity"],
    "total_debt":        ["Total Debt", "TotalDebt"],
    "long_term_debt":    ["Long Term Debt", "LongTermDebt"],
    "short_term_debt":   ["Current Debt", "CurrentDebt", "Short Term Debt"],
    "cash":              ["Cash And Cash Equivalents",
                          "CashAndCashEquivalents", "Cash"],
    "current_assets":    ["Current Assets", "CurrentAssets"],
    "current_liabilities": ["Current Liabilities", "CurrentLiabilities"],
    "inventory":         ["Inventory"],
    "retained_earnings": ["Retained Earnings", "RetainedEarnings"],
    "working_capital":   ["Working Capital", "WorkingCapital"],
}

_CF_ALIASES: dict[str, list[str]] = {
    "cfo":               ["Operating Cash Flow", "OperatingCashFlow",
                          "Cash Flow From Operations"],
    "capex":             ["Capital Expenditure", "CapitalExpenditure",
                          "Purchase Of Property Plant And Equipment"],
    "fcf":               ["Free Cash Flow", "FreeCashFlow"],
}


def _pick(df: pd.DataFrame, aliases: list[str]) -> pd.Series | None:
    """Return the first Series in df whose index label matches an alias."""
    for alias in aliases:
        if alias in df.index:
            return df.loc[alias]
    return None


def _extract(df: pd.DataFrame, alias_map: dict[str, list[str]]) -> dict[str, pd.Series]:
    """Extract named series from a wide DataFrame using alias fallback."""
    result: dict[str, pd.Series] = {}
    for field, aliases in alias_map.items():
        series = _pick(df, aliases)
        if series is not None:
            result[field] = series
        else:
            logger.debug("Field '%s' not found in DataFrame (tried: %s)", field, aliases)
    return result


def fetch_company_data(ticker_str: str) -> dict[str, Any] | None:
    """
    Fetch annual financial statements for a single ticker.

    Returns a dict with keys:
        'income'   : dict[str, pd.Series]
        'balance'  : dict[str, pd.Series]
        'cashflow' : dict[str, pd.Series]
        'periods'  : list[str]   (ISO date strings, most-recent first)
    or None on failure.
    """
    try:
        ticker = yf.Ticker(ticker_str)

        # Fetch raw DataFrames (annual, transposed so columns are dates)
        income_raw  = ticker.financials          # income statement
        balance_raw = ticker.balance_sheet       # balance sheet
        cf_raw      = ticker.cashflow            # cash flow statement

        if income_raw is None or income_raw.empty:
            logger.warning("[%s] Empty income statement — skipping.", ticker_str)
            return None

        # Common periods (columns) — most-recent first
        periods = [str(c.date()) for c in income_raw.columns]

        income_data  = _extract(income_raw,  _INCOME_ALIASES)
        balance_data = _extract(balance_raw, _BALANCE_ALIASES) if balance_raw is not None else {}
        cf_data      = _extract(cf_raw,      _CF_ALIASES)      if cf_raw is not None else {}

        return {
            "income":   income_data,
            "balance":  balance_data,
            "cashflow": cf_data,
            "periods":  periods,
        }

    except Exception as exc:
        logger.error("[%s] Fetch failed: %s", ticker_str, exc)
        return None


def fetch_all(companies: list[dict]) -> dict[str, dict]:
    """
    Fetch data for all companies.

    Returns:
        { ticker: raw_data_dict | None }
    """
    results: dict[str, dict] = {}
    for co in companies:
        ticker = co["ticker"]
        logger.info("Fetching data for %s (%s)…", co["name"], ticker)
        results[ticker] = fetch_company_data(ticker)
    return results
