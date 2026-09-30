"""
sector_overlay.py
Defense sector static overlay data.
"""

from __future__ import annotations

SECTOR_DATA = {
    "RTX": {
        "sector": "Defense & Aerospace",
        "sub_sector": "Diversified Aerospace & Defense",
        "primary_customer": "US DoD & Commercial Airlines",
        "revenue_visibility": "HIGH",
        "capital_intensity": "HIGH",
        "cyclicality": "MEDIUM (Commercial aero cyclical, defense stable)"
    },
    "LMT": {
        "sector": "Defense & Aerospace",
        "sub_sector": "Aerospace, Missiles & Space",
        "primary_customer": "US DoD",
        "revenue_visibility": "HIGH",
        "capital_intensity": "MEDIUM",
        "cyclicality": "LOW"
    },
    "NOC": {
        "sector": "Defense & Aerospace",
        "sub_sector": "Aerospace & Mission Systems",
        "primary_customer": "US DoD",
        "revenue_visibility": "HIGH",
        "capital_intensity": "MEDIUM",
        "cyclicality": "LOW"
    },
    "GD": {
        "sector": "Defense & Aerospace",
        "sub_sector": "Marine, Aerospace & Combat Systems",
        "primary_customer": "US DoD",
        "revenue_visibility": "HIGH",
        "capital_intensity": "HIGH",
        "cyclicality": "MEDIUM"
    },
    "LHX": {
        "sector": "Defense & Aerospace",
        "sub_sector": "Defense Electronics",
        "primary_customer": "US DoD",
        "revenue_visibility": "HIGH",
        "capital_intensity": "LOW",
        "cyclicality": "LOW"
    },
    "AM.PA": {
        "sector": "Defense & Aerospace",
        "sub_sector": "Combat Aircraft & Business Jets",
        "primary_customer": "French MoD & International",
        "revenue_visibility": "MEDIUM",
        "capital_intensity": "HIGH",
        "cyclicality": "MEDIUM"
    },
    "BAESY": {
        "sector": "Defense & Aerospace",
        "sub_sector": "Diversified Defense",
        "primary_customer": "UK MoD & US DoD",
        "revenue_visibility": "HIGH",
        "capital_intensity": "MEDIUM",
        "cyclicality": "LOW"
    },
    "HO.PA": {
        "sector": "Defense & Aerospace",
        "sub_sector": "Defense Electronics",
        "primary_customer": "French MoD",
        "revenue_visibility": "HIGH",
        "capital_intensity": "MEDIUM",
        "cyclicality": "LOW"
    },
    "HAL.NS": {
        "sector": "Defense & Aerospace",
        "sub_sector": "Aircraft & Helicopters",
        "primary_customer": "Indian MoD",
        "revenue_visibility": "HIGH",
        "capital_intensity": "MEDIUM",
        "cyclicality": "LOW"
    },
    "BEL.NS": {
        "sector": "Defense & Aerospace",
        "sub_sector": "Defense Electronics",
        "primary_customer": "Indian MoD",
        "revenue_visibility": "HIGH",
        "capital_intensity": "LOW",
        "cyclicality": "LOW"
    }
}

def get_sector_info(ticker: str) -> dict:
    return SECTOR_DATA.get(ticker, {
        "sector": "Unknown",
        "sub_sector": "Unknown",
        "primary_customer": "Unknown",
        "revenue_visibility": "Unknown",
        "capital_intensity": "Unknown",
        "cyclicality": "Unknown",
        "data_source_note": "Sector context based on publicly available information. Verify independently."
    })
