"""Independent qualification: required table/EPS versus optional narrative EBITDA."""
import copy
import re
import unittest
from scripts import fundamentals_archive_import_once as importer
from scripts.fundamentals import zeiss, archived_zeiss as archive
from test_fundamentals_generic import fixture, OBSERVED
from test_fundamentals_archive_import import wrapped

class PartialTests(unittest.TestCase):
    def without_ebitda(self):
        return re.sub(rb'<p>Das Ergebnis.*?</p>',b'',fixture())
    def validate(self,raw,count,reason=None):
        plan=zeiss.parse(wrapped(raw),OBSERVED)
        self.assertEqual(len(plan['metrics']),count)
        self.assertEqual(len(plan['observations']),count*2)
        keys={m['metric_key'] for m in plan['metrics']}
        self.assertEqual(keys,{r['metric_key'] for r in plan['observations']})
        self.assertTrue(set(zeiss.ROWS.values()).issubset(keys))
        self.assertEqual('ebitda' in keys,count==11)
        self.assertEqual(plan['unqualified_metrics'],[] if reason is None else [dict(metric_key='ebitda',reason=reason)])
        self.assertEqual({(r['period_start'],r['period_end']) for r in plan['observations']},
                         {('2024-10-01','2025-09-30'),('2023-10-01','2024-09-30')})
        plan['metadata']=dict(sha256=archive.SHA256,commit=archive.COMMIT,execution=archive.EXECUTION,url=zeiss.URL,
            bytes=len(raw),observed_at=OBSERVED,http_status=200,content_type='text/html')
        plan['archive']=dict(sha256=archive.SHA256,bytes=len(raw),durable=True,storage_key='/synthetic/response.body')
        importer.validate_plan(plan)
        return plan
    def test_ten_required_metrics_without_optional_ebitda_pass_full_core(self):
        plan=self.validate(self.without_ebitda(),10,'EBITDA_PATTERN_NOT_MATCHED')
        self.assertEqual(plan['parse_status'],'partial')
    def test_unique_optional_ebitda_is_retained_but_missing_invalid_or_ambiguous_is_not(self):
        self.validate(fixture(),11)
        narrative=re.search(rb'<p>Das Ergebnis.*?</p>',fixture())[0]
        self.validate(fixture()+narrative,10,'EBITDA_MULTIPLE_MATCHES')
        self.validate(self.without_ebitda()+narrative.replace(b'456,7',b'765,4')+narrative,10,'EBITDA_MULTIPLE_MATCHES')
        self.validate(fixture().replace(b'456,7 Mio.',b'456,7 Prozent'),10,'EBITDA_PATTERN_NOT_MATCHED')
        self.validate(fixture().replace(b'456,7',b'NaN'),10,'EBITDA_PATTERN_NOT_MATCHED')
    def test_table_and_eps_integrity_still_fail_closed_without_ebitda(self):
        raw=self.without_ebitda()
        variants=[raw.replace(b'1.234,5',b'NaN',1),raw.replace(b'2024/25',b'2022/23'),
                  raw.replace('unverwässerte'.encode(),'verwässerte'.encode()),
                  raw.replace('1,23 €'.encode(),'1,23 %'.encode(),1),raw+raw]
        for bad in variants:
            with self.assertRaises(ValueError):zeiss.parse(wrapped(bad),OBSERVED)

if __name__=='__main__':unittest.main()
