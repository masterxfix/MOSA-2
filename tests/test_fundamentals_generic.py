import copy
import hashlib
import json
import subprocess
import unittest
from scripts.fundamentals import zeiss
from scripts import fundamentals_pilot_once as pilot
from test_fundamentals_pilot import plan as pne_plan, OBSERVED

# Invented amounts, including different thousands and decimal formats.
def fixture():
    rows = ['<tr><th></th><th>2024/25</th><th></th><th>2023/24</th><th>Veränderung</th></tr>']
    for label, key in zeiss.ROWS.items():
        dimension = zeiss.DEFINITIONS[key][2]
        values = ('1,23 €','0,98 €') if key=='eps_basic' else ('42,5 %','39,1 %') if dimension=='ratio' else ('1.234,5','987,6')
        rows.append(f'<tr><td>{label}</td><td>{values[0]}</td><td></td><td>{values[1]}</td><td>+1 %</td></tr>')
    return ('<html><title>Carl Zeiss Meditec</title><h1>Ertragslage</h1>'
        '<p>Zusammenfassung wesentlicher Größen der Konzern-Gewinn- und Verlustrechnung</p>'
        '<p>Angaben in Mio. €, falls nicht angegeben</p><table>'+''.join(rows)+'</table>'
        '<p>Im Geschäftsjahr 2024/25 beläuft sich der unverwässerte Gewinn je Aktie des Mutterunternehmens auf 1,23 € (Vorjahr: 0,98 €).</p>'
        '<p>Das Ergebnis vor Zinsen, Steuern und Abschreibungen (EBITDA) betrug für das abgelaufene Geschäftsjahr 456,7 Mio. € (Vorjahr: 345,6 Mio. €).</p></html>').encode()

def zeiss_plan():
    raw=fixture(); p=zeiss.parse(raw,OBSERVED)
    p['metadata']=dict(url=zeiss.URL,observed_at=OBSERVED,http_status=200,content_type='text/html',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    p['archive']=dict(storage_key='/private/synthetic/zeiss.body',sha256=p['metadata']['sha256'],bytes=len(raw),durable=True)
    return p

class GenericTests(unittest.TestCase):
    def test_qualified_table_actual_previous_and_separate_metrics(self):
        p=zeiss_plan(); self.assertEqual(len(p['observations']),22)
        self.assertEqual(len(p['metrics']),11)
        self.assertEqual({(r['period_start'],r['period_end']) for r in p['observations']},
                         {('2024-10-01','2025-09-30'),('2023-10-01','2024-09-30')})
        self.assertEqual([r['value_decimal'] for r in p['observations'] if r['metric_key']=='eps_basic'],['1.23','0.98'])
        for replacement in [('2024/25','2023/24'),('unverwässerte','verwässerte'),('EBITA</td>','EBITDA</td>'),('Angaben in Mio. €','Angaben in Euro')]:
            with self.assertRaises(ValueError):zeiss.parse(fixture().decode().replace(*replacement).encode(),OBSERVED)
        with self.assertRaises(ValueError):zeiss.parse(fixture()+fixture(),OBSERVED)

    def test_two_assets_repeats_fiscal_quarters_conflicts_and_catalog_reuse(self):
        result=subprocess.run(['php','tests/fundamentals_generic.php'],input=json.dumps([pne_plan(),zeiss_plan()]),
                              text=True,capture_output=True,cwd=pilot.ROOT)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(result.stderr,'')
        self.assertEqual(json.loads(result.stdout),dict(ok=True,assertions=26))

    def test_zeiss_one_shot_guard(self):
        env=dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',
            GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_NUMBER='1',GITHUB_SHA='a'*40,EXPECTED_COMMIT='a'*40,
            FUNDAMENTALS_PROFILE='zeiss',AUTHORIZATION='MOSA2-ZEISS-FUNDAMENTALS-ONCE-20261101:'+'a'*40)
        pilot.guard(env)
        for k,v in [('GITHUB_RUN_ATTEMPT','2'),('GITHUB_RUN_NUMBER','2'),('AUTHORIZATION',pilot.AUTHORIZATION+'a'*40)]:
            with self.assertRaises(ValueError):pilot.guard(env|{k:v})

if __name__=='__main__':unittest.main()
