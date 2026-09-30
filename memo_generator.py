"""
memo_generator.py
Uses the Gemini API to auto-draft structured one-page credit memos.
The prompt is built from the full quantitative analysis output of every module.

DESIGN PRINCIPLES:
- The LLM receives all computed values explicitly in the prompt.
- The LLM is instructed NOT to invent: debt maturities, covenants,
  loan terms, collateral, guarantees, or any financial facts not supplied.
- All assumptions and limitations are labeled in the prompt.
- If data is missing, the LLM must acknowledge the gap explicitly.
"""

from __future__ import annotations

import math
import logging
from typing import Any

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL
from signal_flags import CreditFlag, overall_risk_rating

logger = logging.getLogger(__name__)

# ── Gemini client singleton ──────────────────────────────────────────────────
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


# ── Formatting helpers ────────────────────────────────────────────────────────

def _f(v: float, d: int = 2, suffix: str = "") -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "N/A"
    return f"{v:,.{d}f}{suffix}"


def _fbn(v: float) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "N/A"
    return f"${v / 1e9:,.2f}B"


def _flag_lines(flags: list[CreditFlag]) -> str:
    if not flags:
        return "• No material credit flags detected."
    return "\n".join(
        f"  • [{f.severity}][{f.category}] {f.message}" for f in flags
    )


def _covenant_summary(covenants: dict) -> str:
    if not covenants or "covenants" not in covenants:
        return "  • Illustrative covenant data not available."
    lines = []
    for c in covenants.get("covenants", []):
        status = c.get("status", "N/A")
        cv = _f(c.get("current_value", float("nan")))
        thr = _f(c.get("threshold", float("nan")))
        hdroom = _f(c.get("headroom", float("nan")))
        lines.append(
            f"  • {c.get('metric','?')}: Current={cv}x | "
            f"Threshold={thr}x | Headroom={hdroom}x | Status={status}"
        )
    return "\n".join(lines) if lines else "  • No covenant data."


def _stress_summary(stress: dict) -> str:
    if not stress:
        return "  • Stress test data not available."
    lines = []
    for key in ["moderate", "severe"]:
        s = stress.get(key, {})
        if not s:
            continue
        label = s.get("label", key)
        dde = _f(s.get("delta_vs_base_debt_ebitda", float("nan")), 2)
        dic = _f(s.get("delta_vs_base_ebit_coverage", float("nan")), 2)
        sde = _f(s.get("stressed_debt_ebitda", float("nan")), 1, "x")
        sic = _f(s.get("stressed_ebit_coverage", float("nan")), 1, "x")
        lines.append(
            f"  • {label}: Debt/EBITDA={sde} (Δ{dde}x) | "
            f"Coverage={sic} (Δ{dic}x)"
        )
    return "\n".join(lines) if lines else "  • No stress data."


def _cashflow_summary(cf: dict, ttm: dict) -> str:
    hist = cf.get("historical", [])
    if not hist:
        return "  • Cash flow history not available."
    latest = hist[0]
    return (
        f"  • CFO: {_fbn(latest.get('cfo', float('nan')))} | "
        f"Capex: {_fbn(latest.get('capex', float('nan')))} | "
        f"FCF: {_fbn(latest.get('fcf', float('nan')))}\n"
        f"  • FCF Margin: {_f(latest.get('fcf_margin', float('nan')), 1)}% | "
        f"FCF Conversion: {_f(latest.get('fcf_conversion', float('nan')), 1)}%\n"
        f"  • Debt Paydown Capacity: {_f(latest.get('debt_paydown_capacity', float('nan')), 1)}% of debt per year from FCF"
    )


def _sector_summary(sector: dict) -> str:
    if not sector:
        return "  • Sector data not available."
    return (
        f"  • Sector: {sector.get('sector', 'N/A')} | Sub-sector: {sector.get('sub_sector', 'N/A')}\n"
        f"  • Primary Customer: {sector.get('primary_customer', 'N/A')}\n"
        f"  • Revenue Visibility: {sector.get('revenue_visibility', 'N/A')}\n"
        f"  • Capital Intensity: {sector.get('capital_intensity', 'N/A')} | "
        f"Cyclicality: {sector.get('cyclicality', 'N/A')}\n"
        f"  • Key Programs: {', '.join(sector.get('key_programs', ['N/A']))}\n"
        f"  • Geographic Exposure: {', '.join(sector.get('geographic_exposure', ['N/A']))}"
    )


