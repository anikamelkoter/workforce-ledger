-- Parameters: :as_of. Intervals include start and exclude end.
-- Missing organizational assignments must not remove valid active people.
SELECT p.person_id, p.display_name, p.worker_type,
       COALESCE(d.department_name, 'Unknown') AS department,
       COALESCE(r.region_name, 'Unknown') AS region,
       a.department_id, a.region_id
FROM people p
LEFT JOIN assignments a ON a.person_id = p.person_id
  AND a.valid_from <= :as_of AND (a.valid_to IS NULL OR a.valid_to > :as_of)
LEFT JOIN departments d ON d.department_id = a.department_id
LEFT JOIN regions r ON r.region_id = a.region_id
WHERE p.hire_date <= :as_of AND (p.termination_date IS NULL OR p.termination_date > :as_of)
ORDER BY p.person_id;
