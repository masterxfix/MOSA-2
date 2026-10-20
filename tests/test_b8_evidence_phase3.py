"""Synthetic evidence gates only; no historical identifiers or market values."""
import copy
import importlib.util
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('phase3q_test', ROOT/'scripts/phase3q/evidence.py')
q = importlib.util.module_from_spec(spec);spec.loader.exec_module(q)


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.records = [dict(source_identifier_type='synthetic', source_identifier_value='SYNTH-ONE',
            historical_name='Synthetic instrument', historical_asset_class='Synthetic class',
            historical_provider_instrument='SYNTH.L', historical_source_type='market_data', evidence_reference='fixture:one')]
        self.kw = dict(target=dict(identifier_matches=1, asset_id='101'), source_id='201',
            route=dict(status='PRESENT', qualified=True, id='702', revision='2'),
            provenance=dict(raw_payload=True, deployment_binding=True), reimport='NO_MATCH')
        self.binding = dict(unit_contract_version='mosa2-market-unit-v1', quote_unit_key='GBX', quote_unit_version='1',
            quantity_basis_unit_key=None, quantity_basis_unit_version=None, quantity_basis_amount=None,
            volume_unit_key=None, volume_unit_version=None)
        self.raw = dict(asset_id='101',source_id='201',route_id='702',currency='GBP',price='123.45',bid=None,ask=None,
            volume=None,market_at='2001-01-01 10:00:00',observed_at='2001-01-01 10:05:00',**self.binding)
        route = dict(id='702',asset_id='101',source_id='201',route_revision='2',**self.binding)
        self.plan_kw = dict(raw=self.raw,route_envelopes=[dict(format_version=2,route=route)],existing=[],
            created_at='2001-01-01 10:06:00',catalog=q.prior.writer.observation.catalog_module.normative_catalog())

    def verdict(self):return q.qualify(self.records, **self.kw)
    def plan(self):return q.history_plan(self.records, **self.kw, **self.plan_kw)

    def test_complete_identity_and_existing_group_are_qualified(self):
        self.assertEqual(q.identity_status(self.records),'PASS')
        result=self.verdict();self.assertEqual(result['classification'],'IMPORT_READY')
        self.assertEqual(result['route_group'],'PRESENT');self.assertEqual(result['actual_revision'],'2')

    def test_complementary_referenced_records_and_missing_fields(self):
        second=self.records[0].copy();second.pop('historical_name')
        self.assertEqual(q.identity_status([second]),'OPEN')
        self.assertEqual(q.identity_status([second,self.records[0]]),'PASS')
        second['evidence_reference']='';self.assertEqual(q.identity_status([second]),'OPEN')

    def test_conflicting_identity_stops_before_writer(self):
        self.records.append(dict(self.records[0],historical_name='Different instrument'))
        with patch.object(q.prior,'history_plan',side_effect=AssertionError('must not plan')):
            result,plan=self.plan()
        self.assertEqual(result['classification'],'IDENTITY_CONFLICT');self.assertIsNone(plan)

    def test_missing_target_requires_new_masterdata_no_revision_or_plan(self):
        self.kw['target']=dict(identifier_matches=0,asset_id=None)
        result,plan=self.plan()
        self.assertTrue(result['new_masterdata_required']);self.assertEqual(result['actual_revision'],'OPEN')
        self.assertEqual(result['classification'],'AUTHORITATIVE_SOURCE_REQUIRED');self.assertIsNone(plan)

    def test_ambiguous_target_identity_conflicts(self):
        self.kw['target']['identifier_matches']=2
        self.assertEqual(self.verdict()['classification'],'IDENTITY_CONFLICT')

    def test_absent_and_unqualified_group_do_not_invent_a_revision(self):
        for status in ('ABSENT','OPEN'):
            self.kw['route']['status']=status
            result,plan=self.plan();self.assertEqual(result['actual_revision'],'OPEN');self.assertIsNone(plan)
            self.assertIn('target_route_unqualified',result['blockers'])

    def test_missing_provenance_is_not_automatically_permanent_loss(self):
        self.kw['provenance']['raw_payload']=False
        self.assertEqual(self.verdict()['classification'],'AUTHORITATIVE_SOURCE_REQUIRED')
        self.kw['provenance'].update(permanently_unavailable=True,remaining_contract_complete=True)
        result,plan=self.plan()
        self.assertEqual(result['classification'],'PROVENANCE_GAP_ACCEPTANCE_REQUIRED');self.assertIsNone(plan)

    def test_gap_acceptance_cannot_hide_identity_or_target_gap(self):
        self.kw['provenance'].update(raw_payload=False,permanently_unavailable=True,remaining_contract_complete=True)
        self.kw['target']=dict(identifier_matches=0,asset_id=None)
        self.assertEqual(self.verdict()['classification'],'AUTHORITATIVE_SOURCE_REQUIRED')

    def test_v1_match_and_open_comparison_block_no_match_can_plan(self):
        for status in ('MATCH','OPEN'):
            self.kw['reimport']=status
            result,plan=self.plan();self.assertIsNone(plan);self.assertEqual(result['dry_run'],'NOT_RUN')
        self.kw['reimport']='NO_MATCH'
        self.assertEqual(self.plan()[1]['decision'],'INSERT')

    def test_each_incomplete_prerequisite_prevents_writer_call(self):
        baseline=copy.deepcopy(self.kw)
        mutations=[('source_id',None),('provenance',dict(raw_payload=True,deployment_binding=False)),
                   ('route',dict(status='PRESENT',qualified=False)),('reimport','OPEN')]
        for field,value in mutations:
            self.kw=copy.deepcopy(baseline);self.kw[field]=value
            with patch.object(q.prior,'history_plan',side_effect=AssertionError('must not plan')):
                self.assertIsNone(self.plan()[1])

    def test_actual_writer_reimport_guard_overrules_incorrect_clearance(self):
        row={k:self.raw[k] for k in q.prior.writer.observation.V1_FIELDS};row['route_id']='701'
        old=q.prior.writer.observation.shared('legacy',row=row)
        self.plan_kw['existing']=[dict(format_version=1,payload=old['row'],dedupe_key=bytes.fromhex(old['dedupe_hex']))]
        result,plan=self.plan();self.assertEqual(plan['decision'],'REJECT')
        self.assertNotEqual(result['classification'],'IMPORT_READY')

    def test_plan_cannot_switch_qualified_asset_or_revision(self):
        self.raw['asset_id']='102'
        with self.assertRaisesRegex(ValueError,'identity'):self.plan()
        self.raw['asset_id']='101';self.kw['route']['revision']='3'
        with self.assertRaisesRegex(ValueError,'revision'):self.plan()

    def test_complete_plan_is_native_and_preserves_inputs_without_network(self):
        before=copy.deepcopy((self.records,self.kw,self.raw,self.plan_kw['route_envelopes']))
        with patch.object(socket,'socket',side_effect=AssertionError('no network')):
            result,plan=self.plan()
        self.assertEqual(result['classification'],'IMPORT_READY');self.assertEqual(result['dry_run'],'INSERT')
        self.assertEqual(plan['normalized']['quote_unit_key'],'GBX');self.assertEqual(plan['normalized']['currency'],'GBP')
        self.assertIsNone(plan['normalized']['volume'])
        self.assertEqual((self.records,self.kw,self.raw,self.plan_kw['route_envelopes']),before)
        source=(ROOT/'scripts/phase3q/evidence.py').read_text()
        for forbidden in ('sqlite','mysql','PDO','requests','urllib','write_text','write_bytes','connect('):
            self.assertNotIn(forbidden,source)


if __name__=='__main__':unittest.main()
