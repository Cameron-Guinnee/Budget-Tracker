# 💰 Budget Tracker

A personal finance dashboard built with [Streamlit](https://streamlit.io/) that connects directly to a Google Sheet to visualize, filter, and log income and expenses.

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

Budget Tracker pulls transaction data from a connected Google Sheet and presents it across several interactive tabs:

- **Summary** – High-level overview of income, expenses, and overall balance
- **Accounts** – Breakdown of balances and activity by account/owner
- **Breakdown** – Spending broken down by category
- **Monthly Trends** – Track how income and spending change over time
- **Expense Heatmap** – Visualize spending patterns by day/month
- **Word Cloud** – Visual summary of your most frequent transaction memos
- **Add Transaction** – Log a new transaction directly from the app
- **Data** – View and explore the raw underlying transaction data

You can filter every view by **year** and **owner** using the controls at the top of the page.

---

## 🛠️ Tech Stack

- [Streamlit](https://streamlit.io/) – web app framework
- [Google Sheets](https://www.google.com/sheets/about/) – data storage via [st-gsheets-connection](https://github.com/streamlit/gsheets-connection)
- [gspread](https://github.com/burnash/gspread) – Google Sheets API client
- [Pandas](https://pandas.pydata.org/) – data manipulation
- [Plotly](https://plotly.com/python/) – interactive charts
- [WordCloud](https://github.com/amueller/word_cloud) – word cloud generation
- [Docker](https://www.docker.com/) – containerized deployment

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- A Google Cloud service account with access to the Google Sheets API and a Google Sheet to connect to

### 1. Clone the repository

```bash
git clone https://github.com/Cameron-Guinnee/Budget-Tracker.git
cd Budget-Tracker
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure your Google Sheets connection

Create a `.streamlit/secrets.toml` file with your Google service account credentials and target spreadsheet, following the format expected by [st-gsheets-connection](https://github.com/streamlit/gsheets-connection):

```toml
[connections.gsheets]
spreadsheet = "YOUR_GOOGLE_SHEET_URL_OR_NAME"

type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "..."
client_email = "..."
client_id = "..."
# ...remaining service account fields
```

> ⚠️ Never commit `secrets.toml` to version control — it contains sensitive credentials.

### 4. Run the app

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

---

## 🐳 Running with Docker

A `Dockerfile` is included for containerized deployment:

```bash
docker build -t budget-tracker .
docker run -p 8501:8501 budget-tracker
```

---

## 📁 Project Structure

```
Budget-Tracker/
├── .streamlit/        # Streamlit configuration and secrets (not committed)
├── tabs/              # Individual tab modules (Summary, Breakdown, Trends, etc.)
├── app.py             # Main application entry point
├── styling.py         # Custom styling/theme helpers
├── utils.py           # Helper functions (Google Sheets access, etc.)
├── requirements.txt   # Python dependencies
├── Dockerfile         # Container build configuration
└── LICENSE            # MIT License
```

---

## 📋 Expected Google Sheet Format

The app expects a worksheet with (at minimum) the following columns:

| Date | Owner | Memo | Price | ... |
|------|-------|------|-------|-----|
| MM/DD/YYYY | e.g. "Alice" | Description of transaction | e.g. "$12.34" | |

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
