# Risk Metrics Analyst Agent

An intelligent Streamlit application for analyzing financial risk metrics with AI-powered insights, interactive visualizations, and comprehensive reporting.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.52.0-red.svg)

## Features

### 📊 Risk Metrics Analysis
- Upload CSV files containing risk metrics (VaR, SVaR, STTHH, sensitivities, etc.)
- Automatic metric detection and organization by priority and maturity
- Statistical analysis including mean, median, standard deviation, min/max, and outlier detection (±2σ)
- Limit breach detection and reporting

### 🤖 AI-Powered Insights
- Integration with Google Gemini for intelligent metric commentary
- Portfolio-level summary generation
- Configurable LLM analysis (can be disabled for faster processing)

### 📈 Interactive Visualizations
- Plotly-based interactive time series charts
- Overlay of statistical indicators (mean, median lines)
- Limit threshold visualization
- Outlier highlighting
- Adaptive scaling for metrics with large limit ranges

### 🔍 Metric Filtering
- **Keyword Exclusion Filter**: Exclude metrics by comma-separated keywords (case-insensitive)
- **Limit Filter**: Option to show only metrics with defined limits
- Live preview of excluded metric count
- Maximum 50 exclusion keywords supported

### 📦 Batch Processing
- Automatic detection of multi-node datasets via `stranaNodeName` column
- Per-node analysis with tabbed UI display
- Batch export with node-folder structure

### 📄 Export Options
- **HTML Report**: Single-file interactive report with an executive summary (KPI strip + status table), status-aware navigation, embedded charts, and AI commentary
- **Self-contained mode**: Optionally embed Plotly and styling so the report renders fully offline (no CDN/network dependency). ZIP packages are self-contained by default; the single-file HTML download offers a checkbox.
- **ZIP Package**: Complete export with HTML report, PNG chart images, and text summary
- Excluded metrics section in reports showing filter reasons (user keywords vs. missing limits)

### 🧭 Report Navigation & Status
- Executive summary at the top: counts of breached / outlier / within-limit metrics plus a severity-sorted table with latest value and limit utilization
- Navigation dots and per-metric badges colour-coded by status (breach / outlier / OK)
- Filter the metric navigation by status, in addition to free-text search
- Per-metric stat cards include the latest value and colour-coded limit utilization (%)

## Project Structure

```
Risk-Metrics-Analyst-Agent/
├── app_main.py                 # Application entry point
├── requirements.txt            # Python dependencies
├── README.md
├── Examples/
│   └── Fake Pivot Metrics.csv  # Sample data for testing
├── Output/                     # Generated reports and charts
└── risk_metrics_app/
    ├── __init__.py
    ├── assets/                 # Vendored front-end assets (Tailwind runtime for offline reports)
    ├── app.py                  # Streamlit UI and workflow
    ├── config.py               # Configuration and constants
    ├── extraction.py           # Mock API data extraction
    ├── llm.py                  # Gemini LLM orchestration
    ├── metrics.py              # Data processing and statistics
    ├── prompts.py              # LLM prompt templates
    ├── reporting.py            # HTML/ZIP export generation
    └── visuals.py              # Plotly chart creation
```

## Quick Start

### Prerequisites
- Python 3.11 or higher
- Google API key (for AI insights feature)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/KaFaiLi/Risk-Metrics-Analyst-Agent.git
cd Risk-Metrics-Analyst-Agent
```

2. Create and activate a virtual environment:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:
```powershell
pip install -r requirements.txt
```

4. Run the application:
```powershell
streamlit run app_main.py
```

## Usage

### Data Format
Upload a CSV file with the following structure:
- **ValueDate** column (required): Date column for time series
- **Metric columns**: Numeric columns containing risk metric values
- **Limit columns** (optional): Columns with `_limMaxValue` or `_limMinValue` suffixes
- **stranaNodeName** column (optional): Enables batch mode for multi-node analysis

### Workflow
1. **Upload** your CSV file via the sidebar
2. **Configure** analysis options:
   - Enable/disable AI insights
   - Filter metrics by keywords (e.g., "basis, theta, gamma")
   - Toggle "Only show metrics with limits"
3. **Run Analysis** to generate statistics and visualizations
4. **Export** results as HTML report or complete ZIP package

### Example
Use the provided sample file at `Examples/Fake Pivot Metrics.csv` to explore all features.

## Configuration

Key constants in `risk_metrics_app/config.py`:
- `MAX_EXCLUSION_KEYWORDS`: Maximum number of filter keywords (default: 50)
- `MAX_LLM_CONCURRENCY`: Parallel LLM request limit
- `PRIORITY_METRICS`: Metrics shown first (`['VaR', 'SVaR', 'STTHH']`)

## API Key Setup
Enter your Google API key in the sidebar text input. The key is stored in the environment variable `GOOGLE_API_KEY` for the session.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
