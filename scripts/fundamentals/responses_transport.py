"""Fixed OpenAI Responses endpoint; explicit future authorization only. No env/key reads."""
import http.client
import json
from .assessment import AssessmentError, canonical, need

class OpenAIResponsesTransport:
    is_live=True
    def __init__(self,api_key,*,live_authorized=False):
        need(live_authorized is True,'LIVE_NOT_AUTHORIZED')
        need(isinstance(api_key,str) and 1<=len(api_key)<=4096 and api_key.isascii() and not any(c.isspace() for c in api_key),'SECRET_INVALID')
        self._key=api_key;self._consumed=False
    def __call__(self,request,*,timeout,max_response_bytes):
        need(not self._consumed,'ALREADY_CONSUMED')
        need(timeout==60 and max_response_bytes==65536,'TRANSPORT_LIMITS')
        need(request.get('store') is False and request.get('tools')==[] and request.get('tool_choice')=='none','TRANSPORT_POLICY')
        raw=canonical(request).encode('utf-8');need(len(raw)<=30000,'REQUEST_BOUND')
        self._consumed=True;conn=None
        try:
            conn=http.client.HTTPSConnection('api.openai.com',443,timeout=timeout)
            conn.request('POST','/v1/responses',body=raw,headers={'Authorization':'Bearer '+self._key,'Content-Type':'application/json'})
            response=conn.getresponse()
            need(response.status==200,'MODEL_HTTP_FAILED')
            body=response.read(max_response_bytes+1);need(len(body)<=max_response_bytes,'MODEL_RESPONSE_BOUND')
            return json.loads(body)
        except AssessmentError:raise
        except Exception:raise AssessmentError('MODEL_TRANSPORT_FAILED') from None
        finally:
            if conn is not None:conn.close()
