-- Union retains both missing HR records and missing Finance records.
-- delta bridges Finance to VALIDATED employee headcount; unresolved reasons remain visible.
WITH ids AS (SELECT person_id FROM people UNION SELECT person_id FROM finance UNION SELECT person_id FROM unresolved_people),
membership AS (
 SELECT i.person_id, p.worker_type, p.hire_date, p.termination_date,
        f.reporting_date, u.reason AS unresolved_reason,
        CASE WHEN f.person_id IS NOT NULL THEN 1 ELSE 0 END AS finance_count,
        CASE WHEN p.worker_type='Employee' AND p.hire_date<=:as_of
          AND (p.termination_date IS NULL OR p.termination_date>:as_of) THEN 1 ELSE 0 END AS validated_count
 FROM ids i LEFT JOIN people p USING(person_id) LEFT JOIN finance f USING(person_id)
 LEFT JOIN unresolved_people u USING(person_id)
)
SELECT person_id, finance_count, validated_count, validated_count-finance_count AS delta,
 CASE WHEN unresolved_reason IS NOT NULL THEN 'unresolved_hr_record'
      WHEN worker_type IS NULL THEN 'unknown_hr_person'
      WHEN worker_type='Contractor' THEN 'worker_type_difference'
      WHEN finance_count=0 AND hire_date>:finance_date AND hire_date<=:as_of THEN 'cutoff_difference'
      WHEN finance_count=1 AND termination_date>:finance_date AND termination_date<=:as_of THEN 'cutoff_difference'
      WHEN finance_count=0 THEN 'missing_finance_record'
      ELSE 'unexpected_finance_record' END AS reason
FROM membership WHERE finance_count<>validated_count OR unresolved_reason IS NOT NULL
ORDER BY person_id;
