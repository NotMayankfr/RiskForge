"""
report.py
Generates a self-contained HTML dashboard from all company results.
Upgraded to support Advanced Analytics, Chart.js, and detailed sub-sections.
"""

from __future__ import annotations

import math
import os
import json
from datetime import datetime
from typing import Any

from config import GEMINI_MODEL
from signal_flags import CreditFlag, overall_risk_rating


def _fmt(v: float, decimals: int = 2, suffix: str = "") -> str:
    if math.isnan(v) or v is None:
        return "—"
    return f"{v:,.{decimals}f}{suffix}"


def _fmt_bn(v: float) -> str:
    if math.isnan(v) or v is None:
        return "—"
    return f"${v / 1e9:,.2f}B"


def _risk_badge(rating: str) -> str:
    colors = {
        "HIGH":     ("#dc2626", "#fef2f2"),
        "ELEVATED": ("#d97706", "#fffbeb"),
        "MODERATE": ("#2563eb", "#eff6ff"),
        "LOW":      ("#16a34a", "#f0fdf4"),
    }
    fg, bg = colors.get(rating, ("#6b7280", "#f9fafb"))
    return (
        f'<span class="risk-badge" style="background:{bg};color:{fg};'
        f'border:1px solid {fg};">{rating}</span>'
    )


def _z_badge(z: float, label: str = "") -> str:
    if "DISTRESS" in label:
        return f'<span class="z-badge z-distress">{_fmt(z, 2)} {label}</span>'
    if "GREY" in label:
        return f'<span class="z-badge z-grey">{_fmt(z, 2)} {label}</span>'
    if "SAFE" in label:
        return f'<span class="z-badge z-safe">{_fmt(z, 2)} {label}</span>'
    return f'<span class="z-badge">{label}</span>'


def _severity_icon(sev: str) -> str:
    return {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "ℹ️"}.get(sev, "")


