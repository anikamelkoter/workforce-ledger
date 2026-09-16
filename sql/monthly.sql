-- :start_month and :end_month are first-of-month ISO dates (inclusive).
WITH RECURSIVE months(first_day) AS (
  SELECT :start_month
  UNION ALL SELECT date(first_day, '+1 month') FROM months WHERE first_day < :end_month
), boundaries AS (
  SELECT first_day, date(first_day, '-1 day') AS opening_date,
         date(first_day, '+1 month', '-1 day') AS closing_date FROM months
), metrics AS (
  SELECT substr(first_day,1,7) AS month,
    (SELECT count(*) FROM people WHERE worker_type='Employee' AND hire_date<=opening_date
      AND (termination_date IS NULL OR termination_date>opening_date)) AS opening_headcount,
    (SELECT count(*) FROM people WHERE worker_type='Employee' AND hire_date BETWEEN first_day AND closing_date) AS hires,
    (SELECT count(*) FROM people WHERE worker_type='Employee' AND termination_date BETWEEN first_day AND closing_date) AS departures,
    (SELECT count(*) FROM people WHERE worker_type='Employee' AND hire_date<=closing_date
      AND (termination_date IS NULL OR termination_date>closing_date)) AS closing_headcount
  FROM boundaries
)
SELECT *, round(100.0*departures / NULLIF((opening_headcount+closing_headcount)/2.0,0),6) AS turnover_pct
FROM metrics;
