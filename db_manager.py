"""
db_manager.py
SQLite-backed historical financial data store for RiskForge.

Stores computed ratio snapshots per ticker per fiscal period,
enabling SQL-powered trend detection and period-over-period analysis.

NOTE: On Streamlit Community Cloud the filesystem is ephemeral.
The DB is rebuilt each time the user runs an analysis from the
multi-year data yfinance returns in a single call.
"""

from __future__ import annotations

import logging
import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Default database file location — same directory as the app
DB_PATH = os.environ.get("RISKFORGE_DB_PATH", "riskforge_history.db")

# ── The 26 numeric ratio fields we track ────────────────────────────────────
TRACKED_METRICS = [
    "revenue",
    "ebit",
    "ebitda",
    "net_income",
    "total_debt",
    "net_debt",
    "cash",
    "total_equity",
    "total_assets",
    "interest_expense",
    "fcf",
    "cfo",
    "debt_ebitda",
    "net_debt_ebitda",
    "debt_equity",
    "debt_assets",
    "ebit_coverage",
    "ebitda_coverage",
    "current_ratio",
    "quick_ratio",
    "cash_ratio",
    "ebitda_margin",
    "net_margin",
    "fcf_margin",
    "roce",
    "z_score",
]


# ── Connection helper ───────────────────────────────────────────────────────

@contextmanager
def _connect(db_path: str = DB_PATH):
    """Yield a SQLite connection with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema creation ─────────────────────────────────────────────────────────

_CREATE_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS ratio_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identifiers
    ticker          TEXT    NOT NULL,
    company_name    TEXT    NOT NULL,
    market          TEXT,
    sector          TEXT,

    -- Period information
    fiscal_period   TEXT    NOT NULL,   -- e.g. "2024-06-30" from yfinance
    period_label    TEXT,               -- e.g. "Latest FY (2024)" or "2023"
    period_year     INTEGER,            -- extracted year, e.g. 2024

    -- Timestamp of when this snapshot was computed
    analyzed_at     TEXT    NOT NULL,   -- ISO 8601

    -- ── Financial metrics (absolute values) ──
    revenue             REAL,
    ebit                REAL,
    ebitda              REAL,
    net_income          REAL,
    total_debt          REAL,
    net_debt            REAL,
    cash                REAL,
    total_equity        REAL,
    total_assets        REAL,
    interest_expense    REAL,
    fcf                 REAL,
    cfo                 REAL,

    -- ── Computed ratios ──
    debt_ebitda         REAL,
    net_debt_ebitda     REAL,
    debt_equity         REAL,
    debt_assets         REAL,
    ebit_coverage       REAL,
    ebitda_coverage     REAL,
    current_ratio       REAL,
    quick_ratio         REAL,
    cash_ratio          REAL,
    ebitda_margin       REAL,
    net_margin          REAL,
    fcf_margin          REAL,
    roce                REAL,
    z_score             REAL,

    -- ── Risk assessment ──
    risk_rating         TEXT,
    z_score_zone        TEXT,

    -- Prevent duplicate snapshots for same ticker + fiscal period
    UNIQUE(ticker, fiscal_period)
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_snapshots_ticker ON ratio_snapshots(ticker);",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_period ON ratio_snapshots(period_year);",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_ticker_year ON ratio_snapshots(ticker, period_year);",
]


def initialize_db(db_path: str = DB_PATH) -> None:
    """Create the database and tables if they don't exist."""
    with _connect(db_path) as conn:
        conn.execute(_CREATE_SNAPSHOTS_TABLE)
        for idx_sql in _CREATE_INDEXES:
            conn.execute(idx_sql)
    logger.info("Database initialized at %s", db_path)


# ── Insert / Upsert ────────────────────────────────────────────────────────

def _nan_to_none(val: float | None) -> float | None:
    """Convert NaN to None for SQLite storage (NULL)."""
    if isinstance(val, float) and math.isnan(val):
        return None
    return val


