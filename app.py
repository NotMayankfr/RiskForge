"""
app.py
Institutional Web Application for RiskForge Financial Intelligence.
Run with: python -m streamlit run app.py
"""

import streamlit as st
import math
import pandas as pd
import json
import os
import hashlib

# Import backend modules
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
import db_manager
import trend_detector
import intelligence_report
from config import COVENANT_THRESHOLDS, STRESS_SCENARIOS, PROJECTION_ASSUMPTIONS

st.set_page_config(
    page_title="RiskForge | Corporate Credit & Financial Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── INSTITUTIONAL TERMINAL STYLING ──────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 1440px;
    }

    /* Masthead */
    .rf-masthead {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1.1rem 1.5rem;
        background: linear-gradient(180deg, #111827 0%, #0d131f 100%);
        border: 1px solid #1f2937;
        border-left: 3px solid #3b82f6;
        border-radius: 6px;
        margin-bottom: 1.25rem;
    }
    .rf-brand-title {
        font-size: 1.25rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        color: #f9fafb;
        margin: 0;
        text-transform: uppercase;
    }
    .rf-brand-sub {
        font-size: 0.78rem;
        color: #9ca3af;
        letter-spacing: 0.04em;
        margin-top: 0.2rem;
        text-transform: uppercase;
    }
    .rf-telemetry {
        display: flex;
        gap: 0.65rem;
        flex-wrap: wrap;
    }
    .rf-pill {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        padding: 0.3rem 0.65rem;
        border-radius: 4px;
        background: #1f2937;
        border: 1px solid #374151;
        color: #d1d5db;
    }
    .rf-pill-online {
        background: rgba(16, 185, 129, 0.1);
        border-color: rgba(16, 185, 129, 0.35);
        color: #6ee7b7;
    }

    /* Scorecard Grid */
    .rf-scorecard {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 0.75rem;
        margin: 0.75rem 0 1.25rem 0;
    }
    .rf-card {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 6px;
        padding: 0.85rem 1rem;
    }
    .rf-card-label {
        font-size: 0.68rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #9ca3af;
        margin-bottom: 0.35rem;
    }
    .rf-card-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.05rem;
        font-weight: 600;
        color: #f9fafb;
    }
    .rf-card-sub {
        font-size: 0.72rem;
        color: #6b7280;
        margin-top: 0.25rem;
    }

    /* Rating & Status Badges */
    .rf-badge {
        display: inline-block;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.18rem 0.55rem;
        border-radius: 3px;
        letter-spacing: 0.04em;
    }
    .rf-badge-HIGH, .rf-badge-DETERIORATING, .rf-badge-CRITICAL, .rf-badge-WARNING {
        background: rgba(239, 68, 68, 0.14);
        color: #fca5a5;
        border: 1px solid rgba(239, 68, 68, 0.35);
    }
    .rf-badge-ELEVATED, .rf-badge-MIXED, .rf-badge-CAUTION {
        background: rgba(245, 158, 11, 0.14);
        color: #fcd34d;
        border: 1px solid rgba(245, 158, 11, 0.35);
    }
    .rf-badge-MODERATE, .rf-badge-WATCH {
        background: rgba(59, 130, 246, 0.14);
        color: #93c5fd;
        border: 1px solid rgba(59, 130, 246, 0.35);
    }
    .rf-badge-LOW, .rf-badge-IMPROVING, .rf-badge-STABLE, .rf-badge-OK, .rf-badge-SAFE {
        background: rgba(16, 185, 129, 0.14);
        color: #6ee7b7;
        border: 1px solid rgba(16, 185, 129, 0.35);
    }

    /* Synthesis Banner */
    .rf-synthesis-box {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-left: 3px solid #6366f1;
        border-radius: 5px;
        padding: 0.9rem 1.15rem;
        margin-bottom: 1.25rem;
        font-size: 0.88rem;
        line-height: 1.55;
        color: #e2e8f0;
    }
    .rf-section-header {
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: #9ca3af;
        border-bottom: 1px solid #1f2937;
        padding-bottom: 0.45rem;
        margin: 1.25rem 0 0.75rem 0;
    }

    /* Tabs refinement */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.25rem;
        border-bottom: 1px solid #1f2937;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 0.82rem;
        font-weight: 500;
        letter-spacing: 0.02em;
        padding: 0.55rem 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- TICKER DICTIONARY (Markets & Sectors) ---
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
    """Public-demo-safe Gemini wrapper."""
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

    with GLOBAL_AI["lock"]:
        cached = GLOBAL_AI["cache"].get(cache_key)

    if cached is not None:
        return cached

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
# SIDEBAR & TELEMETRY INITIALIZATION
# ==========================================
db_manager.initialize_db()
try:
    _stored_stats = db_manager.run_custom_query(
        "SELECT COUNT(DISTINCT ticker) AS companies, COUNT(*) AS snapshots FROM ratio_snapshots"
    )
    _num_co = _stored_stats[0]["companies"] if _stored_stats else 0
    _num_snap = _stored_stats[0]["snapshots"] if _stored_stats else 0
