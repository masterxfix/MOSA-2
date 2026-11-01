import copy
from datetime import datetime,timezone
import json
import unittest
from unittest.mock import Mock
from scripts.fundamentals import assessment as a
from test_fundamentals_analysis import fact,snapshot

NOW=datetime(2026,11,1,15,0,tzinfo=timezone.utc)
PRICE=dict(model='gpt-6.1-sol',input_per_million='2',output_per_million='10',checked_at=NOW.isoformat(),source_url='https://developers.openai.com/api/docs/models/gpt-6.1-sol')
def input_data():return snapshot([fact(1,'revenue','50',2024),fact(2,'revenue','200'),fact(3,'ebitda','10'),fact(4,'ebitda_underlying','30')])

def output_for(request):
    package=json.loads(request['input']);p=package['snapshot'];m=package['required_metadata']
    result=dict(m,factual_claims=[dict(observation_id=f['observation_id'],metric_key=f['metric'],value=f['value'],unit_key=f['unit'],source_id=f['source_id'],origin=f['origin'],rounded=f['rounded']) for f in p['facts']],calculation_claims=[dict(calculation_id=c['calculation_id'],value=c['value']) for c in p['calculations']],interpretations=[dict(code='CURATED_ROUNDING',observation_ids=['1'],calculation_ids=[])],uncertainties=['CAUSES_NOT_ESTABLISHED'],missing_information=p['missing_metrics'])
    return result

def response(request,change=lambda x:x):
    result=change(output_for(request))
    return dict(status='completed',model=request['model'],id='synthetic-response',usage=dict(input_tokens=100,output_tokens=200),output=[dict(type='message',status='completed',content=[dict(type='output_text',text=json.dumps(result))])])

