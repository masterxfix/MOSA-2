"""Only synthetic instruments, identities, prices and times; no private B8 data."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('phase3p_qualification_test',ROOT/'scripts/phase3p/qualification.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)


class ReadonlyQualificationTests(unittest.TestCase):
    def setUp(self):
        self.catalog=q.writer.observation.catalog_module.normative_catalog()
        self.binding=dict(unit_contract_version='mosa2-market-unit-v1',quote_unit_key='GBX',quote_unit_version='1',
            quantity_basis_unit_key=None,quantity_basis_unit_version=None,quantity_basis_amount=None,
            volume_unit_key=None,volume_unit_version=None)
        self.legacy=dict(id='701',asset_id='101',source_id='201',route_type='snapshot',external_key='SYNTH.L',
            route_revision='1',**dict.fromkeys(q.UNIT_FIELDS))
        self.routes=[copy.deepcopy(self.legacy)]

    def proposal(self):return q.revision_proposal(self.legacy,self.routes,self.binding,self.catalog)

    def inputs(self):
        proposed=self.proposal()
        # This ID belongs only to this synthetic offline test, never to real B8.
        route={k:proposed[k] for k in ('asset_id','source_id','route_revision',*q.UNIT_FIELDS)}
        route['id']='702'
        raw=dict(asset_id='101',source_id='201',route_id='702',currency='GBP',price='123.45',bid=None,ask=None,volume=None,
            market_at='2001-01-01 10:00:00',observed_at='2001-01-01 10:05:00',**self.binding)
        return raw,[dict(format_version=2,route=route)]

    def test_gbx_gbp_native_number_and_null_volume(self):
        raw,envelopes=self.inputs();plan=q.history_plan(raw,envelopes,[],'2001-01-01 10:06:00',self.catalog)
        self.assertEqual(plan['decision'],'INSERT')
        self.assertEqual(plan['normalized']['price'],'123.4500000000')
        self.assertEqual(plan['normalized']['currency'],'GBP')
        self.assertEqual(plan['normalized']['quote_unit_key'],'GBX')
        self.assertEqual(self.catalog.project('123.45','GBX','1'),'1.2345')
        self.assertIsNone(plan['normalized']['volume']);self.assertIsNone(plan['normalized']['volume_unit_key'])
        for field in q.UNIT_FIELDS[3:6]:self.assertIsNone(plan['normalized'][field])

    def test_new_revision_has_no_allocated_id_and_preserves_legacy(self):
        before=copy.deepcopy((self.legacy,self.routes,self.binding));proposal=self.proposal()
        self.assertNotIn('id',proposal);self.assertEqual(proposal['route_revision'],'2')
        self.assertEqual((self.legacy,self.routes,self.binding),before)
        self.assertTrue(all(self.legacy[k] is None for k in q.UNIT_FIELDS))

    def test_revision_follows_full_group_and_both_unique_contracts(self):
        self.routes.append(dict(self.legacy,id='703',route_revision='4',**self.binding))
        self.assertEqual(self.proposal()['route_revision'],'5')
        for field in ('asset_id','external_key'):
            conflict=self.proposal();conflict['route_revision']='4';conflict[field]='102' if field=='asset_id' else 'OTHER.L'
            with self.assertRaises(ValueError):q.check_unique(conflict,self.routes)

    def test_provider_instrument_cannot_move_to_another_asset(self):
        self.routes.append(dict(self.legacy,id='703',asset_id='102',route_revision='2'))
        with self.assertRaisesRegex(ValueError,'identity conflict'):self.proposal()

    def test_group_cannot_hide_an_instrument_change_in_a_revision(self):
        self.routes.append(dict(self.legacy,id='703',external_key='OTHER.L',route_revision='2'))
        with self.assertRaisesRegex(ValueError,'instrument conflict'):self.proposal()

    def test_unit_not_encoded_into_external_key_or_role(self):
        proposal=self.proposal()
        for field in ('external_key','route_type'):self.assertEqual(proposal[field],self.legacy[field])

    def test_market_and_observed_time_stay_separate(self):
        raw,envelopes=self.inputs();plan=q.history_plan(raw,envelopes,[],'2001-01-01 10:06:00',self.catalog)
        self.assertEqual(plan['normalized']['market_at'],'2001-01-01 10:00:00.000000')
        self.assertEqual(plan['normalized']['observed_at'],'2001-01-01 10:05:00.000000')

    def test_v1_fact_cannot_be_reimported_through_a_new_v2_route(self):
        raw,envelopes=self.inputs()
        prior={k:raw[k] for k in q.writer.observation.V1_FIELDS};prior['route_id']='701'
        legacy=q.writer.observation.shared('legacy',row=prior)
        existing=[dict(format_version=1,payload=legacy['row'],dedupe_key=bytes.fromhex(legacy['dedupe_hex']))]
        self.assertEqual(q.history_plan(raw,envelopes,existing,'2001-01-01 10:06:00',self.catalog)['decision'],'REJECT')

    def test_unqualified_volume_and_legacy_unit_mutation_fail(self):
        raw,envelopes=self.inputs();raw['volume']='7'
        self.assertEqual(q.history_plan(raw,envelopes,[],'2001-01-01 10:06:00',self.catalog)['decision'],'REJECT')
        self.legacy.update(self.binding);self.routes=[copy.deepcopy(self.legacy)]
        with self.assertRaises(ValueError):self.proposal()

    def test_dry_run_preserves_every_input_and_does_not_select_current(self):
        raw,envelopes=self.inputs();existing=[];before=copy.deepcopy((raw,envelopes,existing))
        plan=q.history_plan(raw,envelopes,existing,'2001-01-01 10:06:00',self.catalog)
        self.assertEqual((raw,envelopes,existing),before)
        self.assertNotIn('current',plan);self.assertNotIn('current_selection',plan)
        source=(ROOT/'scripts/phase3p/qualification.py').read_text()
        for forbidden in ('subprocess','sqlite','mysql','PDO','requests','urllib','write_text','write_bytes','fixlab/'):
            self.assertNotIn(forbidden,source)

    def test_missing_legacy_or_exhausted_revision_cannot_be_invented(self):
        with self.assertRaises(ValueError):q.revision_proposal(self.legacy,[],self.binding,self.catalog)
        self.routes.append(dict(self.legacy,id='703',route_revision=str(q.UINT32)))
        with self.assertRaisesRegex(ValueError,'exhausted'):self.proposal()

    def test_noncanonical_identity_cannot_hide_a_unique_conflict(self):
        self.routes.append(dict(self.legacy,id='703',source_id=201,route_revision='2'))
        with self.assertRaisesRegex(ValueError,'canonical unique-key identity'):self.proposal()


if __name__=='__main__':unittest.main()
