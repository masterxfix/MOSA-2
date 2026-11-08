import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from scripts.fundamentals import nel_q2
from scripts.fundamentals import reports


RAW = b'%PDF-synthetic-nel-q2'
OBSERVED = '2026-11-08 00:00:00.123456'


def word(text, x, bottom=100):
    return dict(text=text, x0=x, x1=x + max(8, len(text) * 5), bottom=bottom)


def line(texts, bottom):
    words = [word(text, x, bottom) for text, x in texts]
    return dict(words=words, text=' '.join(text for text, _ in texts), bottom=bottom)


def page(title, rows, page_number):
    lines = [line([('NEL ASA', 10)], 100), line([(title, 10)], 120),
             line([('Q2', 300), ('2026', 330), ('Q2', 400), ('2025', 430)], 140)]
    lines.extend(line([(label, 10), (value, 300)], 160 + index * 20) for index, (label, value) in enumerate(rows))
    return dict(number=page_number, width=600, height=800, lines=lines,
                text='\n'.join(item['text'] for item in lines))


PAGES = [
    page('Consolidated statement of comprehensive income (unaudited)', [
        ('Amounts in NOK thousands', '0'),
        ('Revenue from contracts with customers', '153407'),
        ('Operating loss', '-205220'),
        ('Net income (loss) for the period', '-188571'),
    ], 12),
    page('Consolidated statement of cash flows (unaudited)', [
        ('Amounts in NOK thousands', '0'),
        ('Net cash flow from operating activities', '1673'),
    ], 13),
    page("The following table includes information about Nel's operating segments.", [
        ('Revenue', ''),
        ('Total', '153407'),
        ('EBITDA', ''),
        ('Nel Alkaline Electrolyser', '-27989'),
        ('Nel PEM Electrolyser', '-34810'),
        ('Corporate 1)', '-92538'),
        ('Total', '-155337'),
        ('Investments 2)', ''),
        ('Total', '75097'),
        ('Total assets 3)', ''),
        ('Total', '4639479'),
    ], 17),
]

# NEL's real income statement has a separate Note column before Q2 2026.
PAGES[0]['lines'][4]['words'].insert(1, word('3', 255, 180))
PAGES[0]['lines'][4]['text'] = ' '.join(w['text'] for w in PAGES[0]['lines'][4]['words'])
PAGES[0]['text'] = '\n'.join(item['text'] for item in PAGES[0]['lines'])

# The real report's non-financial note is retained as evidence only.
PAGES[0]['text'] += '\nOther adjustments include the NOK 70m Iwatani settlement.'
PAGES[0]['text'] += '\nNel ASA second quarter 2026 financial results.'