class AssessmentTests(unittest.TestCase):
 def call(self,transport,**kwargs):
    return a.ResponsesAdapter(transport).assess(input_data(),price=PRICE,now=NOW,simulate=True,**kwargs)
 def test_valid_strict_response_config_and_usage(self):
    calls=[]
    def fake(request,**options):
        calls.append(request);self.assertEqual(options,dict(timeout=60,max_response_bytes=65536))
        self.assertFalse(request['store']);self.assertEqual(request['tools'],[]);self.assertEqual(request['reasoning']['effort'],'medium')
        self.assertTrue(request['text']['format']['strict']);return response(request)
    r=self.call(fake);self.assertTrue(r['simulated']);self.assertFalse(r['model_executed']);self.assertEqual(len(calls),1)
    self.assertEqual(r['usage']['output_tokens'],200)
 def test_stable_digest_and_calculation_identifiers(self):
    p,h=a.prepare(input_data());p2,h2=a.prepare(copy.deepcopy(input_data()));self.assertEqual(h,h2)
    self.assertEqual(p['calculations'],p2['calculations']);p['facts'][0]['value']='51';self.assertNotEqual(a.prepare(p)[1],h)
 def test_bad_claims_digest_references_metrics_numbers_and_origin(self):
    variants=[lambda r:r.update(input_digest='wrong'),lambda r:r['factual_claims'][0].update(observation_id='999'),
      lambda r:r['factual_claims'][0].update(metric_key='invented_metric'),lambda r:r['factual_claims'][0].update(value='999'),
      lambda r:r['factual_claims'][0].update(origin='official_issuer'),lambda r:r['factual_claims'][0].update(rounded=False),
      lambda r:r['calculation_claims'][0].update(calculation_id='invalid'),lambda r:r['calculation_claims'][0].update(value='999'),
      lambda r:r['factual_claims'].pop(),lambda r:r.pop('uncertainties'),lambda r:r.update(extra='buy now'),
      lambda r:r['interpretations'][0].update(code='BUY'),lambda r:r['interpretations'][0].update(text='profit 999 from invented cause')]
    for edit in variants:
        def change(result):edit(result);return result
        with self.subTest(edit=edit),self.assertRaises(a.AssessmentError):self.call(lambda req,**kw:response(req,change))
 def test_absent_fundamentals_zero_calls(self):
    transport=Mock(side_effect=AssertionError('must not call'))
    r=a.ResponsesAdapter(transport).assess(snapshot([]),now=NOW)
    self.assertEqual(r['assessment']['status'],'INSUFFICIENT_DATA');self.assertIn('revenue',r['assessment']['missing_information']);transport.assert_not_called()
 def test_cost_unknown_stale_over_limit_and_no_authorization(self):
    transport=Mock()
    for price in [None,dict(PRICE,input_per_million='999'),dict(PRICE,checked_at='2025-01-01T00:00:00+00:00'),dict(PRICE,model='other')]:
        with self.assertRaises(a.AssessmentError):a.ResponsesAdapter(transport).assess(input_data(),price=price,now=NOW,simulate=True)
    with self.assertRaisesRegex(a.AssessmentError,'LIVE_NOT_AUTHORIZED'):a.ResponsesAdapter(transport).assess(input_data(),price=PRICE,now=NOW)
    transport.assert_not_called()
 def test_transport_failure_no_retry_secret_suppressed(self):
    transport=Mock(side_effect=RuntimeError('sk-private secret must never be returned'))
    adapter=a.ResponsesAdapter(transport)
    with self.assertRaisesRegex(a.AssessmentError,'^MODEL_TRANSPORT_FAILED$'):adapter.assess(input_data(),price=PRICE,now=NOW,simulate=True)
    with self.assertRaisesRegex(a.AssessmentError,'ALREADY_CONSUMED'):adapter.assess(input_data(),price=PRICE,now=NOW,simulate=True)
    self.assertEqual(transport.call_count,1)
 def test_incomplete_refusal_invalid_json_no_repair(self):
    for kind in ['incomplete','refusal','bad_json']:
        def fake(req,**kw):
            r=response(req)
            if kind=='incomplete':r['status']='incomplete'
            if kind=='refusal':r['output'][0]['content']=[dict(type='refusal',refusal='no')]
            if kind=='bad_json':r['output'][0]['content'][0]['text']='{bad'
            return r
        transport=Mock(side_effect=fake)
        with self.assertRaises(a.AssessmentError):self.call(transport)
        self.assertEqual(transport.call_count,1)
 def test_source_binding_and_input_limit(self):
    p=input_data();p['facts'][0]['source_id']='999'
    with self.assertRaisesRegex(a.AssessmentError,'SOURCE_REFERENCE'):a.prepare(p)
    p=input_data();p['identity']['name']='x'*40000
    with self.assertRaisesRegex(a.AssessmentError,'INPUT_TOKEN_BOUND'):a.ResponsesAdapter(Mock()).assess(p,price=PRICE,now=NOW,simulate=True)

 def test_schema_file_and_fixed_http_transport_mock_only(self):
    from pathlib import Path
    from scripts.fundamentals.responses_transport import OpenAIResponsesTransport
    from unittest.mock import patch
    self.assertEqual(json.loads(Path('scripts/fundamentals/assessment.schema.json').read_bytes()),a.SCHEMA)
    with self.assertRaisesRegex(a.AssessmentError,'LIVE_NOT_AUTHORIZED'):OpenAIResponsesTransport('synthetic-test-key')
    with patch('scripts.fundamentals.responses_transport.http.client.HTTPSConnection') as factory:
        conn=factory.return_value;conn.getresponse.return_value.status=200;conn.getresponse.return_value.read.return_value=b'{"status":"completed"}'
        t=OpenAIResponsesTransport('synthetic-test-key',live_authorized=True)
        result=t(dict(store=False,tools=[],tool_choice='none'),timeout=60,max_response_bytes=65536)
        factory.assert_called_once_with('api.openai.com',443,timeout=60)
        self.assertEqual(conn.request.call_args.args[:2],('POST','/v1/responses'))
        self.assertEqual(result['status'],'completed')
        with self.assertRaisesRegex(a.AssessmentError,'SIMULATION_TRANSPORT_MISMATCH'):self.call(t)
        with self.assertRaisesRegex(a.AssessmentError,'ALREADY_CONSUMED'):t({},timeout=60,max_response_bytes=65536)
        self.assertEqual(conn.request.call_count,1)

