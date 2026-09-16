"""Acceptance tests use truth only in isolated temporary input directories."""
import csv
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline import ROOT, build, query, report, run

def read(path):
    with path.open(newline='',encoding='utf-8') as f: return list(csv.DictReader(f))

def write(path, rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.raw=self.root/'raw'; shutil.copytree(ROOT/'data/raw',self.raw)
        self.connections=[]

    def tearDown(self):
        for db in self.connections: db.close()
        self.temp.cleanup()

    def database(self):
        db=build(self.raw,self.root/f'{len(self.connections)}.sqlite'); self.connections.append(db); return db

    def clean_input(self):
        people=read(ROOT/'tests/fixtures/truth_people.csv')
        write(self.raw/'hr_people.csv',[dict(source_row_id=f'T{i:05}',**p,extracted_at='2026-09-01T06:00:00Z') for i,p in enumerate(people)])
        history=read(ROOT/'tests/fixtures/truth_assignments.csv')
        write(self.raw/'hr_assignments.csv',[dict(p,extracted_at='2026-09-01T06:00:00Z') for p in history])

    def test_all_planted_issues_found_and_raw_preserved(self):
        db=self.database()
        expected={(r['file'],r['record_id'],r['issue']) for r in read(ROOT/'tests/fixtures/injected_issues.csv')}
        actual={(r['source_file'],r['source_row'],r['code']) for r in db.execute('SELECT * FROM findings')}
        self.assertEqual(actual,expected)
        self.assertEqual(db.execute('SELECT count(*) FROM stage_hr_people').fetchone()[0],1210)
        self.assertEqual(db.execute('SELECT count(*) FROM people').fetchone()[0],1195)
        self.assertEqual(db.execute('SELECT count(*) FROM unresolved_people').fetchone()[0],5)
        for name in ('hr_people','hr_assignments','finance_staffing','departments','regions'):
            source=read(self.raw/f'{name}.csv')
            staged=[dict(r) for r in db.execute(f'SELECT * FROM stage_{name} ORDER BY line_number')]
            for row in staged: row.pop('line_number')
            self.assertEqual(staged,source)

    def test_dirty_reports_are_provisional_and_bridge_balances(self):
        r=report(self.database(),'2026-08-31','2026-01-01'); s=r['summary']
        self.assertEqual(s['status'],'PROVISIONAL')
        self.assertEqual(s['validated_employee_headcount'],963)
        self.assertEqual(s['finance_headcount']+sum(x['delta'] for x in r['reconciliation']),963)
        self.assertEqual(sum(x['reason']=='unresolved_hr_record' for x in r['reconciliation']),5)
        self.assertEqual(s['active_people_with_unknown_organization'],2)

    def test_clean_metrics_match_independent_fixtures(self):
        self.clean_input(); r=report(self.database(),'2026-08-31','2026-01-01')
        expected=json.loads((ROOT/'tests/fixtures/summary.json').read_text())
        self.assertEqual(r['summary']['validated_employee_headcount'],expected['canonical_employee_headcount'])
        self.assertEqual(r['summary']['validated_total_workforce'],expected['canonical_total_workforce'])
        self.assertEqual(r['monthly'],expected['monthly'])
        bridge=read(ROOT/'tests/fixtures/expected_reconciliation.csv')
        self.assertEqual([(x['person_id'],x['reason'],int(x['delta'])) for x in bridge],
                         [(x['person_id'],x['reason'],x['delta']) for x in r['reconciliation']])

    def test_transfer_and_employment_date_boundaries(self):
        self.clean_input(); db=self.database()
        def snap(day): return {r['person_id']:r for r in query(db,'snapshot.sql',{'as_of':day})}
        before=snap('2026-08-14'); after=snap('2026-08-15')
        for i in range(1,21):
            self.assertEqual(before[f'P{i:04}']['region_id'],'US')
            self.assertEqual(after[f'P{i:04}']['region_id'],'UK')
        self.assertNotIn('P0021',snap('2026-08-19'))
        self.assertIn('P0021',snap('2026-08-20'))
        self.assertIn('P0031',snap('2026-08-19'))
        self.assertNotIn('P0031',snap('2026-08-20'))

    def test_conflicting_duplicate_is_not_arbitrarily_resolved(self):
        rows=read(self.raw/'hr_people.csv'); rows.append(dict(rows[0],source_row_id='CONFLICT',worker_type='Contractor'))
        write(self.raw/'hr_people.csv',rows); db=self.database()
        self.assertIsNone(db.execute("SELECT * FROM people WHERE person_id='P0001'").fetchone())
        self.assertEqual(db.execute("SELECT reason FROM unresolved_people WHERE person_id='P0001'").fetchone()[0],'conflicting_person')

    def test_overlapping_assignments_do_not_double_count(self):
        self.clean_input(); rows=read(self.raw/'hr_assignments.csv')
        rows[1]['valid_from']='2026-08-14'; write(self.raw/'hr_assignments.csv',rows)
        db=self.database(); snap=query(db,'snapshot.sql',{'as_of':'2026-08-15'})
        matches=[r for r in snap if r['person_id']=='P0001']
        self.assertEqual(len(matches),1); self.assertEqual(matches[0]['region'],'Unknown')
        self.assertIsNotNone(db.execute("SELECT * FROM findings WHERE code='invalid_assignment_history'").fetchone())

    def test_malformed_date_is_quarantined(self):
        rows=read(self.raw/'hr_people.csv'); rows[0]['hire_date']='2026-02-30'
        write(self.raw/'hr_people.csv',rows); db=self.database()
        self.assertEqual(db.execute("SELECT reason FROM unresolved_people WHERE person_id='P0001'").fetchone()[0],'invalid_date')

    def test_bad_schema_blocks_run(self):
        (self.raw/'regions.csv').write_text('wrong_header\nUS\n')
        with self.assertRaises(ValueError): run(self.raw,self.root/'output')
        self.assertFalse(list((self.root/'output').rglob('COMPLETE')))
        self.assertEqual(len(list((self.root/'output').rglob('FAILED.txt'))),1)

    def test_partial_month_is_not_reported_as_complete(self):
        r=report(self.database(),'2026-08-28','2026-01-01')
        self.assertEqual(r['monthly'][-1]['month'],'2026-07')

    def test_run_is_repeatable_and_does_not_change_sources(self):
        original={p.name:p.read_bytes() for p in self.raw.glob('*.csv')}
        one,r1=run(self.raw,self.root/'output'); two,r2=run(self.raw,self.root/'output')
        self.assertNotEqual(one,two); self.assertEqual(r1,r2)
        self.assertEqual(original,{p.name:p.read_bytes() for p in self.raw.glob('*.csv')})
        self.assertTrue((one/'COMPLETE').exists()); self.assertTrue((two/'COMPLETE').exists())

if __name__=='__main__': unittest.main()