def _generate_company_card(r: dict) -> str:
    co = r["company"]
    ordered_periods = list(r["period_ratios"].keys())
    latest = r["period_ratios"].get(ordered_periods[0], {}) if ordered_periods else {}
    flags = r["flags"]
    memo = r.get("memo_text", "")
    debt_cap = r.get("debt_cap", {})
    stress = r.get("stress", {})
    refi = r.get("refi", {})
    covenants = r.get("covenants", {})
    cashflow = r.get("cashflow", {})
    sector = r.get("sector", {})
    credit_fw = r.get("credit_fw", {})
    
    z = latest.get("z_score", float("nan"))
    risk = overall_risk_rating(flags, z)
    
    # ── Overview Tab ──
    strengths = credit_fw.get("financial_strengths", {}).get("items", []) if credit_fw else []
    weaknesses = credit_fw.get("financial_weaknesses", {}).get("items", []) if credit_fw else []
    view = credit_fw.get("overall_credit_view", "N/A") if credit_fw else "N/A"
    
    flag_html = "".join(f'<div class="flag flag-{f.severity.lower()}">{_severity_icon(f.severity)} <strong>[{f.category}]</strong> {f.message}</div>' for f in flags)
    if not flag_html: flag_html = '<div class="flag flag-ok">✅ No material credit flags.</div>'
    
    # ── Chart Data ──
    labels = ordered_periods[::-1] # oldest to newest
    rev_data = json.dumps([r["period_ratios"][p].get("revenue", float("nan")) / 1e9 for p in labels])
    ebitda_data = json.dumps([r["period_ratios"][p].get("ebitda", float("nan")) / 1e9 for p in labels])
    de_data = json.dumps([r["period_ratios"][p].get("debt_ebitda", float("nan")) for p in labels])
    
    # ── Covenants ──
    cov_rows = ""
    for c in covenants.get("covenants", []):
        stat_cls = "cov-breach" if c.get("status") == "BREACH" else "cov-tight" if c.get("status") == "TIGHT" else "cov-ok"
        cov_rows += f'''
        <tr>
            <td>{c.get('metric','')}</td>
            <td>{_fmt(c.get('current_value', float('nan')))}</td>
            <td>{_fmt(c.get('threshold', float('nan')))}</td>
            <td>{_fmt(c.get('headroom', float('nan')))}</td>
            <td><span class="{stat_cls}">{c.get('status','N/A')}</span></td>
        </tr>'''
        
    # ── Cash flow projection ──
    cf_proj_rows = ""
    for p in cashflow.get("projection", []):
        cf_proj_rows += f'''
        <tr>
            <td>{p.get('year')}</td>
            <td>{_fmt_bn(p.get('projected_revenue', float('nan')))}</td>
            <td>{_fmt_bn(p.get('projected_ebitda', float('nan')))}</td>
            <td>{_fmt_bn(p.get('projected_capex', float('nan')))}</td>
            <td>{_fmt_bn(p.get('projected_fcf', float('nan')))}</td>
        </tr>'''
        
    # ── Stress Testing ──
    stress_rows = ""
    for s_name in ["base", "moderate", "severe"]:
        s_data = stress.get(s_name, {})
        if not s_data: continue
        stress_rows += f'''
        <tr>
            <td>{s_data.get('label', s_name)}</td>
            <td>{_fmt_bn(s_data.get('stressed_revenue', float('nan')))}</td>
            <td>{_fmt_bn(s_data.get('stressed_ebitda', float('nan')))}</td>
            <td>{_fmt(s_data.get('stressed_debt_ebitda', float('nan')), 2, 'x')}</td>
            <td>{_fmt(s_data.get('stressed_ebit_coverage', float('nan')), 2, 'x')}</td>
        </tr>'''

    html = f'''
    <div class="company-card" id="card-{co["ticker"]}">
      <div class="card-header">
        <div class="card-title-block">
          <h2>{co["name"]}</h2>
          <span class="ticker-tag">{co["ticker"]}</span>
          <span class="country-tag">{co["country"]} · {sector.get('sector', 'Defense')}</span>
        </div>
        <div class="card-risk-block">
          {_risk_badge(risk)}
        </div>
      </div>

      <div class="card-body">
        <div class="tab-bar">
          <button class="tab-btn active" onclick="showTab(event, 'overview-{co["ticker"]}')">Overview & Ratios</button>
          <button class="tab-btn" onclick="showTab(event, 'debt-{co["ticker"]}')">Debt Capacity & Covenants</button>
          <button class="tab-btn" onclick="showTab(event, 'cash-{co["ticker"]}')">Cash Flow & Refinancing</button>
          <button class="tab-btn" onclick="showTab(event, 'stress-{co["ticker"]}')">Stress Testing</button>
          <button class="tab-btn" onclick="showTab(event, 'memo-{co["ticker"]}')">📝 AI Credit Memo</button>
        </div>
        
        <div class="tab-content">
          <!-- Overview Tab -->
          <div class="tab-pane active" id="overview-{co["ticker"]}">
            <div class="grid-2">
              <div>
                <h3>Sector & View</h3>
                <p><strong>Primary Customer:</strong> {sector.get('primary_customer','N/A')}</p>
                <p><strong>Revenue Visibility:</strong> {sector.get('revenue_visibility','N/A')}</p>
                <p><strong>Credit View:</strong> {view}</p>
                <br>
                <h3>Strengths & Weaknesses</h3>
                <ul class="sw-list">
                  {''.join(f'<li class="pos">{s}</li>' for s in strengths)}
                  {''.join(f'<li class="neg">{w}</li>' for w in weaknesses)}
                </ul>
              </div>
              <div>
                <h3>Early Warning Flags</h3>
                <div class="flags-container">{flag_html}</div>
              </div>
            </div>
            
            <h3 style="margin-top:20px;">Financial Trends</h3>
            <div class="grid-2">
                <canvas id="chart-rev-{co['ticker']}" height="100"></canvas>
                <canvas id="chart-lev-{co['ticker']}" height="100"></canvas>
            </div>
            <script>
                document.addEventListener('DOMContentLoaded', function() {{
                    new Chart(document.getElementById('chart-rev-{co['ticker']}'), {{
                        type: 'bar',
                        data: {{ labels: {json.dumps(labels)}, datasets: [
                            {{ label: 'Revenue ($B)', data: {rev_data}, backgroundColor: '#3b82f6' }},
                            {{ label: 'EBITDA ($B)', data: {ebitda_data}, backgroundColor: '#10b981' }}
                        ]}}
                    }});
                    new Chart(document.getElementById('chart-lev-{co['ticker']}'), {{
                        type: 'line',
                        data: {{ labels: {json.dumps(labels)}, datasets: [
                            {{ label: 'Debt/EBITDA (x)', data: {de_data}, borderColor: '#ef4444', backgroundColor: 'transparent' }}
                        ]}}
                    }});
                }});
            </script>
          </div>
          
          <!-- Debt Capacity Tab -->
          <div class="tab-pane" id="debt-{co["ticker"]}">
            <div class="grid-2">
                <div>
                    <h3>Debt Capacity (Illustrative)</h3>
                    <table class="ratio-table">
                        <tr><td>Max Net Leverage Assumption</td><td>{debt_cap.get('assumptions',{}).get('max_net_leverage','N/A')}x</td></tr>
                        <tr><td>Current Net Leverage</td><td>{_fmt(debt_cap.get('current_net_leverage', float('nan')), 2, 'x')}</td></tr>
                        <tr><td>Max Sustainable Debt</td><td>{_fmt_bn(debt_cap.get('max_sustainable_debt', float('nan')))}</td></tr>
                        <tr><td>Leverage Headroom</td><td>{_fmt_bn(debt_cap.get('leverage_headroom', float('nan')))}</td></tr>
                        <tr><td>Binding Constraint</td><td>{debt_cap.get('binding_constraint','N/A')}</td></tr>
                    </table>
                </div>
                <div>
                    <h3>Illustrative Covenants</h3>
                    <p style="font-size:0.8rem; color:#94a3b8; margin-bottom:10px;">Not actual legal covenants.</p>
                    <table class="ratio-table">
                        <thead><tr><th>Metric</th><th>Current</th><th>Threshold</th><th>Headroom</th><th>Status</th></tr></thead>
                        <tbody>{cov_rows}</tbody>
                    </table>
                </div>
            </div>
          </div>
          
          <!-- Cash Flow Tab -->
          <div class="tab-pane" id="cash-{co["ticker"]}">
            <div class="grid-2">
                <div>
                    <h3>Refinancing Risk</h3>
                    <p><strong>Classification:</strong> {_risk_badge(refi.get('classification','N/A'))}</p>
                    <p style="margin-top:10px; font-size:0.9rem;">{refi.get('overall_reason','N/A')}</p>
                    <ul class="sw-list" style="margin-top:10px;">
                        {''.join(f'<li>{f.get("name")}: {f.get("status")} - {f.get("reason")}</li>' for f in refi.get("factors", []))}
                    </ul>
                    <p style="font-size:0.8rem; color:#94a3b8; margin-top:10px;">Note: {refi.get('maturity_note','')}</p>
                </div>
                <div>
                    <h3>Cash Flow Projections</h3>
                    <table class="ratio-table">
                        <thead><tr><th>Year</th><th>Revenue</th><th>EBITDA</th><th>Capex</th><th>FCF</th></tr></thead>
                        <tbody>{cf_proj_rows}</tbody>
                    </table>
                </div>
            </div>
          </div>
          
          <!-- Stress Testing Tab -->
          <div class="tab-pane" id="stress-{co["ticker"]}">
            <h3>Stress Scenarios</h3>
            <table class="ratio-table">
                <thead><tr><th>Scenario</th><th>Revenue</th><th>EBITDA</th><th>Debt/EBITDA</th><th>Coverage</th></tr></thead>
                <tbody>{stress_rows}</tbody>
            </table>
          </div>
          
          <!-- Memo Tab -->
          <div class="tab-pane" id="memo-{co["ticker"]}">
            <div class="memo-section">
                <div class="memo-body">{memo.replace("<", "&lt;").replace(">", "&gt;").replace(chr(10), "<br>")}</div>
            </div>
          </div>
          
        </div>
      </div>
    </div>
    '''
    return html