# All financial values below are synthetic; no provider, database or model access.
def financial_snapshot(ebitda_after='20',complete=False):
 rows=[fact(1,'revenue','100',2024),fact(2,'revenue','150'),
       fact(3,'ebitda','10',2024),fact(4,'ebitda',ebitda_after),
       fact(5,'ebit','-5',2024),fact(6,'ebit','6'),
       fact(7,'ebitda_underlying','15',2024),fact(8,'ebitda_underlying','12')]
 if complete:rows.extend([fact(9,'profit_after_tax','4'),fact(10,'operating_cashflow','9')])
 return snapshot(rows)

def complete_output(p,sha,interpretations):
 return dict(contract=a.CONTRACT,status='ASSESSED',input_contract=a.INPUT,input_digest=sha,
   model_id='gpt-6.1-sol',generated_at=NOW.isoformat(),invocation_id='synthetic-contract',
   factual_claims=[dict(observation_id=f['observation_id'],metric_key=f['metric'],value=f['value'],unit_key=f['unit'],source_id=f['source_id'],origin=f['origin'],rounded=f['rounded']) for f in p['facts']],
   calculation_claims=[dict(calculation_id=c['calculation_id'],value=c['value']) for c in p['calculations']],
   interpretations=interpretations,uncertainties=[],missing_information=p['missing_metrics'])

def item(code,ids=(),cs=()):return dict(code=code,observation_ids=list(ids),calculation_ids=list(cs))

