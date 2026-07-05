"""Investor demographics & transaction patterns EDA
Produces summary CSVs and quick charts.
"""
from pathlib import Path
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

DB = Path("db/mutual_funds.db")
OUT = Path("outputs")
OUT.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{DB}")

with engine.begin() as conn:
    try:
        tx = pd.read_sql("SELECT * FROM fact_transactions", conn, parse_dates=['txn_date'])
    except Exception:
        tx = pd.DataFrame()

if tx.empty:
    print("No transaction data found. Run ETL first.")
else:
    # Age bands
    bins = [0,24,34,44,60,120]
    labels = ['<25','25-34','35-44','45-60','60+']
    tx['age_band'] = pd.cut(tx['age'].fillna(0), bins=bins, labels=labels, right=True)
    age_summary = tx.groupby('age_band').agg(txn_count=('txn_id','count'), total_amount=('amount','sum')).reset_index()
    age_summary.to_csv(OUT / 'age_summary.csv', index=False)

    # Income buckets
    inc_summary = tx.groupby('income_bucket').agg(txn_count=('txn_id','count'), total_amount=('amount','sum')).reset_index()
    inc_summary.to_csv(OUT / 'income_summary.csv', index=False)

    # City tier growth (simple year over year from txn_date)
    tx['year'] = tx['txn_date'].dt.year
    tier_year = tx.groupby(['city_tier','year']).size().unstack(fill_value=0)
    tier_year.to_csv(OUT / 'city_tier_yearly.csv')

    # SIP vs lump sum share
    mix = tx['txn_type'].value_counts(normalize=True).reset_index()
    mix.columns = ['txn_type','share']
    mix.to_csv(OUT / 'txn_mix.csv', index=False)

    print('Wrote demographics summaries to outputs/')
