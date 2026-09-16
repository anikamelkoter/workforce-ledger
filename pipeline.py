"""Load, validate and report synthetic exports. Never reads tests/fixtures.

Run: python3 pipeline.py --input data/raw --output output
Each run creates a new timestamped folder, preserving previous runs and raw files.
"""
from pathlib import Path
from datetime import date, datetime, timezone
from collections import defaultdict
import argparse
import csv
import hashlib
import json
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parent
CONTRACTS = {
 'hr_people': 'source_row_id person_id display_name worker_type hire_date termination_date extracted_at',
 'hr_assignments': 'assignment_id person_id department_id region_id valid_from valid_to extracted_at',
 'finance_staffing': 'finance_row_id person_id department_id region_id reporting_date extracted_at',
 'departments': 'department_id department_name',
 'regions': 'region_id country region_name',
}

def iso(value, blank=False):
    if not value and blank: return True
    try: return date.fromisoformat(value).isoformat() == value
    except (ValueError, TypeError): return False

def rows_csv(path):
    with path.open(newline='', encoding='utf-8') as f:
        reader=csv.DictReader(f)
        return reader.fieldnames, list(reader)

def query(db, name, params):
    return [dict(r) for r in db.execute((ROOT/'sql'/name).read_text(),params)]

def build(input_dir, db_path):
    """Creates a fresh DB; schema errors fail the run, row issues are recorded."""
    db=sqlite3.connect(db_path)
    db.row_factory=sqlite3.Row
    try:
        db.executescript((ROOT/'sql/schema.sql').read_text())
        raw={}
        for name, contract in CONTRACTS.items():
            fields, rows=rows_csv(input_dir/f'{name}.csv')
            if fields!=contract.split(): raise ValueError(f'{name}: header does not match documented contract')
            if any(None in r or any(v is None for v in r.values()) for r in rows):
                raise ValueError(f'{name}: malformed CSV row')
            raw[name]=rows
            # Names derive only from fixed contracts; data is always parameterized.
            db.execute(f'CREATE TABLE stage_{name} (line_number INTEGER PRIMARY KEY, '+
                       ','.join(f'{field} TEXT' for field in fields)+')')
            db.executemany(f'INSERT INTO stage_{name} VALUES ({",".join("?" for _ in range(len(fields)+1))})',
                           [(i+2,*r.values()) for i,r in enumerate(rows)])
            db.execute('INSERT INTO run_metadata VALUES (?,?)',(f'{name}_sha256',hashlib.sha256((input_dir/f'{name}.csv').read_bytes()).hexdigest()))
        def finding(file, row, code, detail, severity='error'):
            ref=row.get('source_row_id',row.get('assignment_id',row.get('finance_row_id','')))
            db.execute('INSERT INTO findings(source_file,source_row,person_id,code,severity,detail) VALUES (?,?,?,?,?,?)',
                       (file+'.csv',ref,row.get('person_id',''),code,severity,detail))
        def reject(pid, reason):
            db.execute('INSERT OR IGNORE INTO unresolved_people VALUES (?,?)',(pid,reason))
        for name in ('departments','regions'):
            key=CONTRACTS[name].split()[0]
            if any(not all(r.values()) for r in raw[name]) or len({r[key] for r in raw[name]})!=len(raw[name]):
                raise ValueError(f'{name}: blank or duplicate directory key/value')
            db.executemany(f'INSERT INTO {name} VALUES ({",".join("?" for _ in CONTRACTS[name].split())})',[tuple(r.values()) for r in raw[name]])
        groups=defaultdict(list)
        for r in raw['hr_people']: groups[r['person_id']].append(r)
        accepted={}
        for pid, records in groups.items():
            r=records[0]
            versions={tuple(x[k] for k in ('display_name','worker_type','hire_date','termination_date')) for x in records}
            if len(versions)>1:
                for x in records: finding('hr_people',x,'conflicting_person','Conflicting versions; no automatic winner.')
                reject(pid,'conflicting_person'); continue
            for x in records[1:]: finding('hr_people',x,'duplicate_person','Identical business fields; first occurrence retained.','warning')
            code=None
            if not pid or not r['display_name']: code='missing_person_identity'
            elif r['worker_type'] not in ('Employee','Contractor'): code='invalid_worker_type'
            elif not iso(r['hire_date']) or not iso(r['termination_date'],True): code='invalid_date'
            elif r['termination_date'] and r['termination_date']<=r['hire_date']: code='termination_before_hire'
            if code:
                finding('hr_people',r,code,'Employment status is unresolved; person excluded from validated metrics.')
                reject(pid,code); continue
            accepted[pid]=r
            db.execute('INSERT INTO people VALUES (?,?,?,?,?,?)',(pid,r['display_name'],r['worker_type'],r['hire_date'],r['termination_date'] or None,r['source_row_id']))
        deps={r['department_id'] for r in raw['departments']}; regions={r['region_id'] for r in raw['regions']}
        chains=defaultdict(list)
        assignment_ids=[r['assignment_id'] for r in raw['hr_assignments']]
        if len(set(assignment_ids))!=len(assignment_ids): raise ValueError('Duplicate assignment_id; fix source keys before reporting')
        for r in raw['hr_assignments']: chains[r['person_id']].append(r)
        for pid, records in chains.items():
            if pid not in accepted:
                if pid not in groups: finding('hr_assignments',records[0],'unknown_person','Assignment has no HR person.')
                continue
            p=accepted[pid]; chain=sorted(records,key=lambda r:r['valid_from'])
            valid=all(iso(r['valid_from']) and iso(r['valid_to'],True) and
                      (not r['valid_to'] or r['valid_to']>r['valid_from']) for r in chain)
            valid=valid and chain[0]['valid_from']==p['hire_date'] and chain[-1]['valid_to']==p['termination_date']
            valid=valid and all(a['valid_to']==b['valid_from'] for a,b in zip(chain,chain[1:]))
            if not valid:
                finding('hr_assignments',chain[0],'invalid_assignment_history','Gap, overlap, invalid date or employment-boundary mismatch. Entire organizational history excluded.'); continue
            for r in chain:
                dep=r['department_id']; region=r['region_id']
                if dep not in deps:
                    finding('hr_assignments',r,'missing_department' if not dep else 'unknown_department','Organizational field mapped to Unknown; person remains countable.')
                    dep=None
                if region not in regions:
                    finding('hr_assignments',r,'unknown_region','Organizational field mapped to Unknown; person remains countable.'); region=None
                db.execute('INSERT INTO assignments VALUES (?,?,?,?,?,?)',(r['assignment_id'],pid,dep,region,r['valid_from'],r['valid_to'] or None))
        for pid in accepted.keys()-chains.keys():
            finding('hr_people',accepted[pid],'missing_assignment_history','Person remains countable globally; organization is Unknown.')
        # Finance is a separately sourced comparison, so its unknown HR IDs remain visible.
        finance=raw['finance_staffing']
        dates={r['reporting_date'] for r in finance}
        if len(dates)!=1 or not all(iso(d) for d in dates): raise ValueError('Finance must contain exactly one valid reporting date')
        if len({r['person_id'] for r in finance})!=len(finance) or any(not r['person_id'] for r in finance):
            raise ValueError('Finance has blank/duplicate person keys; comparison blocked')
        for r in finance:
            db.execute('INSERT INTO finance VALUES (?,?,?,?,?)',(r['person_id'],r['department_id'],r['region_id'],r['reporting_date'],r['finance_row_id']))
        db.commit()
        return db
    except Exception:
        db.close()
        raise