class InterpretationContractTests(unittest.TestCase):
 def validate(self,s,items):
  p,sha=a.prepare(s);output=complete_output(p,sha,items)
  return a.validate(output,p,sha,'gpt-6.1-sol','synthetic-contract',NOW.isoformat())
 def calc(self,s,kind,ids):
  p,_=a.prepare(s)
  return next(c['calculation_id'] for c in p['calculations'] if c['kind']==kind and c['observation_ids']==list(ids))
 def reject(self,s,value,reason):
  with self.assertRaises(a.InterpretationError) as caught:self.validate(s,[value])
  expected='INTERPRETATION_BINDING:'+value['code']+':'+reason
  self.assertEqual(str(caught.exception),expected);self.assertEqual(a.interpretation_error_code(caught.exception),expected)

 def test_direction_allowlist_excludes_margins_and_handles_rising_falling_ebitda(self):
  for after,direction in [('20','NUMERICAL_INCREASE'),('5','NUMERICAL_DECREASE')]:
   s=financial_snapshot(after);p,_=a.prepare(s);rules=a.interpretation_contract(p)
   for kind in ('absolute_change','growth_percent'):
    ref=self.calc(s,kind,['3','4']);self.assertIn(ref,rules[direction]['calculation_ids'])
    self.validate(s,[item(direction,['3','4'],[ref])])
   revenue=self.calc(s,'growth_percent',['1','2']);self.assertIn(revenue,rules['NUMERICAL_INCREASE']['calculation_ids'])
   margins=[c for c in p['calculations'] if c['kind']=='margin_percent']
   self.assertTrue(any(a.Decimal(c['value'])<0 for c in margins));self.assertTrue(any(a.Decimal(c['value'])>0 for c in margins))
   for c in margins:
    for direction in ('NUMERICAL_INCREASE','NUMERICAL_DECREASE'):
     self.assertNotIn(c['calculation_id'],rules[direction]['calculation_ids'])
     self.reject(s,item(direction,cs=[c['calculation_id']]),'WRONG_CALCULATION_KIND')

 def test_all_five_codes_and_optional_related_fact_references_valid(self):
  s=financial_snapshot();up=self.calc(s,'absolute_change',['1','2']);down=self.calc(s,'growth_percent',['7','8'])
  gap=self.calc(s,'adjustment_gap',['8','4'])
  values=[item('NUMERICAL_INCREASE',cs=[up]),item('NUMERICAL_INCREASE',['1','2'],[up]),
    item('NUMERICAL_DECREASE',['7','8'],[down]),item('ADJUSTMENT_GAP',['8','4'],[gap]),
    item('CURATED_ROUNDING',['1','4']),item('LIMITED_COVERAGE',['2'])]
  self.assertEqual(self.validate(s,values)['interpretations'],values)
  for code in ('NUMERICAL_INCREASE','NUMERICAL_DECREASE','CURATED_ROUNDING','LIMITED_COVERAGE'):
   self.reject(s,item(code,cs=[gap]),'WRONG_CALCULATION_KIND' if code.startswith('NUMERICAL') else 'CALCULATION_NOT_ALLOWED')

 def test_wrong_sign_zero_change_and_missing_calculation_rejected(self):
  s=financial_snapshot();up=self.calc(s,'absolute_change',['1','2']);down=self.calc(s,'absolute_change',['7','8'])
  self.reject(s,item('NUMERICAL_INCREASE',cs=[down]),'WRONG_SIGN')
  self.reject(s,item('NUMERICAL_DECREASE',cs=[up]),'WRONG_SIGN')
  zero=financial_snapshot('10');ref=self.calc(zero,'absolute_change',['3','4'])
  for code in ('NUMERICAL_INCREASE','NUMERICAL_DECREASE'):
   self.reject(zero,item(code,cs=[ref]),'WRONG_SIGN')
   self.reject(s,item(code,['1']),'CALCULATION_REQUIRED')
  self.reject(s,item('ADJUSTMENT_GAP',['1']),'CALCULATION_REQUIRED')

 def test_gap_requires_gap_kind_independent_of_sign(self):
  s=financial_snapshot();ref=self.calc(s,'absolute_change',['1','2'])
  self.reject(s,item('ADJUSTMENT_GAP',cs=[ref]),'WRONG_CALCULATION_KIND')
  p,_=a.prepare(s);gaps=[c for c in p['calculations'] if c['kind']=='adjustment_gap']
  self.assertTrue(any(a.Decimal(c['value'])>0 for c in gaps));self.assertTrue(any(a.Decimal(c['value'])<0 for c in gaps))
  self.validate(s,[item('ADJUSTMENT_GAP',cs=[c['calculation_id']]) for c in gaps])

 def test_rounding_requires_true_fact_flag_and_never_calculations(self):
  s=financial_snapshot()
  for value in (None,False):
   s['facts'][0].update(origin='issuer_release',rounded=value)
   p,_=a.prepare(s);rules=a.interpretation_contract(p)
   self.assertNotIn('1',rules['CURATED_ROUNDING']['observation_ids'])
   self.reject(s,item('CURATED_ROUNDING',['1']),'FACT_NOT_ROUNDED')
  self.reject(s,item('CURATED_ROUNDING'),'FACT_REQUIRED')
  self.validate(s,[item('CURATED_ROUNDING',['2'])])

 def test_limited_coverage_requires_actual_missing_metrics_and_context_fact(self):
  s=financial_snapshot();p,_=a.prepare(s);rule=a.interpretation_contract(p)['LIMITED_COVERAGE']
  self.assertEqual(rule['missing_metrics'],['operating_cashflow','profit_after_tax']);self.assertTrue(rule['enabled'])
  self.validate(s,[item('LIMITED_COVERAGE',['2'])])
  self.reject(s,item('LIMITED_COVERAGE'),'FACT_REQUIRED')
  full=financial_snapshot(complete=True);p,_=a.prepare(full)
  self.assertFalse(a.interpretation_contract(p)['LIMITED_COVERAGE']['enabled'])
  self.reject(full,item('LIMITED_COVERAGE',['2']),'MISSING_INFORMATION_NOT_ESTABLISHED')

 def test_unknown_duplicate_and_unrelated_references_rejected_safely(self):
  s=financial_snapshot();up=self.calc(s,'growth_percent',['1','2'])
  self.reject(s,item('NUMERICAL_INCREASE',['4'],[up]),'FACT_NOT_IN_REFERENCED_CALCULATION')
  self.reject(s,item('NUMERICAL_INCREASE',cs=[up,up]),'DUPLICATE_REFERENCE')
  self.reject(s,item('CURATED_ROUNDING',['1','1']),'DUPLICATE_REFERENCE')
  self.reject(s,item('CURATED_ROUNDING',['private-model-text']),'UNKNOWN_FACT_REFERENCE')
  self.reject(s,item('NUMERICAL_INCREASE',cs=['private-model-text']),'UNKNOWN_CALCULATION_REFERENCE')
  self.assertIsNone(a.interpretation_error_code(RuntimeError('private-model-text')))
  with self.assertRaisesRegex(a.AssessmentError,'^INTERPRETATION_BINDING$'):a.InterpretationError('private-model-text','wrong')

 def test_request_mapping_matches_validator_and_cannot_override_it(self):
  s=financial_snapshot();seen=[]
  def fake(req,**kw):
   package=json.loads(req['input']);p=package['snapshot'];rules=package['interpretation_contract'];seen.append(req)
   self.assertEqual(rules,a.interpretation_contract(p));self.assertIn('interpretation_contract is authoritative',req['instructions'])
   self.assertIn('Never use margin_percent',req['instructions'])
   values=[]
   for code,rule in rules.items():
    if not rule['enabled']:continue
    values.append(item(code,cs=rule['calculation_ids'][:1]) if rule['basis']=='calculations' else item(code,rule['observation_ids'][:1]))
   output=complete_output(p,package['required_metadata']['input_digest'],values);output.update(package['required_metadata'])
   return dict(status='completed',model=req['model'],id='synthetic-valid',usage=dict(input_tokens=100,output_tokens=200),
    output=[dict(type='message',status='completed',content=[dict(type='output_text',text=json.dumps(output))])])
  r=a.ResponsesAdapter(fake).assess(s,price=PRICE,now=NOW,simulate=True)
  self.assertTrue(r['simulated']);self.assertFalse(r['model_executed']);self.assertEqual(len(seen),1)
  self.assertEqual({v['code'] for v in r['assessment']['interpretations']},set(a.CODES))
  p,_=a.prepare(s);forged=a.interpretation_contract(p);forged['NUMERICAL_INCREASE']['kinds'].append('margin_percent')
  self.assertNotIn('margin_percent',a.interpretation_contract(p)['NUMERICAL_INCREASE']['kinds'])
  margin=next(c['calculation_id'] for c in p['calculations'] if c['kind']=='margin_percent')
  forged['NUMERICAL_INCREASE']['calculation_ids'].append(margin)
  self.reject(s,item('NUMERICAL_INCREASE',cs=[margin]),'WRONG_CALCULATION_KIND')

 def test_pne_zeiss_droneshield_same_general_contract_simulated_only(self):
  from scripts.fundamentals.analysis import build
  for name,isin,currency,parser,offset in [('PNE','DE000A0JBPG2','EUR','issuer_html_v1',False),
     ('Zeiss','DE0005313704','EUR','issuer_html_v1',True),('DroneShield','AU000000DRO2','AUD','curated_public_facts_v1',False)]:
   with self.subTest(issuer=name):
    rows=[]
    for year,revenue,ebitda in [(2024,'100','-5'),(2025,'150','20')]:
     for metric,value in [('revenue',revenue),('ebitda',ebitda)]:
      row=fact(len(rows)+1,metric,value,year,currency=currency,unit=currency+'_MILLION');row['parser_key']=parser
      if offset:row.update(period_start=f'{year-1}-10-01',period_end=f'{year}-09-30')
      rows.append(row)
    s=build(dict(id='synthetic',name=name,identifiers=[dict(normalized_value=isin)],facts=rows,current={},market_sources=[]),[dict(id=1,source_type='issuer_release')])
    calls=[]
    def fake(req,**kw):
     calls.append(req);package=json.loads(req['input']);rule=package['interpretation_contract']['NUMERICAL_INCREASE']
     output=complete_output(package['snapshot'],package['required_metadata']['input_digest'],[item('NUMERICAL_INCREASE',cs=rule['calculation_ids'][:1])]);output.update(package['required_metadata'])
     return dict(status='completed',model=req['model'],id='synthetic-'+name,usage=dict(input_tokens=100,output_tokens=200),output=[dict(type='message',status='completed',content=[dict(type='output_text',text=json.dumps(output))])])
    r=a.ResponsesAdapter(fake).assess(s,price=PRICE,now=NOW,simulate=True)
    self.assertTrue(r['simulated']);self.assertFalse(r['model_executed']);self.assertEqual(len(calls),1)
    self.assertEqual(r['assessment']['input_contract'],a.INPUT)
    p,_=a.prepare(s);self.assertEqual(a.interpretation_contract(p)['CURATED_ROUNDING']['enabled'],name=='DroneShield')
    self.assertEqual(p['facts'][0]['start'],'2023-10-01' if offset else '2024-01-01')