def _generate_summary_table(results: list[dict]) -> str:
    rows = ""
    for r in results:
        co    = r["company"]
        ordered = list(r["period_ratios"].keys())
        ttm   = r["period_ratios"].get(ordered[0], {}) if ordered else {}
        flags = r["flags"]
        z     = ttm.get("z_score", float("nan"))
        z_label = ttm.get("z_score_zone", "")
        risk  = overall_risk_rating(flags, z)
        refi  = r.get("refi", {}).get("classification", "N/A")
        
        rows += f'''
        <tr onclick="document.getElementById('card-{co["ticker"]}').scrollIntoView({{behavior:'smooth'}})">
          <td><strong>{co["name"]}</strong><br><small>{co["ticker"]} · {co["country"]}</small></td>
          <td>{_risk_badge(risk)}</td>
          <td class="num">{_fmt(ttm.get("debt_ebitda", float("nan")), 1, "x")}</td>
          <td class="num">{_fmt(ttm.get("ebit_coverage", float("nan")), 1, "x")}</td>
          <td class="num">{_fmt(ttm.get("fcf", float("nan"))/1e9, 2, "B")}</td>
          <td class="num">{_z_badge(z, z_label)}</td>
          <td>{_risk_badge(refi)}</td>
        </tr>'''

    return f'''
    <table class="summary-table">
      <thead>
        <tr>
          <th>Company</th>
          <th>Overall Risk</th>
          <th>Debt/EBITDA</th>
          <th>Int. Coverage</th>
          <th>FCF ($B)</th>
          <th>Z-Score</th>
          <th>Refi Risk</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>'''


