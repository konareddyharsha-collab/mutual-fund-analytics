"""ETL pipeline for Mutual Fund Analytics

Usage:
  python etl/etl_pipeline.py --data-dir data --db db/mutual_funds.db --schema schema/schema.sql

This script:
- Creates the SQLite schema from `schema/schema.sql`.
- Ingests provided CSVs into their target tables with light cleaning.
- Optionally fetches NAVs from mfapi.in for missing data (if enabled).
"""
import argparse
import logging
from pathlib import Path

import pandas as pd
import requests
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def init_db(engine, schema_path: Path):
    logging.info("Initializing database schema from %s", schema_path)
    with open(schema_path, "r", encoding="utf-8") as fh:
        schema_sql = fh.read()
    # SQLite's DB-API allows executescript for multiple statements; SQLAlchemy
    # doesn't accept multiple statements in a single execute call. Handle
    # sqlite specially and fall back to executing statements one-by-one.
    try:
        with engine.begin() as conn:
            dialect = conn.dialect.name
    except Exception:
        dialect = None

    if dialect == "sqlite":
        raw = engine.raw_connection()
        try:
            cur = raw.cursor()
            cur.executescript(schema_sql)
            raw.commit()
        finally:
            raw.close()
    else:
        # Split on semicolons and execute statements individually
        stmts = [s.strip() for s in schema_sql.split(";") if s.strip()]
        with engine.begin() as conn:
            for s in stmts:
                conn.execute(text(s))


def clean_and_cast(df: pd.DataFrame, date_cols=None, numeric_cols=None):
    if date_cols:
        for c in date_cols:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], format='mixed', dayfirst=True, errors="coerce").dt.strftime('%Y-%m-%d')
    if numeric_cols:
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.drop_duplicates()
    return df


def write_df_to_db(engine, df: pd.DataFrame, table_name: str):
    try:
        with engine.begin() as conn:
            dialect = conn.dialect.name
    except Exception:
        dialect = None

    if dialect == "sqlite":
        raw = engine.raw_connection()
        try:
            cur = raw.cursor()
            cols = list(df.columns)
            placeholders = ",".join(["?" for _ in cols])
            col_list = ",".join(cols)
            sql = f"INSERT OR REPLACE INTO {table_name} ({col_list}) VALUES ({placeholders})"
            data = [tuple(row) for row in df[cols].itertuples(index=False, name=None)]
            cur.executemany(sql, data)
            raw.commit()
            logging.info("Wrote %d rows to %s (sqlite upsert)", len(df), table_name)
        finally:
            raw.close()
    else:
        df.to_sql(table_name, engine, if_exists="append", index=False)
        logging.info("Wrote %d rows to %s", len(df), table_name)


def ingest_csv(engine, csv_path: Path, table_name: str, date_cols=None, numeric_cols=None):
    logging.info("Ingesting %s -> %s", csv_path, table_name)
    df = pd.read_csv(csv_path)
    df = clean_and_cast(df, date_cols=date_cols, numeric_cols=numeric_cols)
    write_df_to_db(engine, df, table_name)


def fetch_nav_for_scheme(scheme_code: str):
    """Fetch NAV history JSON from mfapi.in for a scheme code.

    Endpoint: https://www.mfapi.in/mf/<scheme_code>
    Returns a list of {date, nav} or empty list on error.
    """
    url = f"https://www.mfapi.in/mf/{scheme_code}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data") or []
        records = [{"scheme_code": scheme_code, "nav_date": d.get("date"), "nav_value": d.get("nav")} for d in data]
        return records
    except Exception as e:
        logging.warning("Failed to fetch NAV for %s: %s", scheme_code, e)
        return []


def ingest_mfapi_navs(engine, scheme_codes):
    rows = []
    for sc in scheme_codes:
        recs = fetch_nav_for_scheme(sc)
        rows.extend(recs)
    if not rows:
        logging.info("No NAVs fetched from mfapi.in")
        return
    df = pd.DataFrame(rows)
    df = clean_and_cast(df, date_cols=["nav_date"], numeric_cols=["nav_value"])
    write_df_to_db(engine, df, "fact_nav")



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data", help="Directory containing CSV files")
    parser.add_argument("--db", default="db/mutual_funds.db", help="SQLite DB path to create/append")
    parser.add_argument("--schema", default="schema/schema.sql", help="Path to schema SQL file")
    parser.add_argument("--fetch-mfapi", action="store_true", help="Attempt to fetch NAVs from mfapi.in for schemes in fund_master")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    schema_path = Path(args.schema)
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    # Create schema if not exists
    init_db(engine, schema_path)

    # Map of expected csv filenames to target tables + simple casting hints
    mapping = [
        ("01_fund_master.csv", "dim_fund", None, ["expense_ratio"]),
        ("02_nav_history.csv", "fact_nav", ["nav_date"], ["nav_value"]),
        ("03_aum_by_fund_house.csv", "fact_aum", ["quarter_date"], ["aum_crores"]),
        ("04_monthly_sip_inflows.csv", "fact_sip", ["month_year"], ["sip_inflow_cr", "active_accounts"]),
        ("08_investor_transactions.csv", "fact_transactions", ["txn_date"], ["amount"]),
        ("09_portfolio_holdings.csv", "fact_holdings", None, ["weight_percent", "market_value"]),
        ("10_benchmark_indices.csv", "dim_benchmark", ["date"], ["close"]),
    ]

    for fname, table, date_cols, numeric_cols in mapping:
        path = data_dir / fname
        if path.exists():
            ingest_csv(engine, path, table, date_cols=date_cols, numeric_cols=numeric_cols)
        else:
            logging.warning("Missing expected file %s; skipping", path)

    if args.fetch_mfapi:
        # load scheme codes from dim_fund
        with engine.begin() as conn:
            try:
                df = pd.read_sql("SELECT scheme_code FROM dim_fund", conn)
                scheme_codes = df["scheme_code"].astype(str).unique().tolist()
                ingest_mfapi_navs(engine, scheme_codes)
            except Exception:
                logging.exception("Could not read scheme codes from dim_fund")

    logging.info("ETL run finished. DB: %s", db_path)


if __name__ == "__main__":
    main()