except Exception:
    _num_co, _num_snap = 0, 0

st.sidebar.markdown("### UNDERWRITING PARAMETERS")
st.sidebar.caption("Illustrative credit policy thresholds and projection assumptions.")

max_leverage = st.sidebar.slider(
    "Max Net Debt / EBITDA Cap (x)",
    2.0,
    8.0,
    4.0,
    0.5,
)

fcf_growth = st.sidebar.slider(
    "Projected Annual Revenue Growth",
    -0.10,
    0.20,
    0.05,
    0.01,
)

PROJECTION_ASSUMPTIONS["revenue_growth_pct"] = fcf_growth

st.sidebar.markdown("---")
st.sidebar.markdown("### SYSTEM TELEMETRY")
st.sidebar.markdown(
    f"- **SQL Data Store:** `{_num_co} Issuers / {_num_snap} Periods`\n"
    f"- **AI Engine:** `{'ONLINE' if AI_ENABLED else 'OFFLINE'}`\n"
    f"- **Session Quota:** `{st.session_state.ai_calls_used} / {AI_SESSION_LIMIT} Memos`"
)

# ==========================================
# MASTHEAD
# ==========================================
st.markdown(
    f"""
    <div class="rf-masthead">
        <div>
            <div class="rf-brand-title">RiskForge Financial Intelligence</div>
            <div class="rf-brand-sub">Historical Trends &nbsp;&middot;&nbsp; SQL-Powered Analytics &nbsp;&middot;&nbsp; Risk Deterioration Detection</div>
        </div>
        <div class="rf-telemetry">
            <span class="rf-pill rf-pill-online">SQL ENGINE: ACTIVE ({_num_snap} SNAPSHOTS)</span>
            <span class="rf-pill">AI SYNTHESIS: {'READY' if AI_ENABLED else 'FALLBACK'} ({st.session_state.ai_calls_used}/{AI_SESSION_LIMIT})</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ==========================================
# SELECTION CONTROLS
# ==========================================
with st.container():
    c_mode, c_mkt, c_target, c_ctx = st.columns([1.3, 1.4, 1.4, 1.4])
    with c_mode:
        analysis_mode = st.selectbox(
            "Analysis Scope",
            ["Single Issuer Deep Dive", "Sector Peer Group / Cohort"],
        )
    with c_mkt:
        market_choice = st.selectbox("Exchange / Jurisdiction", list(MARKET_SECTOR_MAP.keys()))

    tickers_to_run = []
    sector_str = "Custom"

    if analysis_mode == "Single Issuer Deep Dive":
        with c_target:
            ticker_input = st.text_input("Issuer Ticker", "LMT")
        with c_ctx:
            sector_str = st.text_input("Sector Classification", "Defense & Aerospace")
        if ticker_input:
            tickers_to_run = [ticker_input.strip().upper()]
    else:
        with c_target:
            sector_choice = st.selectbox("Industry Sector", list(MARKET_SECTOR_MAP[market_choice].keys()))
            sector_str = sector_choice
            tickers_to_run = MARKET_SECTOR_MAP[market_choice][sector_choice]
        with c_ctx:
            st.text_input("Constituent Tickers", ", ".join(tickers_to_run), disabled=True)

run_clicked = st.button("Execute Credit & Trend Analysis", type="primary")

if run_clicked:
    if not tickers_to_run:
        st.warning("Specify at least one valid ticker symbol.")
        st.stop()

    companies = [
        {"name": t, "ticker": t, "country": market_choice, "exchange": market_choice}
        for t in tickers_to_run
    ]

    with st.spinner(f"Ingesting financial statements and populating SQL store for {len(tickers_to_run)} issuer(s)..."):
        raw_data_map = fetch_all(companies)

    if not raw_data_map:
        st.error("Unable to retrieve financial statements. Verify ticker symbol or connectivity.")
        st.stop()

    results = []
    my_bar = st.progress(0, text="Computing ratios and running SQL deterioration detection...")

    for idx, co in enumerate(companies):
        ticker = co["ticker"]
        raw = raw_data_map.get(ticker)
        if not raw:
            st.toast(f"No filing data returned for {ticker}")
            continue

        # 1. Ratios
        period_ratios = compute_all_ratios(raw, raw["periods"])
        latest_period = list(period_ratios.keys())[0] if period_ratios else None
        ttm_ratios = period_ratios.get(latest_period, {}) if latest_period else {}

        # 2. Point-in-time Flags & Baseline Risk
        flags = analyze_flags(period_ratios, ticker)
        z = ttm_ratios.get("z_score", float("nan"))
        baseline_risk = overall_risk_rating(flags, z)

        # 3. Store multi-period snapshots in SQLite
        db_manager.store_all_period_ratios(
            ticker=ticker,
            company_name=co["name"],
            market=market_choice,
            sector=sector_str,
            period_ratios=period_ratios,
            fiscal_periods=raw["periods"],
            risk_rating=baseline_risk,
        )

        # 4. Run SQL-powered trend & deterioration analysis and update risk assessment
        intel_report = trend_detector.analyze_ticker(ticker)
        risk = intel_report.updated_risk_rating if intel_report else baseline_risk

        # 5. Advanced Modules
        debt_cap = (
            debt_capacity.compute_debt_capacity(ttm_ratios)
            if hasattr(debt_capacity, "compute_debt_capacity")
            else {}
        )
        if debt_cap and "assumptions" in debt_cap:
            debt_cap["assumptions"]["max_net_leverage"] = max_leverage
            ebitda = ttm_ratios.get("ebitda", float("nan"))
            net_debt = ttm_ratios.get("net_debt", float("nan"))
            debt_cap["max_sustainable_debt"] = (
                max_leverage * ebitda if not math.isnan(ebitda) else float("nan")
            )
            debt_cap["leverage_headroom"] = (
                debt_cap["max_sustainable_debt"] - net_debt
                if not math.isnan(net_debt)
                else float("nan")
            )

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
            "cyclicality": "Unknown",
        }

        credit_fw = credit_framework.build_credit_assessment(
            co, period_ratios, flags, debt_cap, stress, refi, covenants, cashflow, sector_dict
        )

        # 6. LLM Memo
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
            "baseline_risk": baseline_risk,
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
            "all_ratios": period_ratios,
            "intelligence": intel_report,
        })

        my_bar.progress((idx + 1) / len(companies), text=f"Processed {ticker}...")

    my_bar.empty()
    st.session_state.analysis_results = results
    st.session_state.last_analysis_mode = analysis_mode
    st.session_state.last_sector_str = sector_str
    st.session_state.last_market_choice = market_choice


# ==========================================
# RESULTS WORKSPACE
# ==========================================
if "analysis_results" in st.session_state and st.session_state.analysis_results:
    results = st.session_state.analysis_results
    active_mode = st.session_state.get("last_analysis_mode", analysis_mode)
    active_sector = st.session_state.get("last_sector_str", sector_str)
    active_market = st.session_state.get("last_market_choice", market_choice)

    if active_mode.startswith("Sector") and results:
        st.markdown(
            f'<div class="rf-section-header">SECTOR COHORT OVERVIEW &mdash; {active_sector.upper()} ({active_market})</div>',
            unsafe_allow_html=True,
        )

        s_col1, s_col2, s_col3, s_col4 = st.columns(4)
        s_col1.metric("Issuers Evaluated", len(results))
        high_risk_count = sum(1 for r in results if r["risk"] in ["HIGH", "ELEVATED"])
        s_col2.metric("Elevated / High Risk Issuers", high_risk_count)
        det_count = sum(
            1
            for r in results
            if r.get("intelligence") and r["intelligence"].overall_trajectory == "DETERIORATING"
        )
        s_col3.metric("Deteriorating Trajectory", det_count)
        avg_z = pd.Series([r["ratios"].get("z_score", float("nan")) for r in results]).mean()
        s_col4.metric("Cohort Mean Altman Z", f"{avg_z:.2f}" if not math.isnan(avg_z) else "N/A")

        summary_data = []
        for r in results:
            z_score = r["ratios"].get("z_score", float("nan"))
            intel_obj = r.get("intelligence")
            summary_data.append({
                "Ticker": r["ticker"],
                "Baseline Risk": r.get("baseline_risk", r["risk"]),
                "Trend-Adjusted Risk": r["risk"],
                "Rating Action": intel_obj.risk_action if intel_obj else "MAINTAINED",
                "Trajectory": intel_obj.overall_trajectory if intel_obj else "N/A",
                "Deteriorating Metrics": len(intel_obj.deteriorating) if intel_obj else 0,
                "Net Debt / EBITDA (x)": round(r["ratios"].get("net_debt_ebitda", float("nan")), 2),
                "EBIT Coverage (x)": round(r["ratios"].get("ebit_coverage", float("nan")), 2),
                "Refinancing Risk": r["refi"].get("classification", "N/A"),
                "Altman Z-Score": round(z_score, 2) if not math.isnan(z_score) else "N/A",
            })

        st.dataframe(pd.DataFrame(summary_data).set_index("Ticker"), use_container_width=True)

    st.markdown(
        '<div class="rf-section-header">ISSUER CREDIT DOSSIER &amp; SQL TREND INTELLIGENCE</div>',
        unsafe_allow_html=True,
    )
    tabs = st.tabs([r["ticker"] for r in results])

    for i, r in enumerate(results):
        with tabs[i]:
            intel = r.get("intelligence")
            base_risk = r.get("baseline_risk", r["risk"])
            adj_risk = r["risk"]
            traj_label = intel.overall_trajectory if intel else "N/A"
            period_span = f"{intel.period_range} ({intel.total_periods}Y)" if intel else "Single Period"
            risk_act = intel.risk_action if intel else "MAINTAINED"
            refi_class = r["refi"].get("classification", "N/A")
            z_val = r["ratios"].get("z_score", float("nan"))
            z_zone = r["ratios"].get("z_score_zone", "N/A")
            z_disp = f"{z_val:.2f}" if not math.isnan(z_val) else "N/A"

            # Institutional 5-card Credit Scorecard Strip
            st.markdown(
                f"""
                <div class="rf-scorecard">
                    <div class="rf-card">
                        <div class="rf-card-label">Point-in-Time Risk</div>
                        <div class="rf-card-value"><span class="rf-badge rf-badge-{base_risk}">{base_risk}</span></div>
                        <div class="rf-card-sub">Latest Filing Ratios</div>
                    </div>
                    <div class="rf-card">
                        <div class="rf-card-label">Trend-Adjusted Risk</div>
                        <div class="rf-card-value">
                            <span class="rf-badge rf-badge-{adj_risk}">{adj_risk}</span>
                        </div>
                        <div class="rf-card-sub">{risk_act}</div>
                    </div>
                    <div class="rf-card">
                        <div class="rf-card-label">Historical Trajectory</div>
                        <div class="rf-card-value"><span class="rf-badge rf-badge-{traj_label}">{traj_label}</span></div>
                        <div class="rf-card-sub">{period_span}</div>
                    </div>
                    <div class="rf-card">
                        <div class="rf-card-label">Refinancing Risk</div>
                        <div class="rf-card-value"><span class="rf-badge rf-badge-{refi_class}">{refi_class}</span></div>
                        <div class="rf-card-sub">Rollover &amp; Debt Service</div>
                    </div>
                    <div class="rf-card">
                        <div class="rf-card-label">Altman Z-Score</div>
                        <div class="rf-card-value">{z_disp}</div>
                        <div class="rf-card-sub">Zone: {z_zone}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if intel:
                st.markdown(
                    f"""
                    <div class="rf-synthesis-box">
                        <strong>Risk Assessment &amp; Deterioration Synthesis ({intel.period_range}):</strong>
                        {intel.summary}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            subtabs = st.tabs([
                "Financial Intelligence & SQL",
                "Executive Credit Memo",
                "Fundamentals & Warnings",
                "Debt Capacity & Covenants",
                "Refinancing & Stress Testing",
            ])

            # ── TAB 0: FINANCIAL INTELLIGENCE & SQL ──────────────────────────
            with subtabs[0]:
                if intel is None:
                    st.info("Insufficient historical periods in SQL store for trend analysis (minimum 2 required).")
                else:
                    # 1. Deteriorating Metrics & Drivers Table
                    st.markdown(
                        '<div class="rf-section-header">DETERIORATING METRICS &amp; FUNDAMENTAL DRIVER ATTRIBUTION</div>',
                        unsafe_allow_html=True,
                    )
                    if intel.deteriorating:
                        det_rows = []
                        for alert in intel.deteriorating:
                            streak_txt = (
                                f"{alert.consecutive_periods}Y Consecutive"
                                if alert.consecutive_periods > 0
                                else "Multi-Period Net"
                            )
                            det_rows.append({
                                "Metric": alert.display_name,
                                "Signal": alert.severity,
                                "Pattern": streak_txt,
                                "Earliest": intelligence_report._fmt_val(alert.metric, alert.earliest_value),
                                "Latest": intelligence_report._fmt_val(alert.metric, alert.latest_value),
                                "Period Change": f"{alert.total_change_pct:+.1f}%" if alert.total_change_pct is not None else "N/A",
                                "Identified Fundamental Drivers": "; ".join(alert.drivers) if alert.drivers else "Combined numerator/denominator drift across periods",
                            })
                        st.dataframe(
                            pd.DataFrame(det_rows).set_index("Metric"),
                            use_container_width=True,
                        )
                    else:
                        st.caption("No material deteriorating credit ratios identified across the historical window.")

                    # 2. Improving & Stable Summary
                    col_imp, col_stb = st.columns([1.4, 1])
                    with col_imp:
                        st.markdown(
                            '<div class="rf-section-header">STRENGTHENING METRICS</div>',
                            unsafe_allow_html=True,
                        )
                        if intel.improving:
                            imp_rows = []
                            for alert in intel.improving:
                                imp_rows.append({
                                    "Metric": alert.display_name,
                                    "Periods Improved": f"{alert.consecutive_periods}Y",
                                    "Earliest": intelligence_report._fmt_val(alert.metric, alert.earliest_value),
                                    "Latest": intelligence_report._fmt_val(alert.metric, alert.latest_value),
                                    "Total Change": f"{alert.total_change_pct:+.1f}%" if alert.total_change_pct is not None else "N/A",
                                })
                            st.dataframe(pd.DataFrame(imp_rows).set_index("Metric"), use_container_width=True)
                        else:
                            st.caption("No metrics exhibited multi-period improvement above the 5% materiality threshold.")

                    with col_stb:
                        st.markdown(
                            '<div class="rf-section-header">STABLE METRICS (&lt;5% VARIANCE)</div>',
                            unsafe_allow_html=True,
                        )
                        if intel.stable:
                            st.write(", ".join(intel.stable))
                        else:
                            st.caption("All tracked credit ratios moved by more than 5% over the analysis horizon.")

                    # 3. Historical SQL Ratio Matrix & Chart
                    raw_history = db_manager.get_ticker_history(r["ticker"])
                    history = [
                        h for h in raw_history
                        if any(h.get(k) is not None for k in ("revenue", "ebitda", "total_assets", "total_debt"))
                    ]
                    if history:
                        st.markdown(
                            '<div class="rf-section-header">HISTORICAL FINANCIAL &amp; RATIO MATRIX (SQL STORE)</div>',
                            unsafe_allow_html=True,
                        )
                        hist_df = pd.DataFrame(history)
                        matrix_cols = [
                            ("period_year", "Fiscal Year"),
                            ("revenue", "Revenue ($B)"),
                            ("ebitda", "EBITDA ($B)"),
                            ("total_debt", "Total Debt ($B)"),
                            ("fcf", "Free Cash Flow ($B)"),
                            ("debt_ebitda", "Debt / EBITDA (x)"),
                            ("net_debt_ebitda", "Net Debt / EBITDA (x)"),
                            ("ebit_coverage", "EBIT Coverage (x)"),
                            ("ebitda_margin", "EBITDA Margin (%)"),
                            ("current_ratio", "Current Ratio (x)"),
                            ("z_score", "Altman Z-Score"),
                        ]
                        avail_cols = [c[0] for c in matrix_cols if c[0] in hist_df.columns]
                        display_df = hist_df[avail_cols].copy()
                        for b_col in ["revenue", "ebitda", "total_debt", "fcf"]:
                            if b_col in display_df.columns:
                                display_df[b_col] = (pd.to_numeric(display_df[b_col], errors="coerce") / 1e9).round(2)
                        for r_col in ["debt_ebitda", "net_debt_ebitda", "ebit_coverage", "ebitda_margin", "current_ratio", "z_score"]:
                            if r_col in display_df.columns:
                                display_df[r_col] = pd.to_numeric(display_df[r_col], errors="coerce").round(2)
                        rename_map = dict(matrix_cols)
                        display_df = display_df.rename(columns=rename_map).set_index("Fiscal Year")
                        st.dataframe(display_df, use_container_width=True)

                        st.markdown(
                            '<div class="rf-section-header">MULTI-PERIOD RATIO TRAJECTORY CHART</div>',
                            unsafe_allow_html=True,
                        )
                        chart_metrics = st.multiselect(
                            "Select ratios to plot across fiscal periods",
                            options=[
                                "debt_ebitda",
                                "net_debt_ebitda",
                                "ebit_coverage",
                                "ebitda_coverage",
                                "current_ratio",
                                "z_score",
                                "ebitda_margin",
                                "fcf_margin",
                                "roce",
                            ],
                            default=["debt_ebitda", "ebit_coverage", "z_score"],
                            key=f"chart_metrics_{r['ticker']}",
                        )
                        if chart_metrics:
                            chart_data = hist_df[["period_year"] + chart_metrics].dropna(subset=["period_year"]).copy()
                            for cm in chart_metrics:
                                chart_data[cm] = pd.to_numeric(chart_data[cm], errors="coerce")
                            chart_data["period_year"] = chart_data["period_year"].astype(str)
                            chart_data = chart_data.set_index("period_year")
                            st.line_chart(chart_data)

                    # 4. SQL Analytics Workbench
                    st.markdown(
                        '<div class="rf-section-header">SQL ANALYTICS WORKBENCH (TABLE: ratio_snapshots)</div>',
                        unsafe_allow_html=True,
                    )
                    preset_queries = {
                        "Issuer Multi-Period Credit History": (
                            f"SELECT period_year, ROUND(revenue/1e9, 2) AS revenue_bn, "
                            f"ROUND(ebitda/1e9, 2) AS ebitda_bn, ROUND(total_debt/1e9, 2) AS debt_bn, "
                            f"ROUND(debt_ebitda, 2) AS debt_ebitda, ROUND(ebit_coverage, 2) AS ebit_cov, "
                            f"ROUND(z_score, 2) AS z_score, risk_rating "
                            f"FROM ratio_snapshots WHERE ticker = '{r['ticker']}' ORDER BY period_year ASC"
                        ),
                        "Year-over-Year Leverage & Coverage Deterioration": (
                            f"SELECT cur.period_year AS year, "
                            f"ROUND(prev.debt_ebitda, 2) AS prior_leverage, "
                            f"ROUND(cur.debt_ebitda, 2) AS current_leverage, "
                            f"ROUND(cur.debt_ebitda - prev.debt_ebitda, 2) AS leverage_delta, "
                            f"ROUND(cur.ebit_coverage - prev.ebit_coverage, 2) AS coverage_delta "
                            f"FROM ratio_snapshots cur "
                            f"JOIN ratio_snapshots prev ON cur.ticker = prev.ticker AND cur.period_year = prev.period_year + 1 "
                            f"WHERE cur.ticker = '{r['ticker']}' ORDER BY cur.period_year ASC"
                        ),
                        "All Stored Issuers — Latest Snapshot Ranking": (
                            "SELECT ticker, sector, period_year, "
                            "ROUND(debt_ebitda, 2) AS debt_ebitda, "
                            "ROUND(ebit_coverage, 2) AS ebit_coverage, "
                            "ROUND(z_score, 2) AS z_score, risk_rating "
                            "FROM ratio_snapshots r1 "
                            "WHERE period_year = (SELECT MAX(period_year) FROM ratio_snapshots r2 WHERE r2.ticker = r1.ticker) "
                            "ORDER BY debt_ebitda DESC"
                        ),
                    }
                    selected_preset = st.selectbox(
                        "Analytical Query Template",
                        list(preset_queries.keys()),
                        key=f"sql_preset_{r['ticker']}",
                    )
                    user_query = st.text_area(
                        "SQL Statement (Read-Only SELECT / WITH)",
                        value=preset_queries[selected_preset],
                        height=95,
                        key=f"sql_query_{r['ticker']}_{selected_preset}",
                    )
                    if st.button("Execute SQL Query", key=f"run_sql_{r['ticker']}"):
                        try:
                            results_sql = db_manager.run_custom_query(user_query)
                            if results_sql:
                                st.dataframe(pd.DataFrame(results_sql), use_container_width=True)
                            else:
                                st.info("Query executed successfully (0 rows returned).")
                        except Exception as e:
                            st.error(f"SQL Execution Error: {e}")

            # ── TAB 1: EXECUTIVE CREDIT MEMO ─────────────────────────────────
            with subtabs[1]:
                st.markdown(r["memo"])

            # ── TAB 2: FUNDAMENTALS & WARNINGS ───────────────────────────────
            with subtabs[2]:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(
                        '<div class="rf-section-header">CREDIT STRENGTHS</div>',
                        unsafe_allow_html=True,
                    )
                    strengths = r["credit_fw"].get("financial_strengths", {}).get("items", [])
                    if strengths:
                        for s in strengths:
                            st.markdown(f"- {s}")
                    else:
                        st.caption("No distinct quantitative credit strengths flagged.")
                with c2:
                    st.markdown(
                        '<div class="rf-section-header">CREDIT WEAKNESSES</div>',
                        unsafe_allow_html=True,
                    )
                    weaknesses = r["credit_fw"].get("financial_weaknesses", {}).get("items", [])
                    if weaknesses:
                        for w in weaknesses:
                            st.markdown(f"- {w}")
                    else:
                        st.caption("No material credit weaknesses flagged.")

                st.markdown(
                    '<div class="rf-section-header">POINT-IN-TIME &amp; TREND EARLY-WARNING SIGNALS</div>',
                    unsafe_allow_html=True,
                )
                if not r["flags"]:
                    st.caption("No threshold breaches detected.")
                else:
                    flag_rows = [
                        {
                            "Severity": f.severity,
                            "Category": f.category,
                            "Metric": f.metric,
                            "Assessment": f.message,
                        }
                        for f in r["flags"]
                    ]
                    st.dataframe(pd.DataFrame(flag_rows).set_index("Severity"), use_container_width=True)

                st.markdown(
                    '<div class="rf-section-header">HISTORICAL SCALE &amp; LEVERAGE ($B)</div>',
                    unsafe_allow_html=True,
                )
                periods = list(r["all_ratios"].keys())[::-1]
                chart_df = pd.DataFrame({
                    "Period": periods,
                    "Revenue ($B)": [r["all_ratios"][p].get("revenue", 0) / 1e9 for p in periods],
                    "EBITDA ($B)": [r["all_ratios"][p].get("ebitda", 0) / 1e9 for p in periods],
                    "Total Debt ($B)": [r["all_ratios"][p].get("total_debt", 0) / 1e9 for p in periods],
                }).set_index("Period")
                ch1, ch2 = st.columns(2)
                with ch1:
                    st.bar_chart(chart_df[["Revenue ($B)", "EBITDA ($B)"]])
                with ch2:
                    st.line_chart(chart_df[["Total Debt ($B)"]])

            # ── TAB 3: DEBT CAPACITY & COVENANTS ─────────────────────────────
            with subtabs[3]:
                dc = r["debt_cap"]
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(
                        '<div class="rf-section-header">ILLUSTRATIVE DEBT CAPACITY</div>',
                        unsafe_allow_html=True,
                    )
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Max Net Leverage Cap", f"{max_leverage:.1f}x")
                    m2.metric("Current Net Leverage", f"{dc.get('current_net_leverage', float('nan')):.2f}x")
                    m3.metric("Net Debt Headroom", f"${dc.get('leverage_headroom', 0)/1e9:.2f}B")
                with c2:
                    st.markdown(
                        '<div class="rf-section-header">ILLUSTRATIVE COVENANT COMPLIANCE</div>',
                        unsafe_allow_html=True,
                    )
                    cov_df = pd.DataFrame(r["covenants"].get("covenants", []))
                    if not cov_df.empty:
                        st.dataframe(
                            cov_df[["metric", "current_value", "threshold", "status"]],
                            hide_index=True,
                            use_container_width=True,
                        )
                    else:
                        st.caption("No covenant data available.")

            # ── TAB 4: REFINANCING & STRESS TESTING ──────────────────────────
            with subtabs[4]:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(
                        '<div class="rf-section-header">REFINANCING RISK DRIVERS</div>',
                        unsafe_allow_html=True,
                    )
                    refi_factors = r["refi"].get("factors", [])
                    if refi_factors:
                        st.dataframe(
                            pd.DataFrame(refi_factors)[["name", "status", "reason"]].rename(
                                columns={"name": "Factor", "status": "Risk Level", "reason": "Analytical Basis"}
                            ),
                            hide_index=True,
                            use_container_width=True,
                        )
                with c2:
                    st.markdown(
                        '<div class="rf-section-header">DOWNSIDE STRESS SCENARIOS</div>',
                        unsafe_allow_html=True,
                    )
                    stress_data = []
                    for s_key in ["base", "moderate", "severe"]:
                        s = r["stress"].get(s_key, {})
                        if s:
                            stress_data.append({
                                "Scenario": s.get("label", s_key),
                                "Stressed Debt / EBITDA": f"{s.get('stressed_debt_ebitda', float('nan')):.2f}x",
                                "Stressed EBIT Coverage": f"{s.get('stressed_ebit_coverage', float('nan')):.2f}x",
                            })
                    st.dataframe(pd.DataFrame(stress_data), hide_index=True, use_container_width=True)
