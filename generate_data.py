"""Deterministic, dependency-free synthetic HR fixtures. Python 3.10+."""
from pathlib import Path
from datetime import date, timedelta
import calendar
import csv
import json
import random
import hashlib

ROOT = Path(__file__).resolve().parent
SEED = 42
AS_OF = '2026-08-31'
EXTRACTED = '2026-09-01T06:00:00Z'

def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def active(person, day):
    return person['hire_date'] <= day and (not person['termination_date'] or day < person['termination_date'])

def generate():
    rng = random.Random(SEED)
    departments = [dict(department_id=f'D{i+1:02}', department_name=n)
                   for i,n in enumerate(['Content','Engineering','Sales','Finance','HR'])]
    regions = [dict(region_id=r, country=c, region_name=n) for r,c,n in
               [('US','United States','North America'),('UK','United Kingdom','Europe'),('IN','India','Asia')]]
    people, assignments = [], []
    for i in range(1,1201):
        hire = date(2023,1,1) + timedelta(days=rng.randrange(1000))
        end = hire + timedelta(days=rng.randrange(60,600)) if i % 9 == 0 else None
        # Controlled August cohort: 10 hires, 10 departures, 20 US-to-UK transfers.
        if i <= 40: hire, end = date(2024,1,1), None
        if 21 <= i <= 30: hire = date(2026,8,20)
        if 31 <= i <= 40: end = date(2026,8,20)
        if i == 41: hire, end = date(2026,8,28), None
        if i == 42: hire, end = date(2024,1,1), date(2026,8,28)
        region = rng.choice(['US','UK','IN'])
        if i <= 20: region = 'US'
        if 21 <= i <= 40: region = 'UK'
        person = dict(person_id=f'P{i:04}', display_name=f'Synthetic Person {i:04}',
                      worker_type='Contractor' if i % 10 == 0 and i > 40 else 'Employee',
                      hire_date=hire.isoformat(), termination_date=end.isoformat() if end else '')
        people.append(person)
        dep = rng.choice(departments)['department_id']
        def assignment(start, stop, department, area):
            assignments.append(dict(assignment_id=f'A{len(assignments)+1:05}',person_id=person['person_id'],
                                    department_id=department,region_id=area,
                                    valid_from=start,valid_to=stop))
        transfer = date(2026,8,15) if i <= 20 else (hire+timedelta(days=90) if i%7==0 else None)
        if transfer and transfer <= date.fromisoformat(AS_OF) and (end is None or transfer < end):
            assignment(hire.isoformat(),transfer.isoformat(),dep,region)
            assignment(transfer.isoformat(),person['termination_date'],
                       dep if i<=20 else departments[(int(dep[1:]))%5]['department_id'],
                       'UK' if i<=20 else region)
        else: assignment(hire.isoformat(),person['termination_date'],dep,region)

    def placement(pid, day):
        return next(a for a in assignments if a['person_id']==pid and a['valid_from']<=day
                    and (not a['valid_to'] or day<a['valid_to']))

    hr = [dict(source_row_id=f'HR{i+1:05}', **p, extracted_at=EXTRACTED) for i,p in enumerate(people)]
    history = [dict(a, extracted_at=EXTRACTED) for a in assignments]
    issues = []
    def mutate(rows, index, field, value, code, file):
        row=rows[index]; old=row[field]; row[field]=value
        issues.append(dict(file=file, record_id=row.get('source_row_id',row.get('assignment_id')),
                           issue=code, field=field, observed=value, expected=old))
    for i in range(50,55): mutate(hr,i,'termination_date','2022-01-01','termination_before_hire','hr_people.csv')
    for i in range(60,65): mutate(history,i,'department_id','','missing_department','hr_assignments.csv')
    mutate(history,70,'region_id','ZZ','unknown_region','hr_assignments.csv')
    for i in range(10):
        row=dict(hr[100+i],source_row_id=f'HR{1201+i:05}')
        hr.append(row)
        issues.append(dict(file='hr_people.csv',record_id=row['source_row_id'],issue='duplicate_person',
                           field='person_id',observed=row['person_id'],expected='one row per person'))

    # Finance uses an earlier cutoff, excludes contractors, and has five omitted people.
    cutoff='2026-08-25'
    eligible=[p for p in people if p['worker_type']=='Employee' and active(p,cutoff)]
    omitted={p['person_id'] for p in eligible[-5:]}
    finance=[]
    for p in eligible:
        if p['person_id'] in omitted: continue
        a=placement(p['person_id'],cutoff)
        finance.append(dict(finance_row_id=f'F{len(finance)+1:05}',person_id=p['person_id'],
                            department_id=a['department_id'],region_id=a['region_id'],
                            reporting_date=cutoff,extracted_at='2026-08-26T06:00:00Z'))
    write_csv(ROOT/'data/raw/hr_people.csv',hr)
    write_csv(ROOT/'data/raw/hr_assignments.csv',history)
    write_csv(ROOT/'data/raw/finance_staffing.csv',finance)
    write_csv(ROOT/'data/raw/departments.csv',departments)
    write_csv(ROOT/'data/raw/regions.csv',regions)
    write_csv(ROOT/'tests/fixtures/truth_people.csv',people)
    write_csv(ROOT/'tests/fixtures/truth_assignments.csv',assignments)
    write_csv(ROOT/'tests/fixtures/injected_issues.csv',issues)
    monthly=[]
    for month in range(1,9):
        first=date(2026,month,1); last=date(2026,month,calendar.monthrange(2026,month)[1])
        opening=(first-timedelta(days=1)).isoformat(); closing=last.isoformat()
        employees=[p for p in people if p['worker_type']=='Employee']
        start=sum(active(p,opening) for p in employees); finish=sum(active(p,closing) for p in employees)
        hires=sum(first.isoformat()<=p['hire_date']<=closing for p in employees)
        departures=sum(first.isoformat()<=p['termination_date']<=closing for p in employees if p['termination_date'])
        assert start+hires-departures==finish
        monthly.append(dict(month=first.isoformat()[:7],opening_headcount=start,hires=hires,
                            departures=departures,closing_headcount=finish,
                            turnover_pct=round(departures/((start+finish)/2)*100,6)))
    write_csv(ROOT/'tests/fixtures/expected_monthly_metrics.csv',monthly)
    canonical={p['person_id'] for p in people if p['worker_type']=='Employee' and active(p,AS_OF)}
    finance_ids={p['person_id'] for p in finance}
    lookup={p['person_id']:p for p in people}
    bridge=[]
    for pid in sorted(canonical ^ finance_ids):
        reason='missing_finance_record' if pid in omitted else 'cutoff_difference'
        bridge.append(dict(person_id=pid,reason=reason,finance_count=int(pid in finance_ids),
                           canonical_count=int(pid in canonical),delta=int(pid in canonical)-int(pid in finance_ids)))
    assert len(finance)+sum(r['delta'] for r in bridge)==len(canonical)
    write_csv(ROOT/'tests/fixtures/expected_reconciliation.csv',bridge)
    summary=dict(seed=SEED,reporting_date=AS_OF,people=len(people),hr_source_rows=len(hr),
                 assignment_rows=len(history),deliberate_quality_issues=len(issues),
                 canonical_employee_headcount=len(canonical),finance_headcount=len(finance),
                 canonical_total_workforce=sum(active(p,AS_OF) for p in people),
                 reconciliation_delta=len(canonical)-len(finance),
                 finance_omitted_ids=sorted(omitted),monthly=monthly)
    (ROOT/'tests/fixtures/summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    for p in people:
        chain=[a for a in assignments if a['person_id']==p['person_id']]
        assert chain[0]['valid_from']==p['hire_date']
        assert chain[-1]['valid_to']==p['termination_date']
        assert all(a['valid_to']==b['valid_from'] for a,b in zip(chain,chain[1:]))
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((ROOT/'data/raw').glob('*.csv'))}
    (ROOT/'data/manifest.json').write_text(json.dumps(dict(seed=SEED,sha256=manifest),indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='monthly'},indent=2))

if __name__=='__main__': generate()
