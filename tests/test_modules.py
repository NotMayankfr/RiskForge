"""
test_modules.py
Deterministic unit tests for the defense credit tool backend modules.
"""

import sys
import os
import math
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ratio_engine import _safe_ratio, _div, _altman_z
from debt_capacity import compute_debt_capacity as calculate_debt_capacity
from stress_engine import run_stress_scenarios
from covenant_monitor import analyze_covenants
from refinancing_risk import assess_refinancing_risk
from cashflow_model import model_cashflows


class TestBackendModules(unittest.TestCase):
    
    def test_ratio_engine_safety(self):
        self.assertTrue(math.isnan(_div(5, 0)))
        self.assertTrue(math.isnan(_div(5, math.nan)))
        
        # Negative EBITDA -> NaN leverage
        self.assertTrue(math.isnan(_safe_ratio(100, -10, "debt_ebitda", ebitda=-10)))
        
        # Altman Z with zeros
        z = _altman_z(0, 0, 0, 0, 100, 0, 100)
        self.assertFalse(math.isnan(z))
        self.assertEqual(z, 0.0)
        
    def test_debt_capacity(self):
        ratios = {
            "ebitda": 10000.0,
            "net_debt": 25000.0,
            "total_debt": 30000.0,
            "ebit": 9000.0,
            "interest_expense": 500.0,
            "fcf": 2000.0
        }
        cap = calculate_debt_capacity(ratios)
        self.assertAlmostEqual(cap["current_net_leverage"], 2.5)
        self.assertAlmostEqual(cap["leverage_headroom"], 15000.0) # 10k * 4.0 - 25k
        self.assertAlmostEqual(cap["fcf_paydown_years"], 15.0)
        
        # Test missing data (negative EBITDA)
        ratios_neg = {"ebitda": -1000.0, "net_debt": 5000.0}
        cap_neg = calculate_debt_capacity(ratios_neg)
        self.assertTrue(math.isnan(cap_neg["current_net_leverage"]))
        
    def test_stress_engine(self):
        ratios = {"revenue": 100, "ebitda": 20, "ebit": 15, "total_debt": 40, "net_debt": 30, "interest_expense": 5}
        scenarios = {
            "base": {"revenue_change_pct": 0, "margin_change_ppt": 0},
            "moderate": {"revenue_change_pct": -0.10, "margin_change_ppt": 0}
        }
        res = run_stress_scenarios(ratios, {}, scenarios)
        self.assertAlmostEqual(res["base"]["stressed_revenue"], 100.0)
        self.assertAlmostEqual(res["moderate"]["stressed_revenue"], 90.0)
        
    def test_covenant_monitor(self):
        ratios = {"Latest FY": {"net_debt_ebitda": 4.5}}
        thresholds = {"max_net_debt_ebitda": 4.0}
        covs = analyze_covenants(ratios, thresholds)
        self.assertTrue(covs["covenants"][0]["breach"])
        self.assertEqual(covs["covenants"][0]["status"], "BREACH")
        
        # TIGHT status
        ratios_tight = {"Latest FY": {"net_debt_ebitda": 3.8}}
        covs_tight = analyze_covenants(ratios_tight, thresholds)
        self.assertFalse(covs_tight["covenants"][0]["breach"])
        self.assertEqual(covs_tight["covenants"][0]["status"], "TIGHT")
        
    def test_refinancing_risk(self):
        # High leverage + neg FCF + low cash -> ELEVATED
        r = {"net_debt_ebitda": 5.0, "fcf": -100, "total_debt": 1000, "cash": 50, "interest_expense": 200, "ebitda": 300}
        risk = assess_refinancing_risk(r)
        self.assertEqual(risk["classification"], "ELEVATED")
        
        # Low risk
        r_low = {"net_debt_ebitda": 1.0, "fcf": 500, "total_debt": 1000, "cash": 300, "interest_expense": 50, "ebitda": 800}
        risk_low = assess_refinancing_risk(r_low)
        self.assertEqual(risk_low["classification"], "LOW")
        
    def test_cashflow_model(self):
        raw = {
            "income": {"2024": {"Total Revenue": 100, "EBITDA": 20}},
            "cashflow": {"2024": {"Operating Cash Flow": 15, "Capital Expenditure": -5}},
            "balance": {"2024": {"Total Debt": 50}}
        }
        res = model_cashflows(raw, ["2024"], {"revenue_growth_pct": 0.05, "projection_years": 3})
        self.assertEqual(len(res["historical"]), 1)
        self.assertEqual(res["historical"][0]["fcf"], 10)
        self.assertEqual(res["historical"][0]["fcf_margin"], 10.0)
        
        # Year 1 projection: 100 * 1.05 = 105
        self.assertAlmostEqual(res["projection"][0]["projected_revenue"], 105.0)

if __name__ == "__main__":
    unittest.main()
