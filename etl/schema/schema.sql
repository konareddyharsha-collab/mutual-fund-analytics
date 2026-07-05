-- SQLite schema for Mutual Fund Analytics
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS dim_fund (
    scheme_code TEXT PRIMARY KEY,
    scheme_name TEXT,
    fund_house TEXT,
    category TEXT,
    inception_date DATE,
    expense_ratio REAL
);

CREATE TABLE IF NOT EXISTS fact_nav (
    scheme_code TEXT,
    nav_date DATE,
    nav_value REAL,
    PRIMARY KEY (scheme_code, nav_date)
);

CREATE TABLE IF NOT EXISTS fact_aum (
    fund_house TEXT,
    quarter_date DATE,
    aum_crores REAL
);

CREATE TABLE IF NOT EXISTS fact_sip (
    scheme_code TEXT,
    month_year DATE,
    sip_inflow_cr REAL,
    active_accounts INTEGER
);

CREATE TABLE IF NOT EXISTS fact_transactions (
    txn_id TEXT PRIMARY KEY,
    investor_id TEXT,
    scheme_code TEXT,
    txn_date DATE,
    txn_type TEXT,
    amount REAL,
    city TEXT,
    state TEXT,
    age INTEGER,
    income_bucket TEXT,
    city_tier TEXT
);

CREATE TABLE IF NOT EXISTS fact_holdings (
    scheme_code TEXT,
    as_of_date DATE,
    holding_symbol TEXT,
    weight_percent REAL,
    market_value REAL
);

CREATE TABLE IF NOT EXISTS dim_benchmark (
    date DATE,
    index_name TEXT,
    close REAL,
    PRIMARY KEY (date, index_name)
);

