# Workforce Ledger: data and reporting pipeline

Northstar Media Group is fictional. All records are synthetic and generated locally. This package includes source generation, a working Python/SQLite validation and reporting pipeline, acceptance tests, and example outputs. An interactive browser dashboard is included. Native Power BI implementation is still pending.

## Start here

Download this repository as a ZIP, extract it, and open `index.html` in a browser. No server is needed. Explore region and department filters, employee search, CSV download, monthly trends, Finance reconciliation, and source-quality findings.

Run `python3 build_dashboard.py` to refresh the dashboard from a new pipeline run. GitHub Pages can serve `index.html` if Pages is configured for the root of `main`; committing the files does not enable hosting.

Run `python3 pipeline.py` to build the database and reports. Run `python3 -m unittest discover -s tests -v` to run acceptance tests. Read `docs/PIPELINE.md` for instructions, actual results and limitations. The pipeline preserves source files and marks unresolved reporting as provisional.

Open `data/raw/` to inspect five CSV source files. To reproduce them, run `python3 generate_data.py` from this folder with Python 3.10 or newer. No third-party dependencies or accounts are required. The script overwrites its generated files in this package, so keep edits elsewhere. The default seed is 42 and output is reproducible.

The simulated reporting date is August 31, 2026. Finance uses August 25. HR extracts contain employment history, including future hires and recorded future departures. Date filtering is required. These are simulated exports, not actual SAP exports.

## Source contracts

All CSVs are UTF-8 with headers. Identifiers are text, dates use YYYY-MM-DD, extraction timestamps use UTC, and an empty end date means open-ended. No salary, demographic, contact, or real personal data is included.

| File | Grain and intended key | Fields |
|---|---|---|
| hr_people.csv | One export row; source_row_id unique, person_id intended unique | person_id joins assignments and Finance; display_name is synthetic; worker_type is Employee or Contractor; hire_date inclusive; termination_date exclusive; extracted_at is export timestamp |
| hr_assignments.csv | One effective-dated assignment; assignment_id unique | person_id references people; department_id and region_id reference directories; valid_from inclusive, valid_to exclusive; extracted_at is export timestamp |
| finance_staffing.csv | One person per reporting date; finance_row_id unique | person_id, department_id, region_id, reporting_date, extracted_at; contains employees only |
| departments.csv | One department; department_id unique | department_name: Content, Engineering, Sales, Finance, HR |
| regions.csv | One country-level reporting unit; region_id unique | country and region_name; US, UK and IN map to North America, Europe and Asia |

Each person has one continuous employment spell and a fixed worker type. Rehires, simultaneous assignments and worker-type changes are deferred. Manager hierarchies are also deferred. Assignment intervals cover the employment spell exactly in the truth fixtures. Source files intentionally break some contracts.

## Agreed business requirements

Count distinct active employees for headcount, excluding contractors. Show total workforce separately. Active means hire_date <= reporting date and termination_date is blank or greater than reporting date. Resolve department and region using the same date against assignment intervals. Transfers do not count as hires or departures. Opening monthly headcount is the previous month's closing count. Turnover is employee departures divided by average opening and closing employee headcount, expressed as a percentage and not annualized. All business dates use the agreed company calendar; UTC timestamps describe extraction, not employment events.

HR leaders need overall staffing and trends, regional HR needs its region, Finance needs a record-level reconciliation, and analysts need data-quality exceptions. Real regional enforcement belongs in the later reporting environment; this package provides no access controls.

## Deliberate scenarios

* Ten duplicate people are appended to HR with separate source-row IDs. Do not count export rows as people.
* Five HR termination dates precede hire dates. Quarantine or resolve them through a documented correction workflow; do not silently substitute truth fixtures.
* Five assignment department IDs are blank and one region is invalid.
* Finance excludes contractors, uses an earlier cutoff, and omits five otherwise eligible employees.
* Twenty known employees transfer from the US to the UK on August 15. A controlled cohort also contains ten UK hires and ten UK departures on August 20. Other generated employees have additional activity, so the full UK's net change is not necessarily twenty.

Missing organizational data need not erase a valid person from global headcount: keep organizational completeness separate from employment validity. Invalid employment dates can prevent a reliable active-status determination. The later pipeline should expose unresolved counts and avoid presenting quarantined-data totals as fully reconciled.

## Independent acceptance fixtures

`tests/fixtures/` holds pre-corruption truth, injected issue locations, expected monthly metrics and a record-level reconciliation. This is the answer key for tests, not a production input or a hidden correction source. The expected reconciliation compares clean employee headcount at August 31 with Finance at August 25. It does not explain raw HR row counts or contractors; show those as separate bridges in the later dashboard.

`summary.json` records actual generated counts. `data/manifest.json` records source hashes. The generator checks employment interval continuity, monthly headcount roll-forwards and reconciliation arithmetic. These checks validate the fixture design; they do not establish that a future validation pipeline works.

## Implemented reporting stage

`pipeline.py` and `sql/` now implement staging, validation findings, quarantine, historical headcount, monthly turnover, and a record-level Finance reconciliation. `tests/test_pipeline.py` verifies the results against isolated truth fixtures and exercises failure cases. `build_dashboard.py` embeds pipeline results into the browser dashboard. Power BI remains a separate implementation step.
