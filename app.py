from pathlib import Path

source = Path("/mnt/data/Pasted code.py").read_text()

# Locate the major sections in the supplied app.py.
session_start = source.index("# --- SESSION STATE INITIALIZATION ---")
sidebar_start = source.index("    # --- Sidebar ---", session_start)
main_start = source.index("    # --- Main Content UI ---", sidebar_start)

# Everything before the old login/session state stays unchanged.
head = source[:session_start]

secure_preamble = r'''
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
'''

sidebar = r'''# --- Sidebar ---
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

'''

# Extract the original main dashboard and remove its old four-space indentation.
dashboard_source = source[main_start:]
dashboard = "\n".join(
    line[4:] if line.startswith("    ") else line
    for line in dashboard_source.splitlines()
)

# Replace the direct LLM call with the protected wrapper.
old_call = '''memo = memo_generator.generate_memo(co, period_ratios, flags, debt_cap, stress, refi, covenants, cashflow, sector_dict, credit_fw)'''
new_call = '''memo = generate_protected_memo(
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
                )'''

if old_call not in dashboard:
    raise ValueError("Could not locate the original Gemini memo call in app.py.")

dashboard = dashboard.replace(old_call, new_call, 1)

# Rebrand the browser/tab title.
head = head.replace(
    'st.set_page_config(page_title="Corporate Credit Risk Agent", layout="wide", page_icon="🛡️")',
    'st.set_page_config(page_title="RiskForge — Credit Intelligence", layout="wide", page_icon="🛡️")',
)

# Rebrand the main dashboard title.
dashboard = dashboard.replace(
    'st.title("📊 Global Credit Analysis Hub")',
    'st.title("🛡️ RiskForge — Global Credit Intelligence")',
    1,
)

final_code = head + secure_preamble + sidebar + dashboard + "\n"

# Validate syntax.
compile(final_code, "/mnt/data/RiskForge_app.py", "exec")

out = Path("/mnt/data/RiskForge_app.py")
out.write_text(final_code)

print(f"Created: {out}")
print(f"Lines: {len(final_code.splitlines())}")