def _credit_framework_summary(cf_dict: dict) -> str:
    if not cf_dict:
        return "  • Credit framework data not available."
    strengths = cf_dict.get("financial_strengths", {}).get("items", [])
    weaknesses = cf_dict.get("financial_weaknesses", {}).get("items", [])
    view = cf_dict.get("overall_credit_view", "Not assessed")
    s_lines = "\n".join(f"    + {s}" for s in strengths[:4]) or "    + None identified"
    w_lines = "\n".join(f"    - {w}" for w in weaknesses[:4]) or "    - None identified"
    monitoring = cf_dict.get("monitoring_items", [])
    m_lines = "\n".join(f"    * {m}" for m in monitoring[:5]) or "    * None specified"
    return (
        f"  Strengths:\n{s_lines}\n"
        f"  Weaknesses:\n{w_lines}\n"
        f"  Credit View: {view}\n"
        f"  Key Monitoring Items:\n{m_lines}"
    )


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(
    company: dict,
    latest_period_label: str,
    ttm: dict,
    period_ratios: dict,
    flags: list[CreditFlag],
    risk_rating: str,
    debt_cap: dict,
    stress: dict,
    refi: dict,
    covenants: dict,
    cashflow: dict,
    sector: dict,
    credit_fw: dict,
) -> str:
    ordered = list(period_ratios.keys())
    de_trend = " → ".join(_f(period_ratios[k].get("debt_ebitda", float("nan")), 1, "x") for k in ordered)
    ic_trend = " → ".join(_f(period_ratios[k].get("ebit_coverage", float("nan")), 1, "x") for k in ordered)

    refi_class = refi.get("classification", "N/A") if refi else "N/A"
    refi_reason = refi.get("overall_reason", "N/A") if refi else "N/A"
    refi_note = refi.get("maturity_note", "") if refi else ""

    cov_sum = _covenant_summary(covenants)
    stress_sum = _stress_summary(stress)
    cf_sum = _cashflow_summary(cashflow, ttm)
    sec_sum = _sector_summary(sector)
    framework_sum = _credit_framework_summary(credit_fw)

    prompt = f"""
You are a senior credit analyst producing a structured credit memorandum.
Your task is to write a professional, analytical ONE-PAGE CREDIT MEMO for the company below.

STRICT RULES — violations will invalidate the memo:
1. Use ONLY the data supplied in this prompt. Do NOT invent any facts.
2. Do NOT fabricate debt maturities, specific loan terms, collateral, guarantees, or covenants.
3. If data is unavailable (shown as N/A), acknowledge the gap explicitly — do not fill it.
4. Clearly label all assumptions. All stress scenarios and covenant thresholds are ILLUSTRATIVE.
5. Do NOT present scenario assumptions as the company's actual obligations.
6. Be analytical and direct. Avoid vague qualitative language without numerical support.

═══════════════════════════════════════════════
COMPANY DATA PACKAGE — {company['name']} ({company['ticker']})
Country: {company['country']} | Exchange: {company['exchange']}
Analysis Period: {latest_period_label}
Overall Credit Risk Assessment: {risk_rating}
═══════════════════════════════════════════════

SECTION A — FINANCIAL PERFORMANCE ({latest_period_label})
  Revenue:          {_fbn(ttm.get('revenue', float('nan')))}
  EBITDA:           {_fbn(ttm.get('ebitda', float('nan')))} | Margin: {_f(ttm.get('ebitda_margin', float('nan')), 1)}%
  EBIT:             {_fbn(ttm.get('ebit', float('nan')))}
  Net Income:       {_fbn(ttm.get('net_income', float('nan')))}
  FCF:              {_fbn(ttm.get('fcf', float('nan')))} | FCF Margin: {_f(ttm.get('fcf_margin', float('nan')), 1)}%
  Negative EBITDA:  {ttm.get('negative_ebitda', False)}
  Net Cash Position:{ttm.get('net_cash_position', False)}

SECTION B — LEVERAGE ({latest_period_label})
  Total Debt:            {_fbn(ttm.get('total_debt', float('nan')))}
  Net Debt:              {_fbn(ttm.get('net_debt', float('nan')))}
  Total Debt / EBITDA:   {_f(ttm.get('debt_ebitda', float('nan')), 2)}x
  Net Debt / EBITDA:     {_f(ttm.get('net_debt_ebitda', float('nan')), 2)}x
  Debt / Equity:         {_f(ttm.get('debt_equity', float('nan')), 2)}x
  Leverage Trend (most recent → oldest): {de_trend}

SECTION C — COVERAGE ({latest_period_label})
  EBIT Interest Coverage:   {_f(ttm.get('ebit_coverage', float('nan')), 2)}x
  EBITDA Interest Coverage: {_f(ttm.get('ebitda_coverage', float('nan')), 2)}x
  FCC (simplified proxy):   {_f(ttm.get('fcc_proxy', float('nan')), 2)}x
  Note: {ttm.get('fcc_note', 'FCC is a simplified proxy only.')}
  Coverage Trend (most recent → oldest): {ic_trend}

SECTION D — LIQUIDITY ({latest_period_label})
  Current Ratio:  {_f(ttm.get('current_ratio', float('nan')), 2)}x
  Quick Ratio:    {_f(ttm.get('quick_ratio', float('nan')), 2)}x
  Cash:           {_fbn(ttm.get('cash', float('nan')))}

SECTION E — ALTMAN Z-SCORE
  Z-Score: {_f(ttm.get('z_score', float('nan')), 2)}
  Zone: {ttm.get('z_score_zone', 'N/A')}
  Methodology Note: {ttm.get('z_score_methodology', 'Altman 1968 model with book equity proxy.')}

SECTION F — CASH FLOW ANALYSIS
{cf_sum}

SECTION G — DEBT CAPACITY (ILLUSTRATIVE)
  Max Sustainable Debt (illustrative): {_fbn(debt_cap.get('max_sustainable_debt', float('nan')) if debt_cap else float('nan'))}
  Leverage Headroom:                   {_fbn(debt_cap.get('leverage_headroom', float('nan')) if debt_cap else float('nan'))}
  Incremental Debt Capacity:           {_fbn(debt_cap.get('incremental_debt_capacity', float('nan')) if debt_cap else float('nan'))}
  Binding Constraint:                  {debt_cap.get('binding_constraint', 'N/A') if debt_cap else 'N/A'}
  Stress-Adjusted Capacity:            {_fbn(debt_cap.get('stress_incremental_capacity', float('nan')) if debt_cap else float('nan'))}
  FCF Debt Paydown Capacity:           {_f(debt_cap.get('fcf_paydown_pct', float('nan')) if debt_cap else float('nan'), 1)}% per year
  FCF Paydown Period:                  {_f(debt_cap.get('fcf_paydown_years', float('nan')) if debt_cap else float('nan'), 1)} years
  +200bps Rate Shock Additional Cost:  {_fbn(debt_cap.get('interest_rate_shock_cost', float('nan')) if debt_cap else float('nan'))}
  ASSUMPTIONS: {debt_cap.get('assumptions', {}) if debt_cap else 'N/A'}

SECTION H — REFINANCING RISK
  Classification: {refi_class}
  Reason: {refi_reason}
  Data Limitation: {refi_note}

SECTION I — ILLUSTRATIVE COVENANT ANALYSIS
{cov_sum}
  Disclaimer: All covenant thresholds are illustrative analytical parameters. Not actual legal covenants.

SECTION J — STRESS TESTING (ILLUSTRATIVE SCENARIOS)
{stress_sum}

SECTION K — EARLY-WARNING FLAGS
{_flag_lines(flags)}

SECTION L — SECTOR CONTEXT
{sec_sum}

SECTION M — CREDIT FRAMEWORK ASSESSMENT
{framework_sum}

═══════════════════════════════════════════════
MEMO STRUCTURE — Write each section in order:
═══════════════════════════════════════════════

**CREDIT MEMORANDUM**
Company: {company['name']} ({company['ticker']}) | Country: {company['country']}
Period: {latest_period_label} | Credit Risk: {risk_rating}

**1. BORROWER OVERVIEW**
(2 sentences: company type, primary business, government customer dependency)

**2. BUSINESS & SECTOR PROFILE**
(3 sentences: defense sector positioning, revenue visibility, cyclicality, key programs — use Section L data)

**3. FINANCIAL PERFORMANCE**
(Use Section A data. Comment on revenue, EBITDA, margins, net income trend. Reference actual numbers.)

**4. LIQUIDITY ANALYSIS**
(Use Section D. Assess current ratio, quick ratio, cash position. Flag tight liquidity if current ratio < 1.0x.)

**5. LEVERAGE ANALYSIS**
(Use Section B. Assess gross and net leverage, trend direction, vs. sector norms. Reference actual trend.)

**6. CASH FLOW ANALYSIS**
(Use Section F. CFO, capex, FCF, FCF margin, FCF conversion, debt paydown capacity.)

**7. DEBT CAPACITY**
(Use Section G. State illustrative max debt, headroom, binding constraint. Clearly label as illustrative.)

**8. REFINANCING RISK**
(Use Section H. State classification and reasons. Acknowledge absence of maturity data explicitly.)

**9. COVENANT ANALYSIS (ILLUSTRATIVE)**
(Use Section I. Status, any breaches/tight covenants, trend. Label clearly as illustrative.)

**10. STRESS TESTING**
(Use Section J. Moderate and severe downside impact on leverage and coverage. Label scenarios as illustrative.)

**11. EARLY-WARNING INDICATORS**
(Use Section K. List all flags with severity.)

**12. KEY CREDIT RISKS**
(4-5 bullets: specific, quantitative where possible, from data supplied)

**13. KEY CREDIT STRENGTHS**
(3-4 bullets: specific, quantitative where possible)

**14. MONITORING ITEMS**
(3-4 specific metrics to track quarterly)

**15. ANALYTICAL CREDIT VIEW**
(2-3 sentences: overall view, recommendation [Invest/Monitor/Avoid], and key conditions.
 Do NOT state this as an actual credit rating or regulatory assessment.)

---
Write only the memo. No meta-commentary. No invented facts beyond the data package supplied.
""".strip()

    return prompt