def export_csv(path, rows, columns):
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=columns); writer.writeheader(); writer.writerows(rows)

def report(db, as_of, start_month):
    finance_date=db.execute('SELECT reporting_date FROM finance LIMIT 1').fetchone()[0]
    if finance_date>as_of: raise ValueError('Finance cutoff must not follow the requested reporting date')
    params=dict(as_of=as_of,finance_date=finance_date,start_month=start_month,end_month=as_of[:7]+'-01')
    snapshot=query(db,'snapshot.sql',params)
    monthly=query(db,'monthly.sql',params)
    bridge=query(db,'reconciliation.sql',params)
    findings=[dict(r) for r in db.execute('SELECT * FROM findings ORDER BY finding_id')]
    unknown=db.execute('SELECT count(*) FROM unresolved_people').fetchone()[0]
    hc=sum(r['worker_type']=='Employee' for r in snapshot)
    finance_count=db.execute('SELECT count(*) FROM finance').fetchone()[0]
    assert finance_count+sum(r['delta'] for r in bridge)==hc
    assert len({r['person_id'] for r in snapshot})==len(snapshot)
    summary=dict(reporting_date=as_of,finance_reporting_date=finance_date,
                 status='PROVISIONAL' if unknown or any(r['severity']=='error' for r in findings) else 'VALIDATED',
                 validated_employee_headcount=hc,validated_total_workforce=len(snapshot),
                 finance_headcount=finance_count,bridge_delta=hc-finance_count,
                 unresolved_people=unknown,quality_findings=len(findings),
                 active_people_with_unknown_organization=sum(r['department']=='Unknown' or r['region']=='Unknown' for r in snapshot),
                 note='Validated counts exclude unresolved employment records. Bridge arithmetic does not establish full resolution.',
                 monthly_note='Monthly metrics cover complete months through the month containing reporting_date; partial last month is omitted.')
    # Do not show future events if as_of is mid-month.
    import calendar
    if int(as_of[-2:])!=calendar.monthrange(int(as_of[:4]),int(as_of[5:7]))[1]: monthly=monthly[:-1]
    return dict(summary=summary,snapshot=snapshot,monthly=monthly,reconciliation=bridge,findings=findings)

