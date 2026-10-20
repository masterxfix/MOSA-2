"""Execute the real async renderer with offline responses and no browser network."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('node'),'Node required')
class MarketViewTests(unittest.TestCase):
    def run_view(self,scenario):
        p=subprocess.run(['node',str(ROOT/'tests/fixtures/market_dom_runtime.js'),str(ROOT/'assets/js/market.js'),scenario],capture_output=True,text=True,encoding='utf-8',check=True)
        return json.loads(p.stdout)

    def test_immediate_loading_shell_then_exact_native_price_without_float(self):
        r=self.run_view('stored');self.assertEqual(r['initial']['state'],'loading');self.assertEqual(r['initial']['busy'],'true')
        self.assertEqual(r['rows'][0]['cells'][1]['text'],'123.456.789.012.345.678,123456789 GBX')
        self.assertEqual(r['rows'][0]['cells'][1]['data']['nativePrice'],'123456789012345678.1234567890')
        self.assertEqual(r['rows'][0]['cells'][0]['text'],'Synthetic <asset>')
        self.assertEqual(r['decimals'],['123,45','0,0000000001','999.999.999.999.999.999,9999999999','-1.234,00'])

    def test_statuses_and_local_failure(self):
        for scenario,state,label in [('stale','stored','Veraltet'),('missing','stored','Noch kein Kurs'),('empty','missing','Noch keine gespeicherten Marktdaten.'),('error','error','Nicht verfügbar'),('malformed','error','Nicht verfügbar')]:
            with self.subTest(scenario=scenario):
                r=self.run_view(scenario);self.assertEqual(r['state'],state);self.assertEqual(r['busy'],'false')
                self.assertIn(label,' '.join(c['text'] for row in r['rows'] for c in row['cells']))
                self.assertEqual(r['success'],'false' if state=='error' else 'true')

    def test_one_same_origin_get_no_retry_and_painted_data_timing(self):
        for scenario in ('stored','error'):
            r=self.run_view(scenario);self.assertEqual(r['requests'],[dict(url='api/market.php',method='GET',cache='no-store')]);self.assertEqual(r['timing'],'912 ms')

if __name__=='__main__':unittest.main()