def store_ratio_snapshot(
    ticker: str,
    company_name: str,
    market: str,
    sector: str,
    fiscal_period: str,
    period_label: str,
    ratios: dict[str, Any],
    risk_rating: str = "N/A",
    db_path: str = DB_PATH,
) -> None:
    """
    Store a single period's computed ratios into the database.

    Uses INSERT OR REPLACE so that re-analyzing the same company
    updates the existing row rather than creating duplicates.
    """
    period_year = None
    try:
        period_year = int(fiscal_period[:4])
    except (ValueError, TypeError, IndexError):
        pass

    analyzed_at = datetime.utcnow().isoformat()

    sql = """
    INSERT OR REPLACE INTO ratio_snapshots (
        ticker, company_name, market, sector,
        fiscal_period, period_label, period_year, analyzed_at,
        revenue, ebit, ebitda, net_income,
        total_debt, net_debt, cash, total_equity, total_assets,
        interest_expense, fcf, cfo,
        debt_ebitda, net_debt_ebitda, debt_equity, debt_assets,
        ebit_coverage, ebitda_coverage,
        current_ratio, quick_ratio, cash_ratio,
        ebitda_margin, net_margin, fcf_margin, roce, z_score,
        risk_rating, z_score_zone
    ) VALUES (
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?,
        ?, ?, ?,
        ?, ?, ?, ?, ?,
        ?, ?
    )
    """

    values = (
        ticker, company_name, market, sector,
        fiscal_period, period_label, period_year, analyzed_at,
        _nan_to_none(ratios.get("revenue")),
        _nan_to_none(ratios.get("ebit")),
        _nan_to_none(ratios.get("ebitda")),
        _nan_to_none(ratios.get("net_income")),
        _nan_to_none(ratios.get("total_debt")),
        _nan_to_none(ratios.get("net_debt")),
        _nan_to_none(ratios.get("cash")),
        _nan_to_none(ratios.get("total_equity")),
        _nan_to_none(ratios.get("total_assets")),
        _nan_to_none(ratios.get("interest_expense")),
        _nan_to_none(ratios.get("fcf")),
        _nan_to_none(ratios.get("cfo")),
        _nan_to_none(ratios.get("debt_ebitda")),
        _nan_to_none(ratios.get("net_debt_ebitda")),
        _nan_to_none(ratios.get("debt_equity")),
        _nan_to_none(ratios.get("debt_assets")),
        _nan_to_none(ratios.get("ebit_coverage")),
        _nan_to_none(ratios.get("ebitda_coverage")),
        _nan_to_none(ratios.get("current_ratio")),
        _nan_to_none(ratios.get("quick_ratio")),
        _nan_to_none(ratios.get("cash_ratio")),
        _nan_to_none(ratios.get("ebitda_margin")),
        _nan_to_none(ratios.get("net_margin")),
        _nan_to_none(ratios.get("fcf_margin")),
        _nan_to_none(ratios.get("roce")),
        _nan_to_none(ratios.get("z_score")),
        risk_rating,
        ratios.get("z_score_zone", "N/A"),
    )

    with _connect(db_path) as conn:
        conn.execute(sql, values)

    logger.debug("Stored snapshot: %s / %s", ticker, fiscal_period)


def store_all_period_ratios(
    ticker: str,
    company_name: str,
    market: str,
    sector: str,
    period_ratios: dict[str, dict],
    fiscal_periods: list[str],
    risk_rating: str = "N/A",
    db_path: str = DB_PATH,
) -> None:
    """
    Store all periods' ratios for a company in a single call.
    """
    initialize_db(db_path)

    labels = list(period_ratios.keys())
    for i, label in enumerate(labels):
        fiscal_period = fiscal_periods[i] if i < len(fiscal_periods) else label
        ratios = period_ratios[label]
        store_ratio_snapshot(
            ticker=ticker,
            company_name=company_name,
            market=market,
            sector=sector,
            fiscal_period=str(fiscal_period),
            period_label=label,
            ratios=ratios,
            risk_rating=risk_rating,
            db_path=db_path,
        )


# ── Query functions ─────────────────────────────────────────────────────────

def get_ticker_history(
    ticker: str,
    db_path: str = DB_PATH,
) -> list[dict]:
    """
    Retrieve all stored snapshots for a ticker, ordered by period_year ASC.

    Returns a list of dicts (one per period), oldest first.
    """
    sql = """
    SELECT * FROM ratio_snapshots
    WHERE ticker = ?
    ORDER BY period_year ASC
    """
    with _connect(db_path) as conn:
        rows = conn.execute(sql, (ticker,)).fetchall()
    return [dict(row) for row in rows]


def get_metric_timeseries(
    ticker: str,
    metric: str,
    db_path: str = DB_PATH,
) -> list[tuple[int, float | None]]:
    """
    Retrieve a single metric's values over time for a ticker.

    Returns list of (period_year, value) tuples, oldest first.
    """
    if metric not in TRACKED_METRICS:
        raise ValueError(f"Unknown metric: {metric}. Must be one of {TRACKED_METRICS}")

    sql = f"""
    SELECT period_year, {metric}
    FROM ratio_snapshots
    WHERE ticker = ?
    ORDER BY period_year ASC
    """
    with _connect(db_path) as conn:
        rows = conn.execute(sql, (ticker,)).fetchall()
    return [(row[0], row[1]) for row in rows]


def get_all_tickers_latest(db_path: str = DB_PATH) -> list[dict]:
    """
    Get the latest snapshot for every ticker in the database.
    Useful for portfolio-level views.
    """
    sql = """
    SELECT *
    FROM ratio_snapshots r1
    WHERE period_year = (
        SELECT MAX(period_year)
        FROM ratio_snapshots r2
        WHERE r2.ticker = r1.ticker
    )
    ORDER BY ticker
    """
    with _connect(db_path) as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]


def get_peer_comparison(
    sector: str,
    metric: str,
    db_path: str = DB_PATH,
) -> list[dict]:
    """
    Compare the latest value of a metric across all companies in a sector.
    """
    if metric not in TRACKED_METRICS:
        raise ValueError(f"Unknown metric: {metric}")

    sql = f"""
    SELECT r1.ticker, r1.company_name, r1.period_year, r1.{metric}
    FROM ratio_snapshots r1
    WHERE r1.sector = ?
      AND r1.period_year = (
          SELECT MAX(r2.period_year)
          FROM ratio_snapshots r2
          WHERE r2.ticker = r1.ticker
      )
    ORDER BY r1.{metric} DESC
    """
    with _connect(db_path) as conn:
        rows = conn.execute(sql, (sector,)).fetchall()
    return [dict(row) for row in rows]


def run_custom_query(
    sql: str,
    params: tuple = (),
    db_path: str = DB_PATH,
) -> list[dict]:
    """
    Execute a custom read-only SQL query against the database.
    """
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
        raise ValueError("Only read-only SELECT / WITH queries are permitted in the SQL Explorer.")
    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]
