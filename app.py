"""
app.py
Streamlit web application for the Dynamic Credit Analytics Tool.
Run with: python -m streamlit run app.py
"""

import streamlit as st
import math
import pandas as pd
import json
import os
import hashlib

# Import our backend modules
from data_fetcher import fetch_all
from ratio_engine import compute_all_ratios
from signal_flags import analyze_flags, overall_risk_rating
import memo_generator
import debt_capacity
import stress_engine
import refinancing_risk
import covenant_monitor
import cashflow_model
import credit_framework
from config import COVENANT_THRESHOLDS, STRESS_SCENARIOS, PROJECTION_ASSUMPTIONS

st.set_page_config(page_title="RiskForge — Credit Intelligence", layout="wide", page_icon="🛡️")

# --- TICKER DICTIONARY (Markets & Sectors) ---
# Pre-mapped top ~10 tickers by market capitalization for reliable live analysis.
MARKET_SECTOR_MAP = {
    "United States (NYSE/NASDAQ)": {
        "Defense & Aerospace": ["RTX", "LMT", "NOC", "GD", "LHX", "HII", "BA", "TXT", "SPR", "WWD"],
        "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO", "ORCL", "CSCO", "CRM", "AMD"],
        "Financials": ["JPM", "BAC", "WFC", "C", "GS", "MS", "AXP", "BLK", "CB", "PGR"],
        "Healthcare": ["LLY", "UNH", "JNJ", "MRK", "ABBV", "PFE", "AMGN", "ISRG", "SYK", "MDT"]
    },
    "India (NSE/BSE)": {
        "Defense & Aerospace": ["HAL.NS", "BEL.NS", "BDL.NS", "MAZDOCK.NS", "COCHINSHIP.NS", "BEML.NS", "GRSE.NS", "MTARTECH.NS", "DATA.NS", "ASTRAMICRO.NS"],
        "Technology (IT)": ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "LTIM.NS", "TECHM.NS", "PERSISTENT.NS", "MPHASIS.NS", "OFSS.NS", "CYIENT.NS"],
        "Financials": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS", "RECLTD.NS", "PFC.NS"],
        "Healthcare/Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "MAXHEALTH.NS", "TORNTPHARM.NS", "ZYDUSLIFE.NS", "LUPIN.NS", "AUROPHARMA.NS"]
    },
    "United Kingdom (LSE)": {
        "Defense & Aerospace": ["BA.L", "RR.L", "QQ.L", "CHG.L", "SMIN.L"],
        "Financials": ["HSBA.L", "BARC.L", "LLOY.L", "NWG.L", "STAN.L"],
        "Healthcare/Pharma": ["AZN.L", "GSK.L", "HLN.L", "SNN.L", "HIK.L"]
    },
    "Europe (Euronext)": {
        "Defense & Aerospace": ["HO.PA", "AM.PA", "SAF.PA", "LDO.MI", "RHM.DE"],
        "Technology": ["ASML.AS", "SAP.DE", "SU.PA", "IFX.DE", "STM.PA"],
        "Financials": ["BNP.PA", "SAN.MC", "INGA.AS", "ISP.MI", "GLE.PA"]
    },
    "Japan (TSE)": {
        "Defense & Aerospace": ["7011.T", "7012.T", "7013.T"],
        "Technology": ["6861.T", "8035.T", "6758.T", "6981.T", "6702.T"],
        "Financials": ["8306.T", "8316.T", "8411.T", "8766.T", "8591.T"]
    }
}



# --- SESSION / AI SECURITY INITIALIZATION ---
# Gemini is kept server-side through Streamlit Secrets.
# Local development can use the GEMINI_API_KEY environment variable.
# Visitors never need to supply their own API key.

AI_SESSION_LIMIT = 3
AI_GLOBAL_HOURLY_LIMIT = 20

if "ai_calls_used" not in st.session_state:
    st.session_state.ai_calls_used = 0

if "memo_cache" not in st.session_state:
    st.session_state.memo_cache = {}

try:
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    GEMINI_API_KEY = ""