# ── Public API ────────────────────────────────────────────────────────────────

def generate_memo(
    company: dict,
    period_ratios: dict[str, dict],
    flags: list[CreditFlag],
    debt_cap: dict | None = None,
    stress: dict | None = None,
    refi: dict | None = None,
    covenants: dict | None = None,
    cashflow: dict | None = None,
    sector: dict | None = None,
    credit_fw: dict | None = None,
) -> str:
    ordered = list(period_ratios.keys())
    latest_period_label = ordered[0] if ordered else "Latest FY"
    ttm = period_ratios.get(ordered[0], {}) if ordered else {}
    z = ttm.get("z_score", float("nan"))
    risk_rating = overall_risk_rating(flags, z)

    prompt = _build_prompt(
        company=company,
        latest_period_label=latest_period_label,
        ttm=ttm,
        period_ratios=period_ratios,
        flags=flags,
        risk_rating=risk_rating,
        debt_cap=debt_cap or {},
        stress=stress or {},
        refi=refi or {},
        covenants=covenants or {},
        cashflow=cashflow or {},
        sector=sector or {},
        credit_fw=credit_fw or {},
    )

    # Public-demo configuration:
    # Make at most ONE Gemini API request per memo-generation call.
    # If it fails, use the deterministic fallback rather than trying
    # multiple models/retries and consuming additional API quota.

    try:
        client = _get_client()

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        memo_text = response.text or ""

        if not memo_text.strip():
            raise ValueError("Empty response from Gemini API.")

        logger.info(
            "[%s] Credit memo generated via %s.",
            company["name"],
            GEMINI_MODEL,
        )

        return memo_text

    except Exception as exc:
        logger.warning(
            "[%s] Gemini request failed; using deterministic fallback: %s",
            company["name"],
            exc,
        )

        return _fallback_memo(
            company,
            ttm,
            flags,
            risk_rating,
            debt_cap,
            refi,
            covenants,
        )


