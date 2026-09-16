PRAGMA foreign_keys = ON;
CREATE TABLE findings (
  finding_id INTEGER PRIMARY KEY, source_file TEXT NOT NULL, source_row TEXT NOT NULL,
  person_id TEXT, code TEXT NOT NULL, severity TEXT NOT NULL, detail TEXT NOT NULL
);
CREATE TABLE people (
  person_id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
  worker_type TEXT NOT NULL CHECK(worker_type IN ('Employee','Contractor')),
  hire_date TEXT NOT NULL, termination_date TEXT,
  source_row TEXT NOT NULL, CHECK(termination_date IS NULL OR termination_date > hire_date)
);
CREATE TABLE departments (department_id TEXT PRIMARY KEY, department_name TEXT NOT NULL);
CREATE TABLE regions (region_id TEXT PRIMARY KEY, country TEXT NOT NULL, region_name TEXT NOT NULL);
CREATE TABLE assignments (
  assignment_id TEXT PRIMARY KEY, person_id TEXT NOT NULL REFERENCES people(person_id),
  department_id TEXT REFERENCES departments(department_id), region_id TEXT REFERENCES regions(region_id),
  valid_from TEXT NOT NULL, valid_to TEXT,
  CHECK(valid_to IS NULL OR valid_to > valid_from)
);
CREATE INDEX assignment_person_dates ON assignments(person_id, valid_from, valid_to);
CREATE TABLE finance (
  person_id TEXT PRIMARY KEY, department_id TEXT, region_id TEXT, reporting_date TEXT NOT NULL,
  source_row TEXT NOT NULL
);
CREATE TABLE unresolved_people (person_id TEXT PRIMARY KEY, reason TEXT NOT NULL);
CREATE TABLE run_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
