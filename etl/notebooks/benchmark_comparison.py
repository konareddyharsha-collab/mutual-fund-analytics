"""Benchmark comparison analysis
- Connects to SQLite DB, computes daily returns for schemes and benchmarks
- Computes tracking error, relative performance, rolling 6-month correlation
- Outputs interactive Plotly HTML chart: outputs/benchmark_comparison_O7.html
"""
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine

DB = Path("db/mutual_funds.db")
OUT = Path("outputs")
OUT.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB}")

# load benchmark indices
with engine.begin() as conn:
    try:
        bench = pd.read_sql("SELECT * FROM dim_benchmark", conn, parse_dates=['date'])
    except Exception:
        bench = pd.DataFrame()

# load NAVs for selected schemes (top 5 by availability)
with engine.begin() as conn:
    try:
        nav = pd.read_sql("SELECT * FROM fact_nav", conn, parse_dates=['nav_date'])
    except Exception:
        nav = pd.DataFrame()

if bench.empty or nav.empty:
    print("Missing data in DB. Run ETL first or provide CSVs in data/.")
else:
    # pivot benchmarks: assume index_name column holds names
    bench_pivot = bench.pivot(index='date', columns='index_name', values='close').sort_index()
    bench_ret = bench_pivot.pct_change()

    # calculate scheme returns
    nav['nav_date'] = pd.to_datetime(nav['nav_date'])
    nav = nav.sort_values(['scheme_code','nav_date'])
    nav['ret'] = nav.groupby('scheme_code')['nav_value'].pct_change()
    # pick top 6 schemes with most observations
    top_schemes = nav['scheme_code'].value_counts().head(6).index.tolist()
    nav_top = nav[nav['scheme_code'].isin(top_schemes)].copy()
    nav_pivot = nav_top.pivot(index='nav_date', columns='scheme_code', values='ret').sort_index()

    # merge with benchmark daily returns on common dates
    merged = nav_pivot.join(bench_ret, how='inner')

    # compute tracking error (std of difference vs Nifty 50) annualized
    if 'Nifty 50' in merged.columns:
        rets = merged
        metrics = []
        for sc in top_schemes:
            if sc in rets.columns:
                diff = (rets[sc] - rets['Nifty 50']).dropna()
                te = diff.std(ddof=1) * np.sqrt(252)
                rel_perf = ( (1+rets[sc]).cumprod() - (1+rets['Nifty 50']).cumprod() )
                corr_6m = rets[sc].rolling(window=126, min_periods=2).corr(rets['Nifty 50'])
                metrics.append({'scheme_code': sc, 'tracking_error_annualized': float(te)})
                # attach to DataFrame for plotting
                rets[f'{sc}_rel_perf'] = rel_perf
                rets[f'{sc}_corr_6m'] = corr_6m
        metrics_df = pd.DataFrame(metrics)
        metrics_df.to_csv(OUT / 'benchmark_metrics.csv', index=False)

        # Plot relative performance lines (O7)
        fig = go.Figure()
        for sc in top_schemes:
            col = f'{sc}_rel_perf'
            if col in rets.columns:
                fig.add_trace(go.Scatter(x=rets.index, y=rets[col], name=f'{sc} relative to Nifty 50', mode='lines', hoverinfo='text', text=[f"{sc} - {d.date()}<br>RelPerf: {v:.4f}" for d,v in zip(rets.index, rets[col].fillna(0))]))
        fig.update_layout(title='Benchmark comparison chart (O7): Relative Performance vs Nifty 50', xaxis_title='Date', yaxis_title='Cumulative Relative Performance')
        fig.write_html(OUT / 'benchmark_comparison_O7.html')
        print('Wrote', OUT / 'benchmark_comparison_O7.html')
    else:
        print("Nifty 50 not found in benchmark indices. Available:", bench_pivot.columns.tolist())