def run(input_dir, output, as_of='2026-08-31', start_month='2026-01-01'):
    if not iso(as_of) or not iso(start_month) or not start_month.endswith('-01') or start_month>as_of:
        raise ValueError('Provide ISO dates, a first-of-month start, and start <= as-of')
    output.mkdir(parents=True,exist_ok=True)
    run_dir=Path(tempfile.mkdtemp(prefix='run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-',dir=output))
    try:
        db=build(input_dir,run_dir/'workforce.sqlite')
        try:
            results=report(db,as_of,start_month)
            db.execute('INSERT INTO run_metadata VALUES (?,?)',('reporting_date',as_of)); db.commit()
        finally: db.close()
        for name,rows in results.items():
            if name=='summary': continue
            columns=list(rows[0]) if rows else {'findings':['finding_id','source_file','source_row','person_id','code','severity','detail'],
                       'reconciliation':['person_id','finance_count','validated_count','delta','reason'],
                       'snapshot':['person_id','display_name','worker_type','department','region','department_id','region_id'],
                       'monthly':['month','opening_headcount','hires','departures','closing_headcount','turnover_pct']}[name]
            export_csv(run_dir/f'{name}.csv',rows,columns)
        (run_dir/'summary.json').write_text(json.dumps(results['summary'],indent=2)+'\n')
        (run_dir/'COMPLETE').write_text('Run completed. See summary.json for data-quality status.\n')
        return run_dir,results
    except Exception as exc:
        (run_dir/'FAILED.txt').write_text(str(exc)+'\n')
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'data/raw')
    parser.add_argument('--output',type=Path,default=ROOT/'output')
    parser.add_argument('--as-of',default='2026-08-31')
    parser.add_argument('--start-month',default='2026-01-01')
    args=parser.parse_args()
    folder,results=run(args.input,args.output,args.as_of,args.start_month)
    print(json.dumps(results['summary'],indent=2)); print(f'Reports: {folder}')
