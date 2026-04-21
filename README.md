# Tesla FDE Case Study

This repository contains a Python analysis workflow and Streamlit dashboard for a Tesla Forward Deploy Engineer (FDE) case study.

The project is designed to answer three core questions:
- What went wrong at previous deployment sites?
- Where are the likely user and operational pain points?
- What should be prioritized for a new site deployment?

## Project Structure

- `data/`  
  Source Excel workbooks used for inspection and analysis.
- `src/load_data.py`  
  Loads all sheets, standardizes column names, prints inspection details, and saves workbook summaries.
- `src/analyze.py`  
  Builds derived metrics, diagnostic summaries, risk ranking, and exports presentation charts.
- `src/app.py`  
  Streamlit dashboard for presentation/demo walkthrough.
- `src/utils.py`  
  Shared helpers for paths, directory handling, and string normalization.
- `outputs/cleaned/`  
  Analysis tables and findings CSV/Markdown outputs.
- `outputs/charts/`  
  Plotly chart HTML artifacts for presentation.

## Setup

### 1) Create and activate virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

## Run the Analysis Pipeline

Run the full inspection + diagnostics pipeline:

```bash
.venv/bin/python src/analyze.py
```

This will:
- inspect all workbook sheets
- generate cleaned summary tables in `outputs/cleaned/`
- generate executive charts in `outputs/charts/`
- refresh diagnostic findings text outputs

## Run the Dashboard

```bash
.venv/bin/streamlit run src/app.py
```

Dashboard includes:
- sidebar filters (site/team/system/week range)
- KPI cards
- deployment breakdown charts
- intervention-priority visuals
- explainable risk score breakdown by site

## Key Outputs

Common files in `outputs/cleaned/`:
- `diagnostic_findings.csv`
- `problem_area_ranking.csv`
- `problem_score_contributions_by_site.csv`
- `deployment_event_risk_by_site.csv`
- `financial_variance_by_site_category.csv`
- `pain_points_summary.csv`
- `adoption_operational_metrics.csv`
- `key_findings.md`

Common files in `outputs/charts/`:
- `01_Executive_Cost_Overrun_Priorities.html`
- `02_Executive_Deployment_Breakdown_Risk_Map.html`
- `03_Executive_Adoption_Friction_Trend.html`
- `04_Executive_Intervention_Priorities_by_Team.html`
- `05_Executive_Site_Intervention_Priority.html`
- `06_Executive_Reporting_Reliability_Gaps.html`

## Notes for Interview Use

- The composite risk score is a **directional prioritization metric** (not a calibrated predictive model).
- Site labels are preserved from source data; any family/group normalization is used for explainability only.
- Chart and dashboard wording has been tuned for concise, defensible presentation in a short walkthrough.
