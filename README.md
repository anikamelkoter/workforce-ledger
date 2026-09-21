# WORKFORCE LEDGER

Prepared for the **2026 Representative Society of America Graduate Hiring Deficiency Case Study**

[View the dashboard](https://anikamelkoter.github.io/workforce-ledger/)

## THE QUESTION BEHIND THE PROJECT

Before a company decides where it needs to hire, it needs a reliable picture of who already works there. That sounds straightforward until HR and Finance produce different headcount numbers.

I focused this project on that reporting problem. Workforce Ledger brings employee records, organizational history, and Finance staffing data together so differences can be traced to individual records. The goal is to make the numbers explainable before using them to support hiring decisions.

The scope is workforce reporting. This version does not measure graduate hiring outcomes or establish that a graduate hiring shortage exists.

## THE CASE

Northstar Media Group is a fictional media company with 1,200 synthetic employee and contractor records across the United States, United Kingdom, and India. Its departments are Content, Engineering, Sales, Finance, and HR.

The source files contain the kinds of inconsistencies that can make a staffing report misleading: duplicate people, missing departments, invalid employment dates, and reports pulled at different times. HR uses an August 31, 2026 reporting date. Finance uses August 25 and leaves out five otherwise eligible employees.

All data is generated for this project. There are no real employee records or live SAP exports.

## HOW IT WORKS

Python imports the source files and checks their quality. SQLite preserves the original rows, separates unresolved employment records, and calculates historical headcount, monthly turnover, and the differences between HR and Finance. The browser dashboard presents those results with filters and record-level detail.

| Component | What it does |
| --- | --- |
| Python | Generates reproducible sample data, validates exports, and builds reporting outputs |
| SQLite and SQL | Stores source records and calculates workforce metrics using effective dates |
| JavaScript, HTML, and CSS | Displays workforce trends, reconciliation details, and data-quality findings |
| Automated tests | Check reporting accuracy against known results and exercise failure cases |

One decision matters throughout the project: a missing department should not make an otherwise valid employee disappear from the company-wide count. Those people remain countable, with their organization shown as Unknown. An invalid employment date is different because it can make active status impossible to establish. Those records are set aside and the report stays provisional.

## What the sample run shows

The pipeline identifies all 21 planted data-quality issues:

- Ten duplicate person records with identical business fields.
- Five termination dates that precede hire dates.
- Five missing department assignments.
- One invalid region.

After excluding unresolved employment records, the August 31 report contains **963 validated employees**. Finance reports **962 employees** at its earlier cutoff.

That one-person difference is only the net result. The reconciliation shows the individual additions, exclusions, and unresolved records behind it. Five employment records still require review, so the dashboard labels the results **provisional**.

The clean test data contains 967 active employees at August 31. That figure is an acceptance-test benchmark, not a correction silently applied to the report. The reporting pipeline never reads the answer keys.

## Reporting definitions

| Measure | Definition |
| --- | --- |
| Employee headcount | Distinct active employees on the reporting date, excluding contractors |
| Total workforce | Active employees and contractors combined |
| Active status | Hire date is on or before the reporting date; termination date is blank or later |
| Historical department and region | The assignment effective on the selected reporting date |
| Monthly turnover | Employee departures divided by average opening and closing headcount, multiplied by 100 |
| Internal transfer | An organizational change during continuous employment, rather than a new hire or departure |

Termination dates represent the first day a person is no longer employed. Assignment start dates are inclusive and end dates are exclusive. Monthly turnover is not annualized, and partial final months are omitted from monthly reporting.

## Explore the project

The [live dashboard](https://anikamelkoter.github.io/workforce-ledger/) includes:

- Workforce counts filtered by department and region.
- Company-wide monthly headcount and turnover values.
- Searchable employee and contractor records with CSV download.
- A record-level HR and Finance reconciliation.
- Data-quality findings with source references and explanations.

Region and department filters apply to the workforce snapshot. The monthly trend and reconciliation remain company-wide. The page contains a generated reporting snapshot, so it does not query a live database.

## Run locally

Python 3.10 or newer is sufficient. No third-party Python packages are required.

Download or clone the repository, then run these commands from its root folder:

```bash
# Validate the source files and generate a database and reports
python3 pipeline.py

# Run the acceptance tests
python3 -m unittest discover -s tests -v

# Refresh the browser dashboard from a new pipeline run
python3 build_dashboard.py
```

On Windows, use `py` in place of `python3` if needed.

Open `index.html` in a browser to view the dashboard locally. Viewing the existing dashboard does not require Python or a web server.

Each pipeline run creates a separate folder under `output/`. Start with `summary.json`, then inspect `findings.csv` and `reconciliation.csv`. Generated databases and run folders are excluded from Git.

To regenerate the synthetic source files:

```bash
python3 generate_data.py
```

The generator uses seed 42 and overwrites its generated source files and test fixtures. Keep any manually reviewed exports in a separate folder.

## Repository guide

| Path | Contents |
| --- | --- |
| `data/raw/` | Simulated HR exports, Finance staffing records, and organizational directories |
| `data/manifest.json` | Hashes for the generated source files |
| `generate_data.py` | Reproducible synthetic-data generator |
| `pipeline.py` | Validation, database loading, and report generation |
| `sql/` | Database schema and reporting queries |
| `tests/` | Ten acceptance tests and isolated reference fixtures |
| `build_dashboard.py` | Generates the dashboard from pipeline results |
| `dashboard/template.html` | Dashboard layout and interaction code |
| `index.html` | Generated dashboard published through GitHub Pages |
| `docs/PIPELINE.md` | Detailed running instructions, correction process, and limitations |

## Validation and remaining work

The ten acceptance tests cover planted errors, preservation of source rows, clean-data reporting accuracy, employment and transfer boundaries, conflicting duplicates, overlapping assignments, malformed dates, invalid source structure, partial months, and repeatable runs.

The current model assumes one continuous employment spell and a fixed worker type per person. Rehires, simultaneous assignments, manager hierarchies, and graduate-specific recruitment measures are outside its scope.

Native Power BI reporting, live SAP or Snowflake connections, and enforced regional access controls are not implemented. Dashboard filters are display controls, not security restrictions. Browser visual testing remains pending; the embedded reporting data and JavaScript syntax have been checked.