def _fallback_memo(
    company: dict,
    r: dict,
    flags: list[CreditFlag],
    risk_rating: str,
    debt_cap: dict | None,
    refi: dict | None,
    covenants: dict | None,
) -> str:
    flag_text = _flag_lines(flags)
    cov_text = _covenant_summary(covenants) if covenants else "  • Covenant data not available."
    refi_class = refi.get("classification", "N/A") if refi else "N/A"
    cap_headroom = _fbn(debt_cap.get("leverage_headroom", float("nan"))) if debt_cap else "N/A"

    return f"""CREDIT MEMORANDUM (Offline / Fallback — Gemini API unavailable)
Company: {company['name']} ({company['ticker']}) | {company['country']}
Period: {r.get('period_label', 'Latest FY')} | Credit Risk: {risk_rating}

1. FINANCIAL SUMMARY
   Revenue: {_fbn(r.get('revenue', float('nan')))} | EBITDA: {_fbn(r.get('ebitda', float('nan')))} ({_f(r.get('ebitda_margin', float('nan')), 1)}% margin)
   FCF: {_fbn(r.get('fcf', float('nan')))} | Cash: {_fbn(r.get('cash', float('nan')))}

2. LEVERAGE & COVERAGE
   Debt/EBITDA: {_f(r.get('debt_ebitda', float('nan')), 2)}x | Net Debt/EBITDA: {_f(r.get('net_debt_ebitda', float('nan')), 2)}x
   EBIT Coverage: {_f(r.get('ebit_coverage', float('nan')), 2)}x | Current Ratio: {_f(r.get('current_ratio', float('nan')), 2)}x

3. ALTMAN Z-SCORE
   Z-Score: {_f(r.get('z_score', float('nan')), 2)} | Zone: {r.get('z_score_zone', 'N/A')}
   Note: {r.get('z_score_methodology', 'Altman 1968 with book equity proxy.')}

4. DEBT CAPACITY (ILLUSTRATIVE)
   Leverage Headroom: {cap_headroom}

5. REFINANCING RISK
   Classification: {refi_class}
   Note: Debt maturity data not available from yfinance.

6. ILLUSTRATIVE COVENANT ANALYSIS
{cov_text}

7. EARLY-WARNING FLAGS
{flag_text}

Note: Full AI-generated memo unavailable. Set a valid GEMINI_API_KEY in environment.
All data sourced from yfinance annual filings.
""".strip()
