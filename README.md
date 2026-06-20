# 💰 Ledgerline

A personal finance dashboard built with [Streamlit](https://streamlit.io/) that connects to Google Sheets to visualize, filter, and log transactions across a **Ledger** (income & expenses) and a **Portfolio** (stocks & crypto).

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

Pulls transaction data from a connected Google Sheet and presents it across several interactive tabs, with a KPI row showing income, expenses, net savings, and savings rate at a glance. Filter every view by **year** and **owner** using the sidebar.

- **Summary** – Donut charts for savings/expenses split and expense breakdown by category; shared-expense split by owner (when multiple owners are configured)
- **Accounts** – Balance over time per account with configurable date ranges and granularity
- **Breakdown** – Spending by category as a bar chart, with optional per-owner grouping
- **Monthly Trends** – Income vs. expenses by month as a combined line/bar chart
- **Expense Heatmap** – Spending by category and month as a color heatmap
- **Word Cloud** – Visual frequency map of transaction memos weighted by amount
- **Add Transaction** – Log a new transaction directly to the sheet, with optional presets
- **Data** – Color-coded, filterable view of the underlying transaction table

### 💼 Portfolio

Pulls investment transactions from a separate Google Sheet and tracks your positions in real time via [yfinance](https://github.com/ranaroussi/yfinance).

- **Holdings** – Open positions with live prices, current value, unrealized P&L, realized gains, and dividends
- **Performance** – Portfolio value over time (area chart) and realized gains/dividends by symbol
- **Allocation** – Donut charts by symbol and asset type, plus a treemap
- **Add Transaction** – Log Buy, Sell, or Dividend transactions to the portfolio sheet

---

## 🛠️ Tech Stack

- [Streamlit](https://streamlit.io/) – web app framework
- [Google Sheets](https://www.google.com/sheets/about/) – data storage via [st-gsheets-connection](https://github.com/streamlit/gsheets-connection) and [gspread](https://github.com/burnash/gspread)
- [Pandas](https://pandas.pydata.org/) – data manipulation
- [Plotly](https://plotly.com/python/) – interactive charts
- [yfinance](https://github.com/ranaroussi/yfinance) – live and historical market prices
- [WordCloud](https://github.com/amuelman/word_cloud) – word cloud generation
- [Docker](https://www.docker.com/) – containerized deployment

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
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
# ── Ledger connection ───────────────────────────────────────────────────────
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

# ── Portfolio connection (optional) ────────────────────────────────────────
[connections.portfolio_gsheets]
type        = "service_account"
spreadsheet = "https://docs.google.com/spreadsheets/d/<YOUR_PORTFOLIO_SHEET_ID>/edit"
worksheet   = 0
# ... same service account credential fields as above ...
```

> ⚠️ Never commit `secrets.toml` to version control — it contains sensitive credentials.

### 4. (Optional) Configure owners and presets

You can add per-owner colors and Add Transaction presets in `secrets.toml`:

```toml
[expense_tracker]
[[expense_tracker.owners]]
name  = "Alice"
color = "#4169e1"

[[expense_tracker.owners]]
name  = "Bob"
color = "#fc0000"

[[expense_tracker.transaction_tab.presets]]
memo           = "Rent"
category       = "Housing"
owner          = "Alice"
payment_method = "Check"

[expense_tracker.transaction_tab.defaults]
shared = false
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
├── .streamlit/           # Streamlit configuration and secrets (not committed)
├── pages/
│   ├── ledger.py         # Ledger page (income & expense tracking)
│   └── portfolio.py      # Portfolio page (investment tracking)
├── tabs/                 # Ledger tab modules
│   ├── summary_tab.py
│   ├── accounts_tab.py
│   ├── breakdown_tab.py
│   ├── monthly_trends_tab.py
│   ├── expense_heatmap_tab.py
│   ├── wordcloud_tab.py
│   ├── add_transaction_tab.py
│   └── df_tab.py
├── portfolio_tabs/       # Portfolio tab modules
│   ├── holdings_tab.py
│   ├── performance_tab.py
│   ├── allocation_tab.py
│   └── add_transaction_tab.py
├── app.py                # Main entry point (navigation setup)
├── styling.py            # Color maps and styling helpers
├── utils.py              # Ledger Google Sheets helpers
├── portfolio_utils.py    # Portfolio Google Sheets helpers and market data utilities
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container build configuration
└── LICENSE               # MIT License
```

---

## 📋 Expected Google Sheet Formats

### Ledger Sheet

The first row is treated as a header. Columns used by the app:

| Date | Memo | Category | Owner | Account | Price | Payment Method | Shared |
|------|------|----------|-------|---------|-------|----------------|--------|
| MM/DD/YYYY | Description | e.g. "Dining" | e.g. "Alice" | e.g. "Checking" | e.g. "$12.34" | Credit / Debit / Cash / Check | Yes / No |

`Category` values drive chart colors. The built-in categories are listed in `styling.py`. Use `"Income"` to mark income rows.

### Portfolio Sheet

| Date | Symbol | Asset Type | Transaction Type | Shares | Price Per Share | Total | Notes |
|------|--------|------------|-----------------|--------|-----------------|-------|-------|
| MM/DD/YYYY | e.g. AAPL | Stock / Crypto | Buy / Sell / Dividend | e.g. 10 | e.g. 150.00 | e.g. 1500.00 | Optional |

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