if not GEMINI_API_KEY:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

AI_ENABLED = bool(GEMINI_API_KEY)


@st.cache_resource
def _get_global_ai_guard():
    """Shared cache and hourly AI-call guard for the app instance."""
    import threading
    import time

    return {
        "cache": {},
        "calls": 0,
        "window_start": time.time(),
        "lock": threading.Lock(),
    }


GLOBAL_AI = _get_global_ai_guard()

# Configure the existing Gemini module without exposing the key in the UI.
memo_generator.GEMINI_API_KEY = GEMINI_API_KEY
memo_generator._client = None


def _memo_cache_key(
    company,
    period_ratios,
    flags,
    debt_cap,
    stress,
    refi,
    covenants,
    cashflow,
    sector,
    credit_fw,
    max_leverage,
    revenue_growth,
):
    """Create a stable cache key from the complete analytical context."""
    payload = {
        "company": company,
        "period_ratios": period_ratios,
        "flags": [vars(f) for f in flags],
        "debt_cap": debt_cap,
        "stress": stress,
        "refi": refi,
        "covenants": covenants,
        "cashflow": cashflow,
        "sector": sector,
        "credit_fw": credit_fw,
        "max_leverage": max_leverage,
        "revenue_growth": revenue_growth,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        default=str,
        allow_nan=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _fallback_memo(
    company,
    period_ratios,
    flags,
    risk,
    debt_cap,
    refi,
    covenants,
    reason,
):
    """Use the existing deterministic fallback memo."""
    ordered = list(period_ratios.keys())
    ttm = period_ratios.get(ordered[0], {}) if ordered else {}

    try:
        return memo_generator._fallback_memo(
            company,
            ttm,
            flags,
            risk,
            debt_cap,
            refi,
            covenants,
        )
    except Exception:
        return (
            f"### Credit Memo — {company['ticker']}\n\n"
            f"AI memo unavailable: {reason}\n\n"
            "The deterministic credit analysis remains available in the "
            "other dashboard sections."
        )


def generate_protected_memo(
    company,
    period_ratios,
    flags,
    risk,
    debt_cap,
    stress,
    refi,
    covenants,
    cashflow,
    sector,
    credit_fw,
    max_leverage,
    revenue_growth,
):
    """
    Public-demo-safe Gemini wrapper:
    - server-side secret only
    - 3 new AI generations per browser session
    - 20 new AI generations per app instance per hour
    - shared memo cache across visitors
    - deterministic fallback when AI is unavailable
    """

    cache_key = _memo_cache_key(
        company,
        period_ratios,
        flags,
        debt_cap,
        stress,
        refi,
        covenants,
        cashflow,
        sector,
        credit_fw,
        max_leverage,
        revenue_growth,
    )

    # Identical analyses reuse the same memo without another Gemini request.
    with GLOBAL_AI["lock"]:
        cached = GLOBAL_AI["cache"].get(cache_key)

    if cached is not None:
        return cached

    # The analytical dashboard still works when Gemini is not configured.
    if not AI_ENABLED:
        return _fallback_memo(
            company,
            period_ratios,
            flags,
            risk,
            debt_cap,
            refi,
            covenants,
            "Gemini API key is not configured.",
        )

    # Limit the amount one browser session can generate.
    if st.session_state.ai_calls_used >= AI_SESSION_LIMIT:
        return _fallback_memo(
            company,
            period_ratios,
            flags,
            risk,
            debt_cap,
            refi,
            covenants,
            "AI session limit reached.",
        )

    # Shared hourly guard for the public deployment.
    import time

    with GLOBAL_AI["lock"]:
        now = time.time()

        if now - GLOBAL_AI["window_start"] >= 3600:
            GLOBAL_AI["window_start"] = now
            GLOBAL_AI["calls"] = 0

        if GLOBAL_AI["calls"] >= AI_GLOBAL_HOURLY_LIMIT:
            global_limit_reached = True
        else:
            GLOBAL_AI["calls"] += 1
            global_limit_reached = False

    if global_limit_reached:
        return _fallback_memo(
            company,
            period_ratios,
            flags,
            risk,
            debt_cap,
            refi,
            covenants,
            "Shared AI hourly limit reached.",
        )

    # Reserve the session slot before calling the API.
    st.session_state.ai_calls_used += 1

    try:
        memo = memo_generator.generate_memo(
            company,
            period_ratios,
            flags,
            debt_cap,
            stress,
            refi,
            covenants,
            cashflow,
            sector,
            credit_fw,
        )
    except Exception:
        memo = _fallback_memo(
            company,
            period_ratios,
            flags,
            risk,
            debt_cap,
            refi,
            covenants,
            "Gemini request failed.",
        )

    if memo and memo.strip():
        with GLOBAL_AI["lock"]:
            if len(GLOBAL_AI["cache"]) >= 100:
                oldest_key = next(iter(GLOBAL_AI["cache"]))
                GLOBAL_AI["cache"].pop(oldest_key, None)

            GLOBAL_AI["cache"][cache_key] = memo

    return memo


# ==========================================
# MAIN DASHBOARD
# ==========================================
# --- Sidebar ---
st.sidebar.title("Configuration")

if AI_ENABLED:
    st.sidebar.success("AI memo service configured")
else:
    st.sidebar.warning("AI memo service unavailable")

st.sidebar.caption(
    f"AI memo generations: "
    f"{st.session_state.ai_calls_used}/{AI_SESSION_LIMIT} this session"
)

st.sidebar.markdown("---")
st.sidebar.subheader("Illustrative Assumptions")

max_leverage = st.sidebar.slider(
    "Max Net Debt / EBITDA",
    2.0,
    8.0,
    4.0,
    0.5,
)

fcf_growth = st.sidebar.slider(
    "Revenue Growth Projection",
    -0.10,
    0.20,
    0.05,
    0.01,
)

PROJECTION_ASSUMPTIONS["revenue_growth_pct"] = fcf_growth

# --- Main Content UI ---
st.title("🛡️ RiskForge — Global Credit Intelligence")

analysis_mode = st.radio("Choose Analysis Mode:", ["Specific Company (Ticker)", "Entire Sector (Top 10 Companies)"], horizontal=True)

col1, col2 = st.columns(2)
with col1:
    market_choice = st.selectbox("Select Stock Market", list(MARKET_SECTOR_MAP.keys()))

tickers_to_run = []
sector_str = "Custom"

with col2:
    if analysis_mode == "Specific Company (Ticker)":
        ticker_input = st.text_input("Enter Company Ticker (e.g., LMT, AAPL, HAL.NS)", "LMT")
        sector_str = st.text_input("Industry / Sector Context", "Defense & Aerospace")
        if ticker_input:
            tickers_to_run = [ticker_input.strip().upper()]
    else:
        sector_choice = st.selectbox("Select Sector", list(MARKET_SECTOR_MAP[market_choice].keys()))
        sector_str = sector_choice
        tickers_to_run = MARKET_SECTOR_MAP[market_choice][sector_choice]
        st.info(f"Will analyze the following top companies: {', '.join(tickers_to_run)}")

if st.button("Run Comprehensive Analysis", type="primary"):
    if not tickers_to_run:
        st.warning("No tickers selected.")
        st.stop()
        
    companies = [{"name": t, "ticker": t, "country": market_choice, "exchange": market_choice} for t in tickers_to_run]
    
    with st.spinner(f"Fetching financial data for {len(tickers_to_run)} companies from Yahoo Finance..."):
        raw_data_map = fetch_all(companies)
        
    if not raw_data_map:
        st.error("Failed to fetch data. Check tickers or network connection.")
        st.stop()
        
    results = []
    progress_text = "Running analytical modules..."
    my_bar = st.progress(0, text=progress_text)
    
    for idx, co in enumerate(companies):
        ticker = co["ticker"]
        raw = raw_data_map.get(ticker)
        if not raw:
            st.toast(f"Could not retrieve data for {ticker}")
            continue
            
        # 1. Ratios
        period_ratios = compute_all_ratios(raw, raw["periods"])
        latest_period = list(period_ratios.keys())[0] if period_ratios else None
        ttm_ratios = period_ratios.get(latest_period, {}) if latest_period else {}
        
        # 2. Flags
        flags = analyze_flags(period_ratios, ticker)
        z = ttm_ratios.get("z_score", float("nan"))
        risk = overall_risk_rating(flags, z)
        
        # 3. Advanced Modules
        debt_cap = debt_capacity.compute_debt_capacity(ttm_ratios) if hasattr(debt_capacity, "compute_debt_capacity") else {}
        if debt_cap and "assumptions" in debt_cap:
            debt_cap["assumptions"]["max_net_leverage"] = max_leverage
            ebitda = ttm_ratios.get("ebitda", float("nan"))
            net_debt = ttm_ratios.get("net_debt", float("nan"))
            debt_cap["max_sustainable_debt"] = max_leverage * ebitda if not math.isnan(ebitda) else float("nan")
            debt_cap["leverage_headroom"] = debt_cap["max_sustainable_debt"] - net_debt if not math.isnan(net_debt) else float("nan")

        stress = stress_engine.run_stress_scenarios(ttm_ratios, raw, STRESS_SCENARIOS)
        refi = refinancing_risk.assess_refinancing_risk(ttm_ratios)
        covenants = covenant_monitor.analyze_covenants(period_ratios, COVENANT_THRESHOLDS)
        cashflow = cashflow_model.model_cashflows(raw, raw["periods"], PROJECTION_ASSUMPTIONS)
        
        sector_dict = {
            "sector": sector_str,
            "sub_sector": "N/A",
            "primary_customer": "Market Aggregate",
            "revenue_visibility": "Unknown",
            "capital_intensity": "Unknown",
            "cyclicality": "Unknown"
        }
        
        credit_fw = credit_framework.build_credit_assessment(co, period_ratios, flags, debt_cap, stress, refi, covenants, cashflow, sector_dict)
        
        # 4. LLM Memo
        memo = generate_protected_memo(
                    co,
                    period_ratios,
                    flags,
                    risk,
                    debt_cap,
                    stress,
                    refi,
                    covenants,
                    cashflow,
                    sector_dict,
                    credit_fw,
                    max_leverage,
                    fcf_growth,
                )
            
        results.append({
            "ticker": ticker,
            "risk": risk,
            "ratios": ttm_ratios,
            "flags": flags,
            "memo": memo,
            "debt_cap": debt_cap,
            "stress": stress,
            "refi": refi,
            "covenants": covenants,
            "cashflow": cashflow,
            "credit_fw": credit_fw,
            "all_ratios": period_ratios
        })
        
        my_bar.progress((idx + 1) / len(companies), text=f"Analyzed {ticker}...")

    my_bar.empty()
    
    # --- RENDER SECTOR SUMMARY (If applicable) ---
    if analysis_mode == "Entire Sector (Top 10 Companies)" and results:
        st.header(f"🌐 Sector Aggregate: {sector_str} ({market_choice})")
        
        s_col1, s_col2, s_col3 = st.columns(3)
        s_col1.metric("Total Companies Analyzed", len(results))
        high_risk_count = sum(1 for r in results if r["risk"] in ["HIGH", "ELEVATED"])
        s_col2.metric("High/Elevated Risk Constituents", high_risk_count)
        
        avg_z = pd.Series([r["ratios"].get("z_score", float("nan")) for r in results]).mean()
        s_col3.metric("Sector Average Z-Score", f"{avg_z:.2f}" if not math.isnan(avg_z) else "N/A")
        
        summary_data = []
        for r in results:
            z_score = r["ratios"].get("z_score", float("nan"))
            summary_data.append({
                "Ticker": r["ticker"],
                "Risk Profile": r["risk"],
                "Net Debt / EBITDA": round(r["ratios"].get("net_debt_ebitda", float("nan")), 2),
                "EBIT Coverage": round(r["ratios"].get("ebit_coverage", float("nan")), 2),
                "Refinancing Risk": r["refi"].get("classification", "N/A"),
                "Z-Score": round(z_score, 2) if not math.isnan(z_score) else "N/A"
            })
        
        st.dataframe(pd.DataFrame(summary_data).set_index("Ticker"), use_container_width=True)
        st.markdown("---")

    # --- RENDER INDIVIDUAL TABS ---
    st.header("🏢 Individual Company Deep Dives")
    tabs = st.tabs([r["ticker"] for r in results])
    
    for i, r in enumerate(results):
        with tabs[i]:
            st.subheader(f"{r['ticker']} - Credit Profile")
            
            # Badges
            st.markdown(f"**Risk Rating:** `{r['risk']}` | **Refinancing Risk:** `{r['refi'].get('classification', 'N/A')}`")
            
            # Sub-tabs for deep dive
            subtabs = st.tabs(["📝 AI Credit Memo", "Overview & Trends", "Debt Capacity & Covenants", "Cash Flow & Stress"])
            
            with subtabs[0]:
                st.markdown(r["memo"])

            with subtabs[1]:
                st.markdown("### Strengths & Weaknesses")
                c1, c2 = st.columns(2)
                with c1:
                    for s in r["credit_fw"].get("financial_strengths", {}).get("items", []):
                        st.markdown(f"✅ {s}")
                with c2:
                    for w in r["credit_fw"].get("financial_weaknesses", {}).get("items", []):
                        st.markdown(f"⚠️ {w}")
                        
                st.markdown("### Early Warning Flags")
                if not r["flags"]:
                    st.success("No material credit flags detected.")
                for f in r["flags"]:
                    st.warning(f"**[{f.severity}]** {f.message}")
                    
                st.markdown("### Historical Financials ($B)")
                periods = list(r["all_ratios"].keys())[::-1]
                chart_df = pd.DataFrame({
                    "Period": periods,
                    "Revenue": [r["all_ratios"][p].get("revenue", 0)/1e9 for p in periods],
                    "EBITDA": [r["all_ratios"][p].get("ebitda", 0)/1e9 for p in periods],
                    "Total Debt": [r["all_ratios"][p].get("total_debt", 0)/1e9 for p in periods]
                }).set_index("Period")
                st.bar_chart(chart_df[["Revenue", "EBITDA"]])
                st.line_chart(chart_df[["Total Debt"]])
                
            with subtabs[2]:
                dc = r["debt_cap"]
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("### Debt Capacity (Illustrative)")
                    st.metric("Max Net Leverage Assumption", f"{max_leverage}x")
                    st.metric("Current Net Leverage", f"{dc.get('current_net_leverage', float('nan')):.2f}x")
                    st.metric("Leverage Headroom", f"${dc.get('leverage_headroom', 0)/1e9:.2f}B")
                with c2:
                    st.markdown("### Covenants Monitor")
                    cov_df = pd.DataFrame(r["covenants"].get("covenants", []))
                    if not cov_df.empty:
                        st.dataframe(cov_df[["metric", "current_value", "threshold", "status"]], hide_index=True)
                    else:
                        st.info("No covenant data available.")

            with subtabs[3]:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("### Refinancing Risk")
                    for factor in r["refi"].get("factors", []):
                        st.markdown(f"- **{factor['name']}** ({factor['status']}): {factor['reason']}")
                with c2:
                    st.markdown("### Stress Scenarios")
                    stress_data = []
                    for s_key in ["base", "moderate", "severe"]:
                        s = r["stress"].get(s_key, {})
                        if s:
                            stress_data.append({
                                "Scenario": s.get("label", s_key),
                                "Debt/EBITDA": f"{s.get('stressed_debt_ebitda', float('nan')):.1f}x",
                                "Interest Cov": f"{s.get('stressed_ebit_coverage', float('nan')):.1f}x"
                            })
                    st.dataframe(pd.DataFrame(stress_data), hide_index=True)