def generate_html(results: list[dict], output_path: str) -> None:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    n_companies = len(results)
    n_high = sum(1 for r in results if overall_risk_rating(r["flags"], r["period_ratios"].get(list(r["period_ratios"].keys())[0], {}).get("z_score", float("nan")) if r["period_ratios"] else float("nan")) in ("HIGH", "ELEVATED"))
    
    cards_html = "\n".join(_generate_company_card(r) for r in results)
    summary_table = _generate_summary_table(results)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Defense Sector Credit Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
/* ── Reset & Base ── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e2e8f0; line-height: 1.6; }}
a {{ color: #60a5fa; text-decoration: none; }}
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}

/* ── Header ── */
.site-header {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-bottom: 2px solid #334155; padding: 24px 40px; display: flex; align-items: center; justify-content: space-between; }}
.site-header h1 {{ font-size: 1.6rem; font-weight: 700; color: #f1f5f9; }}
.site-header h1 span {{ color: #60a5fa; }}
.header-meta {{ font-size: 0.8rem; color: #94a3b8; text-align: right; }}

/* ── Stats Bar ── */
.stats-bar {{ background: #1e293b; padding: 16px 40px; display: flex; gap: 32px; border-bottom: 1px solid #334155; }}
.stat {{ text-align: center; }}
.stat-val {{ font-size: 1.8rem; font-weight: 700; color: #60a5fa; }}
.stat-label {{ font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }}

/* ── Container ── */
.container {{ max-width: 1400px; margin: 0 auto; padding: 32px 40px; }}

/* ── Summary Table ── */
.summary-section {{ margin-bottom: 40px; }}
.summary-section h2 {{ font-size: 1.2rem; color: #f1f5f9; margin-bottom: 12px; }}
.summary-table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 12px; overflow: hidden; }}
.summary-table thead {{ background: #0f172a; }}
.summary-table th {{ padding: 12px 16px; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; text-align: left; }}
.summary-table td {{ padding: 12px 16px; border-top: 1px solid #334155; font-size: 0.85rem; cursor: pointer; }}
.summary-table tbody tr:hover {{ background: #273549; }}
.summary-table td.num {{ font-family: 'Courier New', monospace; font-size: 0.82rem; }}

/* ── Company Card ── */
.company-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 16px; margin-bottom: 32px; overflow: hidden; }}
.card-header {{ background: linear-gradient(135deg, #1e3a5f 0%, #1e293b 100%); padding: 20px 28px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #334155; }}
.card-title-block h2 {{ font-size: 1.25rem; font-weight: 700; color: #f1f5f9; display:inline-block; margin-right: 10px;}}
.ticker-tag {{ background: #1e40af; color: #bfdbfe; font-size: 0.75rem; font-weight: 700; padding: 2px 10px; border-radius: 20px; }}
.country-tag {{ font-size: 0.75rem; color: #94a3b8; margin-left: 8px; }}
.card-risk-block {{ display: flex; align-items: center; gap: 12px; }}
.risk-badge {{ font-size: 0.75rem; font-weight: 700; padding: 4px 12px; border-radius: 20px; }}

.card-body {{ padding: 28px; }}

/* ── Tabs ── */
.tab-bar {{ display: flex; gap: 6px; margin-bottom: 24px; border-bottom: 1px solid #334155; padding-bottom: 12px; }}
.tab-btn {{ background: transparent; color: #94a3b8; border: 1px solid #334155; border-radius: 6px; padding: 8px 16px; font-size: 0.85rem; cursor: pointer; transition: all 0.15s; }}
.tab-btn.active, .tab-btn:hover {{ background: #2563eb; color: #fff; border-color: #2563eb; }}
.tab-pane {{ display: none; animation: fadeIn 0.3s; }}
.tab-pane.active {{ display: block; }}
@keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

/* ── Typography & Elements ── */
h3 {{ font-size: 1.1rem; color: #cbd5e1; margin-bottom: 14px; padding-bottom: 4px; border-bottom: 1px solid #334155; }}
.sw-list {{ list-style-type: none; font-size: 0.85rem; }}
.sw-list li {{ padding: 4px 0; }}
.sw-list .pos::before {{ content: "✅ "; }}
.sw-list .neg::before {{ content: "⚠️ "; }}

.ratio-table {{ width: 100%; border-collapse: collapse; font-size: 0.84rem; }}
.ratio-table th {{ background: #0f172a; color: #94a3b8; padding: 8px 14px; text-align: left; font-size: 0.73rem; text-transform: uppercase; }}
.ratio-table td {{ padding: 7px 14px; border-top: 1px solid #1e293b; }}
.cov-breach {{ color: #ef4444; font-weight:bold; }}
.cov-tight {{ color: #f59e0b; font-weight:bold; }}
.cov-ok {{ color: #10b981; }}

.flags-container {{ display: flex; flex-direction: column; gap: 8px; }}
.flag {{ padding: 10px 14px; border-radius: 8px; font-size: 0.84rem; border-left: 4px solid; }}
.flag-critical {{ background: #1c0a0a; border-color: #dc2626; color: #fca5a5; }}
.flag-warning  {{ background: #1c1208; border-color: #d97706; color: #fcd34d; }}
.flag-info     {{ background: #0c1a2e; border-color: #2563eb; color: #93c5fd; }}
.flag-ok       {{ background: #0a1f0e; border-color: #16a34a; color: #86efac; }}

.memo-section .memo-body {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 20px 24px; font-size: 0.9rem; color: #cbd5e1; white-space: pre-wrap; }}

.footer {{ text-align: center; color: #475569; font-size: 0.75rem; padding: 24px; border-top: 1px solid #334155; margin-top: 40px; }}
</style>
</head>
<body>
<header class="site-header">
  <div>
    <h1>🛡️ Defense Sector <span>Advanced Credit Dashboard</span></h1>
    <div style="font-size:0.8rem;color:#64748b;margin-top:4px;">
      yfinance · Credit Modeling · Gemini AI
    </div>
  </div>
  <div class="header-meta">Generated: {generated_at}<br>Coverage: {n_companies} companies</div>
</header>
<div class="stats-bar">
  <div class="stat"><div class="stat-val">{n_companies}</div><div class="stat-label">Companies</div></div>
  <div class="stat"><div class="stat-val" style="color:#f87171;">{n_high}</div><div class="stat-label">High/Elevated Risk</div></div>
</div>
<div class="container">
  <div class="summary-section">
    <h2>📊 Portfolio Overview</h2>
    {summary_table}
  </div>
  {cards_html}
</div>
<footer class="footer">Defense Credit Intelligence Tool · For informational purposes only.</footer>
<script>
function showTab(event, paneId) {{
    const card = event.target.closest('.card-body');
    card.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
    card.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById(paneId).classList.add('active');
    event.target.classList.add('active');
}}
</script>
</body>
</html>"""

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] HTML dashboard saved -> {output_path}")
