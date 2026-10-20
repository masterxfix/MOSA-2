"""Synthetic offline v2 plans and immutable v1 vectors; never live market data."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('phase3n_writer_tests', ROOT/'scripts/phase3n/writer_plan.py')
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)
obs = writer.observation
adapter = obs.catalog_module
CREATED = '2026-01-01 00:00:05.000000'


def row(unit='EUR', **changes):
    value = dict(asset_id='101', source_id='201', route_id='301', currency={'EUR':'EUR','GBP':'GBP','GBX':'GBP','POINT':None}[unit],
                 market_at='2026-01-01 00:00:00', observed_at='2026-01-01 00:00:01',
                 price='123.45', bid='123', ask='124', volume=None,
                 unit_contract_version='mosa2-market-unit-v1', quote_unit_key=unit, quote_unit_version='1',
                 quantity_basis_unit_key=None, quantity_basis_unit_version=None, quantity_basis_amount=None,
                 volume_unit_key=None, volume_unit_version=None)
    value.update(changes)
    return value


def route(value, version=2, **changes):
    record = dict(id=value['route_id'],asset_id=value['asset_id'],source_id=value['source_id'],route_revision='1')
    record.update({k: value.get(k) for k in obs.UNIT_FIELDS})
    record.update(changes)
    return dict(format_version=version, route=record)


def qualified_synthetic_manifest():
    manifest = copy.deepcopy(adapter.units.load_manifest())
    manifest['package_key'] = 'synthetic-writer-tests'
    base = dict(manifest['definitions'][0])
    for key, dimension, currency, version in [('SYNTH_QUANTITY','energy',None,'1'),
                                             ('SYNTH_VOLUME','quantity',None,'1'),
                                             ('SYNTH_QUOTE','monetary','EUR','1'),
                                             ('SYNTH_QUOTE','monetary','EUR','2')]:
        definition = dict(base, unit_key=key, unit_version=version, dimension_key=dimension,
                          base_unit_key=key, base_unit_version=version, monetary_currency_code=currency,
                          scale_numerator='1', scale_denominator='1', definition_reference='synthetic offline fixture')
        definition['definition_sha256'] = adapter.units.definition_sha256(definition)
        manifest['definitions'].append(definition)
    manifest['package_sha256'] = adapter.units.package_sha256(manifest)
    return manifest


class ObservationV2WriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = adapter.normative_catalog()
        cls.synthetic_manifest = qualified_synthetic_manifest()
        # Explicit test-only qualification. This anchor is not taken from a
        # caller-supplied package; mutations below remain bound to the original.
        cls.synthetic_anchor = cls.synthetic_manifest['package_sha256']
        cls.synthetic = adapter.UnitCatalog(cls.synthetic_manifest, cls.synthetic_anchor)

    def plan(self, value=None, route_contract=None, catalog=None, existing=(), **kwargs):
        value = row() if value is None else value
        try:
            planner = writer.WriterPlanner(catalog or self.catalog,
                                           [route_contract or route(value)], existing)
            return planner.plan(value, format_version=kwargs.pop('format_version',2),
                                intent=kwargs.pop('intent','NEW_NATIVE_V2'), created_at=CREATED, **kwargs)
        except ValueError as error:
            return dict(decision='REJECT', reason=str(error))

    def test_all_four_normative_units_native_and_currency(self):
        for unit in ('EUR','GBP','GBX','POINT'):
            with self.subTest(unit=unit):
                result=self.plan(row(unit));self.assertEqual(result['decision'],'INSERT',result)
                self.assertEqual(result['normalized']['price'],'123.4500000000')
                self.assertEqual(len(result['dedupe_key']),32)
                self.assertEqual(result['catalog_fingerprint'],adapter.APPROVED)

    def test_canonical_order_exact_domain_compact_utf8_no_trailing_lf(self):
        result=self.plan();canonical=result['canonical_bytes']
        self.assertTrue(canonical.startswith(b'mosa2-observation-v2\n{'))
        self.assertEqual(list(json.loads(canonical.split(b'\n',1)[1])),list(obs.FIELDS))
        self.assertEqual(len(obs.FIELDS),18);self.assertFalse(canonical.endswith(b'\n'))
        expected = b'mosa2-observation-v2\n'+json.dumps(result['normalized'],ensure_ascii=False,separators=(',',':')).encode()
        self.assertEqual(canonical,expected);self.assertEqual(hashlib.sha256(expected).digest(),result['dedupe_key'])
        self.assertEqual(obs.dedupe_key(row(),self.catalog),result['dedupe_key'])
        self.assertEqual(result['dedupe_key'].hex(),'8f4cd570642285d1d52e24d22102c5890bcd91966b3ea514712a725e9981f2eb')

    def test_order_and_v1_numeric_normalizations_are_deterministic(self):
        value=row(asset_id='000101',source_id=201,route_id='000301',price='+00123.45000',bid='0123.0',ask=124)
        a=obs.canonical_observation(value,self.catalog)
        b=obs.canonical_observation(dict(reversed(list(row().items()))),self.catalog)
        self.assertEqual(a,b)

    def test_plan_has_complete_existing_schema_columns_and_no_generated_identity(self):
        result=self.plan();values=result['db_values']
        self.assertEqual(tuple(values),result['expected_db_columns'])
        self.assertEqual(len(values),21);self.assertNotIn('id',values)
        self.assertEqual(values['observation_format_version'],2)
        self.assertEqual(values['created_at'],CREATED)
        self.assertEqual(values['dedupe_key'],result['dedupe_key'])
        self.assertEqual(result['route_binding']['route_revision'],'1')

    def test_quantity_basis_explicit_one_and_fixed_eight_scale(self):
        for amount in ('1','1.00000000','0.00000001','999999999999999999999999.99999999'):
            value=row(quantity_basis_unit_key='SYNTH_QUANTITY',quantity_basis_unit_version='1',quantity_basis_amount=amount)
            result=self.plan(value,catalog=self.synthetic)
            self.assertEqual(result['decision'],'INSERT',result)
            self.assertTrue(result['normalized']['quantity_basis_amount'].endswith('00000000') if amount.startswith('1') else True)
        self.assertEqual(self.plan(value,catalog=self.synthetic)['normalized']['price'],'123.4500000000')

    def test_volume_nonnull_requires_own_unit(self):
        value=row(volume='2.5',volume_unit_key='SYNTH_VOLUME',volume_unit_version='1')
        result=self.plan(value,catalog=self.synthetic)
        self.assertEqual(result['decision'],'INSERT',result)
        self.assertEqual(result['normalized']['volume'],'2.50000000')
        self.assertEqual(self.plan(row())['normalized']['volume_unit_key'],None)

    def test_duplicate_unchanged_and_equal_key_different_payload_conflict(self):
        result=self.plan();stored=dict(format_version=2,payload=result['normalized'],dedupe_key=result['dedupe_key'])
        duplicate=self.plan(existing=[stored]);self.assertEqual(duplicate['decision'],'DUPLICATE_UNCHANGED')
        for field in obs.FIELDS:
            changed=copy.deepcopy(stored);changed['payload'][field]='different'
            with self.subTest(field=field):
                self.assertEqual(self.plan(existing=[changed])['decision'],'CONFLICT')
        changed=copy.deepcopy(stored);changed['payload']['unexpected']='value'
        self.assertEqual(self.plan(existing=[changed])['decision'],'CONFLICT')

    def test_every_semantic_field_binds_hash_and_metadata_is_excluded(self):
        normalized=self.plan()['normalized'];key=hashlib.sha256(obs._canonical(normalized)).digest()
        # Serializer coverage, including unsupported future contract changes:
        # public validation rejects such contracts before hashing.
        for field in obs.FIELDS:
            altered=dict(normalized);altered[field]='synthetic-different'
            self.assertNotEqual(hashlib.sha256(obs._canonical(altered)).digest(),key,field)
        altered=dict(normalized,created_at='ignored',definition_reference='ignored',scale_numerator='ignored')
        self.assertEqual(obs._canonical(altered),obs._canonical(normalized))
        self.assertEqual(self.plan(altered)['decision'],'REJECT')

    def test_changed_quote_version_uses_distinct_key_without_unit_special_cases(self):
        a=row(quote_unit_key='SYNTH_QUOTE');b=dict(a,quote_unit_version='2')
        self.assertNotEqual(self.plan(a,catalog=self.synthetic)['dedupe_key'],self.plan(b,catalog=self.synthetic)['dedupe_key'])

    def test_unknown_unit_version_contract_and_bad_ascii_rejected(self):
        for changes in [dict(quote_unit_key='UNKNOWN'),dict(quote_unit_version='2'),dict(unit_contract_version='wrong'),
                        dict(unit_contract_version=''),dict(quote_unit_key=''),dict(quote_unit_key='é'),
                        dict(quote_unit_version='01'),dict(quote_unit_version=0),dict(quote_unit_version=True),
                        dict(quote_unit_version='4294967296')]:
            self.assertEqual(self.plan(row(**changes))['decision'],'REJECT',changes)

    def test_currency_is_derived_from_frozen_quote_definition(self):
        for value in [row('GBX',currency='GBX'),row('POINT',currency='EUR'),row('POINT',currency='XXX'),
                      row('EUR',currency='GBP'),row('GBP',currency=None)]:
            self.assertEqual(self.plan(value)['decision'],'REJECT',value)

    def test_quantity_triple_incomplete_nonpositive_noncanonical_or_overflow_rejected(self):
        base=row(quantity_basis_unit_key='SYNTH_QUANTITY',quantity_basis_unit_version='1',quantity_basis_amount='1')
        for field in obs.UNIT_FIELDS[3:6]:
            altered=dict(base);altered[field]=None
            self.assertEqual(self.plan(altered,catalog=self.synthetic)['decision'],'REJECT')
        for amount in ('0','-1','+1','01','1e2','1.000000001','1'*25,1,1.0,True):
            self.assertEqual(self.plan(dict(base,quantity_basis_amount=amount),catalog=self.synthetic)['decision'],'REJECT',amount)

    def test_volume_half_pairs_and_nullness_rejected(self):
        for value in [row(volume='1'),row(volume_unit_key='EUR',volume_unit_version='1'),
                      row(volume='1',volume_unit_key='EUR'),row(volume='1',volume_unit_version='1')]:
            self.assertEqual(self.plan(value)['decision'],'REJECT')

    def test_every_route_binding_field_is_strict(self):
        base=row(volume='1',volume_unit_key='SYNTH_VOLUME',volume_unit_version='1',
                 quantity_basis_unit_key='SYNTH_QUANTITY',quantity_basis_unit_version='1',quantity_basis_amount='1')
        replacements=dict(asset_id='999',source_id='999',id='999',unit_contract_version='wrong',
                          quote_unit_key='GBP',quote_unit_version='2',quantity_basis_unit_key='SYNTH_VOLUME',
                          quantity_basis_unit_version='2',quantity_basis_amount='2',volume_unit_key='SYNTH_QUANTITY',volume_unit_version='2')
        for field,value in replacements.items():
            binding=route(base);binding['route'][field]=value
            self.assertEqual(self.plan(base,binding,catalog=self.synthetic)['decision'],'REJECT',field)

    def test_route_revision_and_format_dispatch_are_explicit(self):
        for version in (None,0,3,'2',True):
            self.assertEqual(self.plan(format_version=version)['decision'],'REJECT')
        for rev in ('0','-1','01',1.0):
            self.assertEqual(self.plan(route_contract=route(row(),route_revision=rev))['decision'],'REJECT')
        self.assertEqual(self.plan(intent='V1_REPLAY')['decision'],'REJECT')
        self.assertEqual(self.plan(format_version=1,intent='V1_REPLAY')['decision'],'REJECT')
        legacy={k:row()[k] for k in obs.V1_FIELDS}
        self.assertEqual(self.plan(legacy,route(legacy,1))['decision'],'REJECT')
        with self.assertRaises(ValueError):writer.WriterPlanner(self.catalog,[route(row(),1)])

    def test_route_snapshot_and_unit_catalog_cannot_be_mutated_by_input_or_results(self):
        value=row();envelope=route(value);planner=writer.WriterPlanner(self.catalog,[envelope])
        envelope['route']['quote_unit_key']='GBP'
        a=planner.plan(value,format_version=2,intent='NEW_NATIVE_V2',created_at=CREATED)
        a['route_binding']['matched_fields']['quote_unit_key']='GBP'
        self.assertEqual(planner.plan(value,format_version=2,intent='NEW_NATIVE_V2',created_at=CREATED)['decision'],'INSERT')
        definition=self.catalog.resolve('GBX','1',adapter.units.CONTRACT);definition['scale_denominator']='2'
        self.assertEqual(self.catalog.resolve('GBX','1',adapter.units.CONTRACT)['scale_denominator'],'100')
        with self.assertRaises(ValueError):writer.WriterPlanner(self.catalog,[route(value),route(value,route_revision='2')])

    def test_all_numeric_floats_exponents_invalid_prices_and_times_rejected(self):
        for field in ('asset_id','source_id','route_id','price','bid','ask','volume','quote_unit_version'):
            for value in (1.5,'1e2',True):
                self.assertEqual(self.plan(row(**{field:value}))['decision'],'REJECT',(field,value))
        for changes in (dict(price='0'),dict(price='-1'),dict(price='1'*19),dict(price='0.00000000001'),
                        dict(bid='125',ask='124'),dict(market_at='2026-02-30 00:00:00'),dict(observed_at='now')):
            self.assertEqual(self.plan(row(**changes))['decision'],'REJECT',changes)

    def test_manifest_fingerprint_and_each_definition_semantic_field_are_pinned(self):
        original=adapter.units.load_manifest()
        for field,value in [('status','draft'),('unit_contract_version','other'),('dimension_key','energy'),
                            ('monetary_currency_code','GBP'),('base_unit_key','GBP'),('scale_numerator','2'),
                            ('scale_denominator','3'),('unit_version','2'),('definition_sha256','0'*64)]:
            changed=copy.deepcopy(original);changed['definitions'][0][field]=value
            with self.assertRaises(ValueError):adapter.UnitCatalog(changed,adapter.APPROVED)
        changed=copy.deepcopy(original);changed['definitions'][-1]['scale_denominator']='50'
        changed['definitions'][-1]['definition_sha256']=adapter.units.definition_sha256(changed['definitions'][-1])
        changed['package_sha256']=adapter.units.package_sha256(changed)
        with self.assertRaisesRegex(ValueError,'unapproved'):adapter.UnitCatalog(changed,adapter.APPROVED)
        self.assertEqual(adapter.normative_catalog().fingerprint,adapter.APPROVED)

    def test_projected_display_never_becomes_second_native_observation(self):
        native=self.plan(row('GBX'));self.assertEqual(native['normalized']['price'],'123.4500000000')
        self.assertEqual(self.catalog.project('123.45','GBX','1'),'1.2345')
        self.assertEqual(self.plan(row('GBP',price='1.2345'),representation='base_projection')['decision'],'REJECT')
        history=[dict(format_version=2,payload=native['normalized'],dedupe_key=native['dedupe_key'])]
        self.assertEqual(self.plan(row('GBP',route_id='302',price='1.2345'),existing=history)['decision'],'REJECT')

    def test_existing_v1_fact_cannot_be_reimported_under_v2_or_new_route(self):
        legacy={k:row()[k] for k in obs.V1_FIELDS};proof=obs.shared('legacy',row=legacy)
        stored=dict(format_version=1,payload=proof['row'],dedupe_key=bytes.fromhex(proof['dedupe_hex']))
        self.assertEqual(self.plan(existing=[stored])['decision'],'REJECT')
        self.assertEqual(self.plan(row(route_id='302'),existing=[stored])['decision'],'REJECT')

    def test_stored_snapshot_hash_mismatch_cannot_enable_an_insert(self):
        stored=dict(format_version=2,payload=self.plan()['normalized'],dedupe_key=b'x'*32)
        self.assertEqual(self.plan(row(observed_at='2026-01-02 00:00:00'),existing=[stored])['decision'],'REJECT')

    def test_v1_source_and_homepage_are_byteidentical(self):
        for path,digest in [('scripts/phase3c/market_flow.php','ab2b9510da0a76b549b587e10db5d768f079b57cd1d4e0d6542b46f805cd33af'),
                            ('index.html','55e479482b15e6f698e7a96a595dd7093b80894f73ca5a59e579424e92a18583'),
                            ('docs/database/migrations/0003_market_units.sql','199933884802bd139b706e50e57e04687e9cbe5f8bd1366e98e302af7d47b8ee')]:
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest)

    def test_eight_frozen_v1_canonical_vectors_and_replay_stay_identical(self):
        fixture=json.loads((ROOT/'tests/fixtures/phase3n_v1_vectors.json').read_text(encoding='utf-8'))
        self.assertEqual(len(fixture['vectors']),8)
        envelopes=[];history=[]
        for vector in fixture['vectors']:
            value=vector['input'];proof=obs.shared('legacy',row=value)
            self.assertEqual(proof['canonical'],vector['canonical'])
            self.assertEqual(proof['dedupe_hex'],vector['dedupe_hex'])
            envelopes.append(route(value,1))
            history.append(dict(format_version=1,payload=proof['row'],dedupe_key=bytes.fromhex(vector['dedupe_hex'])))
        planner=writer.WriterPlanner(self.catalog,envelopes,history)
        before=copy.deepcopy(history)
        for vector in fixture['vectors']:
            result=planner.plan(vector['input'],format_version=1,intent='V1_REPLAY',created_at=CREATED)
            self.assertEqual(result['decision'],'DUPLICATE_UNCHANGED',result)
            self.assertEqual(result['canonical_bytes'],vector['canonical'].encode())
            self.assertEqual(result['dedupe_key'].hex(),vector['dedupe_hex'])
            self.assertIsNone(result['observation_format_version'])
        self.assertEqual(before,history)

    def test_no_new_v1_insert_and_no_old_physical_route_reinterpretation(self):
        legacy={k:row()[k] for k in obs.V1_FIELDS}
        self.assertEqual(self.plan(legacy,route(legacy,1),format_version=1,intent='V1_REPLAY')['decision'],'REJECT')
        native=self.plan();stored=dict(format_version=2,payload=native['normalized'],dedupe_key=native['dedupe_key'])
        changed=row('GBP',observed_at='2026-01-02 00:00:00')
        self.assertEqual(self.plan(changed,existing=[stored])['decision'],'REJECT')
        prior=obs.shared('legacy',row=legacy)
        stored=dict(format_version=1,payload=prior['row'],dedupe_key=bytes.fromhex(prior['dedupe_hex']))
        self.assertEqual(self.plan(row(observed_at='2026-01-02 00:00:00'),existing=[stored])['decision'],'REJECT')

    def test_missing_extra_or_derived_payload_fields_rejected(self):
        for field in obs.FIELDS:
            value=row();del value[field]
            self.assertEqual(self.plan(value,route(row()))['decision'],'REJECT',field)
            with self.assertRaises(ValueError):obs.normalize_observation(value,self.catalog)
        for field in ('created_at','scale_numerator','dimension_key','definition_reference','base_projection'):
            self.assertEqual(self.plan(dict(row(),**{field:'extra'}))['decision'],'REJECT',field)

    def test_v1_v2_domains_separate_without_upgrading_payload(self):
        old=obs.shared('legacy',row={k:row()[k] for k in obs.V1_FIELDS})
        new=self.plan();self.assertNotEqual(bytes.fromhex(old['dedupe_hex']),new['dedupe_key'])
        self.assertTrue(old['canonical'].startswith('mosa2-observation-v1\n'))
        self.assertEqual(list(old['row']),list(obs.V1_FIELDS))

    def test_local_value_adapter_only_no_network_or_persistence_capability(self):
        run=subprocess.run
        with patch.object(obs.subprocess,'run',wraps=run) as calls:
            result=self.plan();self.assertEqual(result['decision'],'INSERT')
        for call in calls.call_args_list:
            self.assertEqual(call.args[0],['php',str(obs.HERE/'value_adapter.php')])
        source='\n'.join(p.read_text(encoding='utf-8') for p in (ROOT/'scripts/phase3n').glob('*') if p.is_file())
        for forbidden in ('PDO','mysqli','socket','urllib','requests','INSERT INTO','UPDATE ','execute(', 'datetime.now', 'GBX','POINT','GBP','EUR'):
            self.assertNotIn(forbidden,source)
        lint=subprocess.run(['php','-l',str(ROOT/'scripts/phase3n/value_adapter.php')],capture_output=True,text=True)
        self.assertEqual(lint.returncode,0,lint.stderr+lint.stdout)


if __name__ == '__main__':
    unittest.main()
