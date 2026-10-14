# Sales Intelligent System

An interactive sales analytics dashboard built with Python, pandas, Plotly and Streamlit.
It loads a sales file (CSV/Excel), validates and cleans it, calculates business KPIs,
and presents filterable charts, customer segments, a backtested forecast, rule-based
insights and downloadable reports.

> **Data notice:** the repository ships with a **SYNTHETIC** (randomly generated) demo
> dataset, `data/raw/sample_sales_SYNTHETIC.csv`. Every number you see with it is
> artificial and says nothing about any real business. Upload your own file in the
> sidebar to analyse real data.

## Business problems it addresses

| Question | Where it is answered |
|---|---|
| How much did we sell, and how healthy is the average order? | KPI cards (revenue, orders, units, AOV, customers, discount rate) |
| Which categories / products / regions matter most? | Products & Categories, Regions tabs |
| Do a few products carry most of the revenue? | Pareto (80/20) analysis |
| Are we growing? Is there seasonality? | Trends & Growth (MoM, YoY, heatmap) |
| Are we profitable, and where is margin low? | Gross profit / margin (needs `unit_cost`) |
| Who are our best and at-risk customers? | Repeat-purchase metrics and rule-based RFM segments |
| What might the next months look like? | Forecast tab (backtested against a baseline) |
| What should I look at first? | Insights tab (findings computed from the data) |

## Quick start (Windows)

```bat
cd "C:\Users\visha\OneDrive\Desktop\sales intelligent system"
.sales\Scripts\activate
python -m streamlit run app.py
```

or double-click `run_app.bat`. The synthetic sample file is created automatically on
the first run if it is missing.

Run the tests:

```bat
python -m unittest discover -s tests -t . -v
```

(`python -m pytest` also works if you `pip install pytest`.)

Process a file from the command line (writes `data/processed/`):

```bat
python -m src.pipeline
python -m src.pipeline --input path\to\your_file.csv
```

Regenerate the synthetic data (optional): `python -m src.generate_sample_data`
(`--clean` for a version without deliberately dirty rows).

## Project structure

```text
sales intelligent system/
├── app.py                     Streamlit dashboard (UI only)
├── config.py                  Paths, required columns, business constants
├── requirements.txt
├── run_app.bat                Windows launcher
├── src/
│   ├── data_loader.py         Read CSV/XLSX, normalise headers, validate columns
│   ├── data_cleaning.py       Types, validation, duplicates, derived columns, cleaning report
│   ├── pipeline.py            load -> validate -> clean (+ command-line entry)
│   ├── analytics.py           KPIs, breakdowns, Pareto, growth, RFM, forecast, insights
│   ├── visualizations.py      Plotly chart builders (drawing only)
│   ├── exporter.py            Filtered CSV and multi-sheet Excel report
│   └── generate_sample_data.py  SYNTHETIC data generator
├── tests/                     38 unit tests (hand-computed expected values)
├── data/raw, data/processed
├── docs/INTERVIEW_GUIDE.md
└── notebooks/                 Free space for exploration
```

**Data flow:** file -> `data_loader` (validate) -> `data_cleaning` (type, repair,
derive revenue/profit) -> sidebar filters (`analytics.apply_filters`) -> analytics
functions -> `visualizations` -> Streamlit tabs -> `exporter` downloads.

## Dataset requirements

One row = one product line of an order. Column names are matched case-insensitively
(spaces become underscores).

| Column | Required | Description |
|---|---|---|
| `order_id` | yes | Order identifier; repeats when an order has several products |
| `order_date` | yes | Prefer ISO `YYYY-MM-DD`. Other formats are read month-first |
| `customer_id` | yes | Customer identifier |
| `region` | yes | Missing values become `Unknown` |
| `category` | yes | Product category |
| `product` | yes | Product name |
| `quantity` | yes | Units, must be > 0 |
| `unit_price` | yes | Price per unit, must be > 0 |
| `discount` | no | **Fraction** 0-1 (0.10 = 10%). Missing = 0. Outside 0-1 = row removed |
| `unit_cost` | no | Cost per unit. Without it, profit and margin are disabled |

## KPI definitions

| Metric | Formula | Notes |
|---|---|---|
| Revenue | `quantity * unit_price * (1 - discount)` | Net of discount, summed over rows |
| Orders | distinct `order_id` | Not the number of rows |
| AOV | revenue / distinct orders | Correct grain for multi-line orders |
| Units | sum of `quantity` | |
| Gross profit | revenue - `quantity * unit_cost` | Product cost only; overheads, tax and returns are not modelled |
| Gross margin % | gross profit / revenue (rows with known cost) | |
| Discount rate % | (gross sales - revenue) / gross sales | |
| MoM / YoY % | change vs previous month / same month last year | Missing months are filled with 0 so shifts are correct |
| Contribution | item revenue / total revenue | |
| Pareto core items | smallest set of top items reaching 80% of revenue | |
| Repeat customer | 2+ distinct orders inside the selected filters | A selection effect, see limitations |
| RFM segments | percentile scores (1-5) for recency, frequency, monetary, mapped by fixed rules | Rule-based, not machine learning |

## Why no machine-learning model?

Forecasting is the only predictive feature, and it is deliberately simple (linear trend +
monthly seasonality) because the dataset has one target (monthly revenue) and a few dozen
points. It is **always backtested** against a "same month last year" baseline and the
dashboard warns if it does not win. Classification or deep models would be unjustified
for this data size and would add complexity without evidence of benefit. MySQL
(`sqlalchemy`, `pymysql`) is not used because the file-based flow covers the requirements;
it can be added behind `data_loader.py` later without touching the analytics.

## Verification status (be honest in interviews)

* 38 unit tests pass (loader, cleaning, KPIs, breakdowns, filters, growth, RFM, forecast,
  export). Expected values are computed by hand on a tiny dataset and cross-checked against
  independent NumPy calculations on the synthetic data.
* The dashboard and chart code were smoke-tested end-to-end (default, empty filters, bad
  upload, valid Excel upload) using stand-in `streamlit`/`plotly` modules in the build
  environment. **Run it once on your machine and look at every tab** before demonstrating it.
* Not performed: browser testing, large-file performance testing, deployment.

## Known limitations

* Descriptive analytics only: insights say *what* happened, not *why*.
* Partial periods (first/last month, current year) can look like declines.
* Repeat-purchase and RFM depend on the selected date range and filters.
* Forecast ranges are approximate and probably too narrow; promotions, price changes and
  market shocks are invisible to the model.
* Dates in non-ISO formats are assumed month-first (`03/04/2024` = 4 March).
* Exact duplicate rows are treated as duplicates; legitimate identical lines would be lost.
* Currency symbol is set in `config.py` (default `₹`); there is no currency conversion.
* Whole file is processed in memory (fine for hundreds of thousands of rows, not millions).

## Ideas for future work

Optional MySQL source, targets vs actuals, product-level forecasts, cohort retention,
price/discount elasticity, role-based login, deployment to Streamlit Community Cloud.
