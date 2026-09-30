"""
main.py
Orchestrator -- runs the full defense credit analysis pipeline:
  1. Fetch data (yfinance)
  2. Compute ratios (including Altman Z, FCC, fixed denoms)
  3. Generate credit flags
  4. Run Advanced Analytics (Debt Capacity, Stress Testing, Cash Flow, Refinancing, Covenants, Sector, Credit Framework)
  5. Draft AI credit memos (Gemini)
  6. Render HTML dashboard
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

# ---- Logging setup (UTF-8 safe) --------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
logger = logging.getLogger("main")

# ---- Project imports -------------------------------------------------------
from config import COMPANIES, OUTPUT_DIR, STRESS_SCENARIOS, PROJECTION_ASSUMPTIONS, COVENANT_THRESHOLDS
from data_fetcher import fetch_all
from ratio_engine import compute_all_ratios
from signal_flags import analyze_flags, overall_risk_rating
from memo_generator import generate_memo
from report import generate_html

# Optional advanced modules (we import dynamically or safely to allow partial failures)
try:
    from debt_capacity import compute_debt_capacity as calculate_debt_capacity
except ImportError:
    calculate_debt_capacity = None

try:
    from stress_engine import run_stress_scenarios
except ImportError:
    run_stress_scenarios = None

try:
    from refinancing_risk import assess_refinancing_risk
except ImportError:
    assess_refinancing_risk = None

try:
    from covenant_monitor import analyze_covenants
except ImportError:
    analyze_covenants = None

try:
    from cashflow_model import model_cashflows
except ImportError:
    model_cashflows = None

try:
    from credit_framework import build_credit_assessment
except ImportError:
    build_credit_assessment = None

try:
    from sector_overlay import get_sector_info
except ImportError:
    get_sector_info = None


def run_pipeline(skip_memo: bool = False) -> None:
    """
    Full analysis pipeline.
    """
    logger.info("=" * 60)
    logger.info("Defense Sector Credit Analysis -- Starting Pipeline")
    logger.info("Companies: %d", len(COMPANIES))
    logger.info("=" * 60)

    # ---- Step 1: Fetch Data ------------------------------------------------
    logger.info("Step 1: Fetching financial data from yfinance...")
    raw_data_map = fetch_all(COMPANIES)

    # ---- Step 2-5: Per-company analysis ------------------------------------
    results: list[dict] = []

    for co in COMPANIES:
        ticker = co["ticker"]
        name   = co["name"]
        raw    = raw_data_map.get(ticker)

        if raw is None:
            logger.warning("[%s] No data -- skipping.", ticker)
            continue

        # Step 2: Compute ratios
        logger.info("[%s] Computing ratios...", name)
        try:
            period_ratios = compute_all_ratios(raw, raw["periods"])
        except Exception as e:
            logger.error("[%s] Ratio engine failed: %s", name, e)
            continue
            
        ordered_periods = list(period_ratios.keys())
        latest_period = ordered_periods[0] if ordered_periods else None
        ttm_ratios = period_ratios.get(latest_period, {}) if latest_period else {}

        # Step 3: Generate flags
        logger.info("[%s] Running early-warning checks...", name)
        flags = analyze_flags(period_ratios, name)
        z = ttm_ratios.get("z_score", float("nan"))
        risk = overall_risk_rating(flags, z)

        # Step 4: Advanced Analytics
        logger.info("[%s] Running advanced analytical modules...", name)
        debt_cap, stress, refi, covenants, cashflow, sector, credit_fw = {}, {}, {}, {}, {}, {}, {}

        if calculate_debt_capacity:
            try:
                debt_cap = calculate_debt_capacity(ttm_ratios)
            except Exception as e:
                logger.error("[%s] Debt capacity failed: %s", name, e)

        if run_stress_scenarios:
            try:
                stress = run_stress_scenarios(ttm_ratios, raw, STRESS_SCENARIOS)
            except Exception as e:
                logger.error("[%s] Stress engine failed: %s", name, e)

        if assess_refinancing_risk:
            try:
                refi = assess_refinancing_risk(ttm_ratios)
            except Exception as e:
                logger.error("[%s] Refinancing risk failed: %s", name, e)

        if analyze_covenants:
            try:
                covenants = analyze_covenants(period_ratios, COVENANT_THRESHOLDS)
            except Exception as e:
                logger.error("[%s] Covenant monitor failed: %s", name, e)

        if model_cashflows:
            try:
                cashflow = model_cashflows(raw, raw["periods"], PROJECTION_ASSUMPTIONS)
            except Exception as e:
                logger.error("[%s] Cashflow model failed: %s", name, e)

        if get_sector_info:
            try:
                sector = get_sector_info(ticker)
            except Exception as e:
                logger.error("[%s] Sector overlay failed: %s", name, e)

        if build_credit_assessment:
            try:
                credit_fw = build_credit_assessment(
                    company=co,
                    period_ratios=period_ratios,
                    flags=flags,
                    debt_capacity=debt_cap,
                    stress_results=stress,
                    refinancing=refi,
                    covenants=covenants,
                    cashflow=cashflow,
                    sector_info=sector
                )
            except Exception as e:
                logger.error("[%s] Credit framework failed: %s", name, e)
                traceback.print_exc()

        # Step 5: LLM credit memo
        if skip_memo:
            memo_text = "[Memo generation skipped -- set skip_memo=False or provide GEMINI_API_KEY]"
            logger.info("[%s] Memo skipped.", name)
        else:
            logger.info("[%s] Generating Gemini credit memo...", name)
            memo_text = generate_memo(
                company=co,
                period_ratios=period_ratios,
                flags=flags,
                debt_cap=debt_cap,
                stress=stress,
                refi=refi,
                covenants=covenants,
                cashflow=cashflow,
                sector=sector,
                credit_fw=credit_fw
            )

        # Summary log
        n_crit = sum(1 for f in flags if f.severity == "CRITICAL")
        n_warn = sum(1 for f in flags if f.severity == "WARNING")
        logger.info(
            "   -> Risk: %s | Flags: %d critical, %d warning | Z-Score: %.2f",
            risk, n_crit, n_warn, z if z == z else -1,
        )

        results.append({
            "company":      co,
            "period_ratios": period_ratios,
            "flags":        flags,
            "memo_text":    memo_text,
            "debt_cap":     debt_cap,
            "stress":       stress,
            "refi":         refi,
            "covenants":    covenants,
            "cashflow":     cashflow,
            "sector":       sector,
            "credit_fw":    credit_fw,
        })

    # ---- Step 6: Generate HTML dashboard -----------------------------------
    logger.info("Step 6: Rendering HTML dashboard...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html_path = os.path.join(OUTPUT_DIR, "defense_credit_dashboard.html")
    generate_html(results, html_path)

    # ---- Final summary -----------------------------------------------------
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE -- Summary")
    logger.info("=" * 60)
    
    # We use the new risk_rating directly
    high_risk = [
        r["company"]["name"] for r in results
        if overall_risk_rating(
            r["flags"],
            r["period_ratios"].get(list(r["period_ratios"].keys())[0], {}).get("z_score", float("nan")) if r["period_ratios"] else float("nan")
        ) in ("HIGH", "ELEVATED")
    ]
    logger.info("Companies analyzed : %d", len(results))
    logger.info("High/Elevated risk : %d -- %s", len(high_risk), ", ".join(high_risk) or "None")
    total_critical = sum(
        sum(1 for f in r["flags"] if f.severity == "CRITICAL") for r in results
    )
    logger.info("Total critical flags: %d", total_critical)
    logger.info("HTML dashboard     : %s", os.path.abspath(html_path))
    logger.info("=" * 60)

    # Print a quick console table
    print("\n+---------------------------+------------+------------+----------+------------+")
    print("|  Company                  |  Risk      | Debt/EBITDA| Int. Cov |  Z-Score   |")
    print("+---------------------------+------------+------------+----------+------------+")
    for r in results:
        co    = r["company"]
        ordered = list(r["period_ratios"].keys())
        ttm   = r["period_ratios"].get(ordered[0], {}) if ordered else {}
        z     = ttm.get("z_score", float("nan"))
        risk  = overall_risk_rating(r["flags"], z)
        de    = ttm.get("debt_ebitda", float("nan"))
        ic    = ttm.get("ebit_coverage", float("nan"))
        de_s  = f"{de:.1f}x" if de == de else "N/A"
        ic_s  = f"{ic:.1f}x" if ic == ic else "N/A"
        z_s   = f"{z:.2f}"   if z  == z  else "N/A"
        print(f"|  {co['name']:<25s} | {risk:<10s} | {de_s:<10s} | {ic_s:<8s} | {z_s:<10s} |")
    print("+---------------------------+------------+------------+----------+------------+")
    print(f"\nOpen: {os.path.abspath(html_path)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-memo", action="store_true", help="Skip LLM credit memo generation")
    args = parser.parse_args()

    run_pipeline(skip_memo=args.no_memo)
