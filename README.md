# 💰 Ledgerline

A personal finance dashboard built with [Streamlit](https://streamlit.io/) that connects to Google Sheets to visualize, filter, and log transactions across a **Ledger** (income & expenses), a **Portfolio** (stocks & crypto), and a **Net Worth** overview combining both.

**🔗 Live Demo:** [budget-tracker-hqzvmiazybvhhkjkv4pih8.streamlit.app](https://budget-tracker-hqzvmiazybvhhkjkv4pih8.streamlit.app/)

---

## 📸 Screenshots

> *Add screenshots of the app here to give visitors a quick preview.*

| Summary | Breakdown |
|---|---|
| ![Summary tab screenshot](docs/screenshots/summary.png) | ![Breakdown tab screenshot](docs/screenshots/breakdown.png) |

| Monthly Trends | Expense Heatmap |
|---|---|
| ![Monthly trends screenshot](docs/screenshots/monthly-trends.png) | ![Expense heatmap screenshot](docs/screenshots/heatmap.png) |

---

## ✨ Features

### 📒 Ledger

Pulls transaction data from a connected Google Sheet and presents it across several interactive tabs. A persistent KPI row shows **income**, **expenses**, **net savings**, and **savings rate** at a glance — with year-over-year deltas when viewing a specific year. Filter every view by **year** and **owner** using the sidebar.

- **Summary** – Donut charts for the savings/expenses split and expense breakdown by category; shared-expense split by owner (when multiple owners are configured)
- **Accounts** – Balance over time per account with configurable date ranges (7D, 1M, 3M, YTD, 1Y, All, Custom) and granularity (Daily, Weekly, Monthly); optional APY interest tracking that compares projected vs. logged interest per account
- **Breakdown** – Spending by category as a bar chart, with optional per-owner grouping and a toggle to show or hide savings
- **Monthly Trends** – Income vs. expenses by month as a combined line/bar chart
- **Expense Heatmap** – Spending by category and month as a color-intensity heatmap
- **Word Cloud** – Visual frequency map of transaction memos weighted by dollar amount
- **Budgets** – Actual spend vs. configured monthly budgets, with 🟢/🟡/🔴 indicators, percent-used progress bars, and unbudgeted category detection
- **Insights** – Three sub-tabs:
  - *Subscriptions* – Detects recurring memos appearing across 3+ months at a consistent amount, with estimated annual cost
  - *Anomalies* – Flags transactions that are statistical outliers (configurable Z-score threshold) within their category
  - *Export* – Downloads filtered transaction data as CSV or Excel (with a summary sheet)
- **Data** – Color-coded transaction table with a live memo search filter
- **Add Transaction** – Log a new transaction directly to the sheet, with optional saved presets for common entries

### 💼 Portfolio

Pulls investment transactions from a separate Google Sheet and tracks your positions in real time via [yfinance](https://github.com/ranaroussi/yfinance).

- **Holdings** – Open positions with live prices, portfolio weight %, unrealized P&L, realized gains, and dividends received; closed positions in a separate section
- **Performance** – Portfolio value over time (area chart) with optional SPY/QQQ benchmark overlay; drawdown chart; XIRR (money-weighted return), Sharpe ratio, max drawdown, and volatility KPIs; realized gains & dividends by symbol; full tax-lot report with short/long-term classification and CSV export
- **Allocation** – Donut charts by symbol, asset type (Stock vs. Crypto), and sector; treemap view drilling down by type → sector → symbol
- **Dividends** – Historical dividend income by quarter, yield-on-cost, projected annual income, current yield, and upcoming ex-dividend dates
- **Add Transaction** – Log Buy, Sell, or Dividend transactions to the portfolio sheet

### 📊 Net Worth

Combines ledger account balances with live portfolio value into a single unified view.

- Current snapshot KPIs: **Account Balances**, **Portfolio Value**, **Net Worth** (with a data-through timestamp)
- Net Worth over time (area chart) with Account Balances and Portfolio as dotted overlay lines
- Assets & Liabilities breakdown as side-by-side donut charts

---

## 🛠️ Tech Stack

| Library | Purpose |
|---|---|
| [Streamlit 1.58](https://streamlit.io/) | Web app framework |
| [gspread](https://github.com/burnash/gspread) + [st-gsheets-connection](https://github.com/streamlit/gsheets-connection) | Google Sheets read/write |
| [Pandas](https://pandas.pydata.org/) | Data manipulation |
| [Plotly](https://plotly.com/python/) | Interactive charts |
| [yfinance](https://github.com/ranaroussi/yfinance) | Live and historical market prices |
| [WordCloud](https://github.com/amuelman/word_cloud) | Word cloud generation |
| [Docker](https://www.docker.com/) | Containerized deployment |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- A Google Cloud service account with access to the Google Sheets API

### 1. Clone the repository

```bash
git clone https://github.com/Cameron-Guinnee/Ledgerline.git
cd Ledgerline
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure your Google Sheets connections

Create a `.streamlit/secrets.toml` file with your service account credentials. The Ledger and Portfolio pages each use their own connection key.

```toml
# ── Ledger connection ────────────────────────────────────────────────────────
[connections.gsheets]
type        = "service_account"
spreadsheet = "https://docs.google.com/spreadsheets/d/<YOUR_LEDGER_SHEET_ID>/edit"
worksheet   = "Sheet1"   # worksheet name or 0-based index
project_id      = "..."
private_key_id  = "..."
private_key     = "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
client_email    = "...@....iam.gserviceaccount.com"
client_id       = "..."
auth_uri        = "https://accounts.google.com/o/oauth2/auth"
token_uri       = "https://oauth2.googleapis.com/token"

# ── Portfolio connection (optional) ──────────────────────────────────────────
[connections.portfolio_gsheets]
type        = "service_account"
spreadsheet = "https://docs.google.com/spreadsheets/d/<YOUR_PORTFOLIO_SHEET_ID>/edit"
worksheet   = 0
# ... same service account credential fields as above ...
```

> ⚠️ Never commit `secrets.toml` to version control — it contains sensitive credentials.

### 4. (Optional) Configure owners, budgets, presets, and APY

All optional configuration lives in `secrets.toml`:

```toml
# ── Multi-owner support ───────────────────────────────────────────────────────
[[expense_tracker.owners]]
name  = "Alice"
color = "#4169e1"

[[expense_tracker.owners]]
name  = "Bob"
color = "#fc0000"

# ── Monthly budget targets (used in the Budgets tab) ─────────────────────────
[expense_tracker.budgets]
Grocery       = 500
Dining        = 200
Entertainment = 100

# ── Add Transaction presets (quick-fill common entries) ──────────────────────
[[expense_tracker.transaction_tab.presets]]
memo           = "Rent"
category       = "Housing"
owner          = "Alice"
payment_method = "Check"
price          = 1500

[expense_tracker.transaction_tab.defaults]
shared = false

# ── Account APY tracking (shown in the Accounts tab) ─────────────────────────
[[expense_tracker.accounts]]
name = "High Yield Savings"
apy  = 4.5
```

### 5. Run the app

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

---

## 🐳 Running with Docker

A `Dockerfile` is included for containerized deployment:

```bash
docker build -t ledgerline .
docker run -p 8501:8501 ledgerline
```

---

## 📁 Project Structure

```
Ledgerline/
├── .streamlit/
│   ├── config.toml           # Committed theme configuration
│   └── secrets.toml          # Local credentials (never committed)
├── pages/
│   ├── ledger.py             # Ledger page (income & expense tracking)
│   ├── portfolio.py          # Portfolio page (investment tracking)
│   └── net_worth.py          # Net Worth page (combined overview)
├── tabs/                     # Ledger tab modules
│   ├── summary_tab.py
│   ├── accounts_tab.py
│   ├── breakdown_tab.py
│   ├── monthly_trends_tab.py
│   ├── expense_heatmap_tab.py
│   ├── wordcloud_tab.py
│   ├── budgets_tab.py
│   ├── subscriptions_tab.py
│   ├── add_transaction_tab.py
│   └── df_tab.py
├── portfolio_tabs/           # Portfolio tab modules
│   ├── holdings_tab.py
│   ├── performance_tab.py
│   ├── allocation_tab.py
│   ├── dividends_tab.py
│   └── add_transaction_tab.py
├── app.py                    # Main entry point (navigation setup)
├── styling.py                # Color maps and styling helpers
├── utils.py                  # Ledger Google Sheets and config helpers
├── portfolio_utils.py        # Portfolio data, market prices, and analytics
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container build configuration
└── LICENSE                   # MIT License
```

---

## 📋 Expected Google Sheet Formats

### Ledger Sheet

The first row is treated as a header. Columns used by the app:

| Date | Memo | Category | Owner | Account | Price | Payment Method | Shared |
|------|------|----------|-------|---------|-------|----------------|--------|
| MM/DD/YYYY | Description | e.g. "Dining" | e.g. "Alice" | e.g. "Checking" | e.g. "$12.34" | Credit / Debit / Cash / Check | Yes / No |

`Category` values drive chart colors. The built-in categories are defined in `styling.py`. Use `"Income"` to mark income rows and `"Transfer In"` / `"Transfer Out"` for inter-account transfers (these are excluded from expense totals).

### Portfolio Sheet

| Date | Symbol | Asset Type | Transaction Type | Shares | Price Per Share | Total | Notes |
|------|--------|------------|-----------------|--------|-----------------|-------|-------|
| MM/DD/YYYY | e.g. AAPL | Stock / Crypto | Buy / Sell / Dividend | e.g. 10 | e.g. 150.00 | e.g. 1500.00 | Optional |

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
