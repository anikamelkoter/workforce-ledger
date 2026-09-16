# Running Workforce Ledger

## Quick start

Python 3.10 or newer is the only requirement. No installation, database server or third-party packages are required.

From the unzipped `workforce-ledger` folder:

```sh
python3 pipeline.py
python3 -m unittest discover -s tests -v
```

On Windows use `python` if `python3` is unavailable. Each pipeline run creates a separate folder under `output/`. Open its `summary.json` first, followed by `findings.csv` and `reconciliation.csv`. The browser dashboard contains a completed example. Generated SQLite files are excluded from Git; run the pipeline to create your own. A `COMPLETE` file means processing finished, not that source quality is perfect. Failed runs have `FAILED.txt` and must not be used for reporting.

To change the reporting date:

```sh
python3 pipeline.py --as-of 2026-08-28 --start-month 2026-01-01
```

The Finance date cannot be later than the report date. Monthly output excludes a partial final month. The default report date is August 31, 2026.

## What is implemented

The database stores every CSV row in `stage_*` tables with its original values and CSV line number. Validation creates separate `findings`, accepted `people`, usable `assignments`, reference directories, and an `unresolved_people` register. Source hashes are stored in `run_metadata`. Reruns preserve earlier output folders and never edit inputs.

Identical person duplicates retain the first occurrence and emit warnings. Conflicting business fields quarantine the person. Invalid employment dates also quarantine the person. Assignment gaps, overlaps and mismatched employment boundaries exclude organizational history without removing the valid person from global headcount. Missing or invalid department/region values become Unknown. Unknown HR identities in Finance remain in the reconciliation.

The application executes the SQL in `sql/` with bound date parameters. `snapshot.sql` reconstructs historical assignments, `monthly.sql` computes employee headcount and turnover, and `reconciliation.sql` explains differences between Finance and validated employee totals. SQLite can be opened with a database viewer for inspection, or queried with Python's built-in sqlite3.

## Interpreting the default result

The supplied dirty-source run detects 21 findings and quarantines five people. Its validated employee count is 963 and Finance's count is 962. The result is PROVISIONAL. The clean test-fixture headcount is 967; that number is not used by the production pipeline. Four quarantined people are active employees at the reporting date in the synthetic truth. The fifth is not active then.

The reconciliation delta of +1 is an arithmetic bridge to the currently validated population. It includes unresolved HR exclusions, cutoff differences and missing Finance records. A balanced bridge is not evidence that the sources have been fully resolved. Employee-level Finance discrepancies can cancel numerically, so inspect record-level reasons even when a headline delta is small.

## Correction procedure

1. Review a finding's file, source-row ID and person ID against the original source.
2. Ask the simulated source owner to verify the questionable field. Never infer an employment date from a missing dashboard record.
3. Preserve the original raw folder. Put a reviewed replacement export in a separate folder with the same source contracts.
4. Keep a correction log containing old value, replacement, reason, reviewer and review date.
5. Run with `--input path/to/reviewed_exports`. Compare the new findings and metrics to the earlier run.

No reviewed corrections are supplied or claimed. Test fixtures are used only by isolated acceptance tests, which create temporary clean exports to validate SQL accuracy. There is no automatic use of the answer key in pipeline.py.

## Scope and limitations

This is a local portfolio prototype, with no authentication, row-level security, live SAP/Snowflake connection or Power BI report yet. CSV exports and the database contain only synthetic people. The pipeline assumes one employment spell per person, one Finance snapshot per file, fixed worker type, and complete assignment history. Malformed CSV structure, duplicate directory keys and duplicate Finance person IDs stop a run. Source extraction timestamps are preserved, but freshness and timezone correctness are not currently validated. Finance organizational fields are preserved for inspection; the current reconciliation compares membership, not department allocation. No record of formal approvals is implied.

The browser dashboard now displays these outputs, including provisional status and unresolved records. Rebuild it with `python3 build_dashboard.py`. Native Power BI integration remains pending.
