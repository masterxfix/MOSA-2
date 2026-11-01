import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from scripts import pdf_archive_diagnose as d
from test_fundamentals_pdf import fixture

class Doc:
 def __init__(self,allowed=True,pages=1,text='safe'):self.doc=SimpleNamespace(is_extractable=allowed);self.pages=[self]*pages;self.text=text
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def dedupe_chars(self,**kw):return self
 def extract_words(self,**kw):return [dict(text=self.text)]
class Tests(unittest.TestCase):
 def test_classes_and_no_forbidden_extraction(self):
  for doc,code in [(Doc(False),'PDF_EXTRACTION_FORBIDDEN'),(Doc(pages=201),'PDF_PAGE_LIMIT'),(Doc(text='x'*2000001),'PDF_CHARACTER_LIMIT'),(Doc(),'NONE')]:
   result=d.inspect_pdf(b'%PDF-synthetic',lambda *a,**kw:doc)
   self.assertEqual(result['first_error'],code)
   self.assertLess(len(json.dumps(result)),4096);self.assertNotIn('safe',json.dumps(result))
  result=d.inspect_pdf(fixture());self.assertTrue(result['pdf_open']);self.assertEqual(result['first_error'],'NONE')
 def test_corrupt_pdf(self):self.assertEqual(d.inspect_pdf(b'%PDF-corrupt')['first_error'],'PDF_LIBRARY_OR_STRUCTURE')
 def test_hash_and_remote_validation(self):
  raw=b'synthetic';import hashlib
  with patch.dict(d.PROFILE,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()):
   d.verify_bytes(raw)
   with self.assertRaises(ValueError):d.verify_bytes(raw+b'bad')
   with patch.object(d.remote,'remote_call',return_value=(0,json.dumps(dict(ok=True,bytes=len(raw),sha256=d.PROFILE['sha256'])).encode(),False,1)) as call:
    d.archive_receipt(None)
    payload=json.loads(call.call_args.args[2]);self.assertIn('ORIGINAL_MARKER',payload['source']);self.assertIn('STABLE_ARCHIVE',payload['source'])
   with patch.object(d.remote,'remote_call',return_value=(0,b'{"ok":false}',False,1)):
    with self.assertRaises(ValueError):d.archive_receipt(None)
