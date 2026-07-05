# Mutual Fund Analytics ETL & Analysis Pipeline

This repository contains an end-to-end ETL (Extract, Transform, Load) pipeline and exploratory data analysis (EDA) scripts for analyzing mutual fund performance, benchmark tracking, and investor demographics.

## Project Structure

```text
etl/
├── data/                       # Contains source CSV datasets
│   ├── 01_fund_master.csv      # Fund details (category, expense ratio, etc.)
│   ├── 02_nav_history.csv      # Daily/historical NAV records
│   ├── 08_investor_transactions.csv  # Demographics and transaction data
│   ├── 09_portfolio_holdings.csv     # Fund holdings weights
│   └── 10_benchmark_indices.csv      # Benchmark closing prices (Nifty 50, etc.)
├── db/                         # Target SQLite database directory
│   └── mutual_funds.db         # Generated database (after running ETL)
├── schema/                     # Database schema definitions
│   └── schema.sql              # SQL DDL script defining tables
├── notebooks/                  # Analysis and visualization scripts
│   ├── benchmark_comparison.py # Relative performance, tracking error, correlation
│   ├── demographics_analysis.py# EDA on age bands, income, city tier, and transaction mix
│   └── generate_presentation.py# Assembles a 12-slide PDF report/presentation
├── outputs/                    # Output directory for charts, reports, and summaries
│   ├── presentation.pdf        # Main 12-slide executive presentation
│   ├── benchmark_comparison_O7.html # Interactive Plotly line chart
│   └── *.csv                   # Summarized analytics data
├── requirements.txt            # Python environment dependencies
└── README.md                   # Project documentation (this file)
```

---

## Getting Started

### 1. Setup Environment
Create a virtual environment and install the required packages:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Run the ETL Pipeline
To read the source files, create the database schema, clean/cast data, and load it into SQLite:
```powershell
python etl_pipeline.py --data-dir data --db db/mutual_funds.db --schema schema/schema.sql
```
*(Optional)* Add the `--fetch-mfapi` flag to fetch live historical NAV data from the `mfapi.in` API for schemes in the database.

### 3. Run Analysis & Generate Reports
Generate the benchmark metrics, demographics reports, and the PDF presentation:
```powershell
python notebooks/benchmark_comparison.py
python notebooks/demographics_analysis.py
python notebooks/generate_presentation.py
```
Outputs will be saved directly in the `outputs/` folder.

---

## Bugs and Issues Fixed

We resolved several critical bugs and warnings to ensure correctness and compatibility:

1. **Benchmark Primary Key Conflict (`schema.sql`)**:
   - *Problem*: The `dim_benchmark` table had `date` as the sole `PRIMARY KEY`. When multiple benchmarks (e.g., `Nifty 50` and `Nifty 100`) had records on the same date, they would overwrite each other during SQLite upsert, leading to sparse/missing rows and resulting in an empty merged returns dataset.
   - *Fix*: Changed the primary key of `dim_benchmark` to a composite key `PRIMARY KEY (date, index_name)`.

2. **Mixed Date Format Parsing (`etl_pipeline.py`)**:
   - *Problem*: Local CSVs used `YYYY-MM-DD` while the `mfapi.in` API returned dates in `DD-MM-YYYY`. Standard date parsing was parsing dates like `05-06-2023` as May 6th instead of June 5th.
   - *Fix*: Configured date parsing with `format='mixed'` and `dayfirst=True` to parse both formats cleanly and accurately.

3. **SQLite Deprecation Warnings (`etl_pipeline.py`)**:
   - *Problem*: Passing Python `datetime.date` objects directly to SQLite is deprecated as of Python 3.12+ and raised deprecation warnings.
   - *Fix*: Standardized the clean pipeline to format dates as ISO strings (`YYYY-MM-DD`) during casting, ensuring warning-free database writes.

4. **Tracking Error & Rolling Correlation Failures (`benchmark_comparison.py` & `generate_presentation.py`)**:
   - *Problem*: A premature `.dropna()` call on the benchmark returns removed all rows where any benchmark was missing. Additionally, calculating rolling correlation on small/sample datasets resulted in all-NaN values due to the hardcoded `window=126` constraint.
   - *Fix*: Removed the general `.dropna()` from `bench_ret` and handled NaNs specifically per-benchmark comparison using `.dropna()`. Set `min_periods=2` on the rolling correlation so it successfully outputs metrics even on smaller datasets.

---

## Git Operations

Configure your repository and push to GitHub:

```powershell
git init
git add .
git commit -m "Initialize project: Fix ETL date parsing, SQLite composite primary keys, and metrics calculations"
git remote add origin https://github.com/konareddyharsha-collab/mutual-fund-analytics.git
git branch -M main
git push -u origin main
```
