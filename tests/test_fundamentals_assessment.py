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