class NelQ2Tests(unittest.TestCase):
    def metadata(self):
        return dict(url=nel_q2.URL, observed_at=OBSERVED, http_status=200,
                    content_type='application/pdf', bytes=len(RAW),
                    sha256=hashlib.sha256(RAW).hexdigest())

    def test_exact_q2_values_and_existing_catalog_definitions(self):
        with patch.object(nel_q2, 'read_pdf', return_value=PAGES):
            plan = nel_q2.parse(RAW, self.metadata(), dict(isin=nel_q2.ISIN, name='NEL ASA'))
        self.assertEqual([row['metric_key'] for row in plan['observations']], list(nel_q2.METRIC_ORDER))
        self.assertEqual([row['value_decimal'] for row in plan['observations']],
                         ['153407', '-155337', '-205220', '-188571', '1673'])
        values = {row['metric_key']: row['value_decimal'] for row in plan['observations']}
        self.assertEqual(values['ifrs_operating_profit'], '-205220')
        self.assertEqual(values['ebitda'], '-155337')
        self.assertEqual({row['period_type'] for row in plan['observations']}, {'fq'})
        self.assertEqual({row['period_start'] for row in plan['observations']}, {'2026-04-01'})
        self.assertEqual({row['period_end'] for row in plan['observations']}, {'2026-06-30'})
        self.assertEqual({row['unit_key'] for row in plan['observations']}, {'NOK_THOUSAND'})
        compact, stored = nel_q2.evidence(plan, self.metadata(), dict(isin=nel_q2.ISIN, name='NEL ASA'))
        document = json.loads(compact)
        self.assertEqual(len(document['facts']), 5)
        self.assertEqual(document['facts'][0]['position'].split(';')[0], 'pdf:page=12')
        self.assertEqual(document['special_effects'][0]['treatment'], 'evidence_only_no_ebitda_adjustment')
        self.assertEqual(stored['sha256'], hashlib.sha256(compact).hexdigest())

        plan['metadata'] = self.metadata()
        plan['archive'] = dict(storage_key='/private/mosa2/nel-q2/evidence.json',
                               sha256=stored['sha256'], bytes=stored['bytes'], durable=True)
        plan['stored_evidence'] = stored
        php = os.environ.get('PHP_BIN') or shutil.which('php')
        self.assertTrue(php, 'php CLI is required for the NEL writer contract test')
        result = subprocess.run([php, str(Path(__file__).with_name('fundamentals_nel_q2.php'))],
                                input=json.dumps(plan), text=True, capture_output=True,
                                cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['observations'], 5)

    def test_original_bold_glyph_splits_are_normalized(self):
        self.assertEqual(nel_q2._normal('O perating loss'), 'Operating loss')
        self.assertEqual(nel_q2._normal('N et income (loss) for the period'), 'Net income (loss) for the period')
        self.assertEqual(nel_q2._normal('T otal operating expenses'), 'Total operating expenses')
        modified = copy.deepcopy(PAGES)
        modified[0]['lines'][5] = line([('O perating loss', 10), ('-205220', 300)], 200)
        modified[0]['lines'][6] = line([('N et income (loss) for the period', 10), ('-188571', 300)], 220)
        with patch.object(nel_q2, 'read_pdf', return_value=modified):
            plan = nel_q2.parse(RAW, self.metadata(), dict(isin=nel_q2.ISIN, name='NEL ASA'))
        result = {row['metric_key']: row['value_decimal'] for row in plan['observations']}
        self.assertEqual(result['ifrs_operating_profit'], '-205220')
        self.assertEqual(result['profit_after_tax'], '-188571')

    def test_segment_total_is_section_scoped_and_duplicate_stops(self):
        changed = copy.deepcopy(PAGES)
        # A repeated Total inside EBITDA must not be silently accepted.
        changed[2]['lines'].insert(10, line([('Total', 10), ('-155337', 300)], 295))
        with patch.object(nel_q2, 'read_pdf', return_value=changed):
            with self.assertRaisesRegex(ValueError, 'NEL_EBITDA_AMBIGUOUS'):
                nel_q2.parse(RAW, self.metadata(), dict(isin=nel_q2.ISIN, name='NEL ASA'))

    def test_wrong_quarter_value_rejected(self):
        changed = copy.deepcopy(PAGES)
        changed[2]['lines'][9] = line([('Total', 10), ('-86365', 300)], 290)
        with patch.object(nel_q2, 'read_pdf', return_value=changed):
            with self.assertRaisesRegex(ValueError, 'NEL_Q2_VALUE_MISMATCH'):
                nel_q2.parse(RAW, self.metadata(), dict(isin=nel_q2.ISIN, name='NEL ASA'))

    def test_report_registry_authorizes_only_the_single_nel_report(self):
        selected = reports.selection(['nel-q2-2026'])
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['identity'], {'isin': nel_q2.ISIN, 'name': 'NEL ASA'})
        self.assertEqual(selected[0]['preserve_assets'][0]['observations'], 6)
        self.assertEqual(selected[0]['preserve_assets'][0]['current'], 3)
        self.assertEqual(selected[0]['periods'], [('fq', '2026-04-01', '2026-06-30')])

    def test_pdf_reader_is_installed_and_checked_before_authorized_get(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/fundamentals-reports.yml').read_text(encoding='utf-8')
        self.assertIn('pdfplumber==0.11.9', workflow)
        self.assertIn("import pdfplumber; assert pdfplumber.__version__", workflow)
        self.assertLess(workflow.index("import pdfplumber; assert pdfplumber.__version__"),
                        workflow.index('Authorized report GET, compact evidence'))

    def test_registered_nel_execution_matches_both_reservation_lists(self):
        execution = reports.REPORTS['nel-q2-2026']['execution']
        source = (Path(__file__).resolve().parents[1] / 'scripts/fundamentals/archive_remote.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in {'EXECUTIONS', 'EVIDENCE_EXECUTIONS'}:
                    values[node.targets[0].id] = ast.literal_eval(node.value)
        self.assertIn(execution, values['EXECUTIONS'])
        self.assertIn(execution, values['EVIDENCE_EXECUTIONS'])
        self.assertLess(source.index("need(data['execution'] in EXECUTIONS"),
                        source.index("create_file(locks, ONCE+'.consumed'"))

    def test_wrong_report_period_or_identity_stops(self):
        with patch.object(nel_q2, 'read_pdf', return_value=PAGES):
            with self.assertRaises(ValueError):
                nel_q2.parse(RAW, self.metadata(), dict(isin=nel_q2.ISIN, name='Other'))


if __name__ == '__main__':
    unittest.main()
