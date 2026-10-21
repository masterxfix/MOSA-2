"""Encrypted private evidence, recoverable with the existing SSH secret or local recipient key."""
import base64
import json
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from scripts.market_current.takeover import digest
AAD=b'mosa2-current-takeover-evidence-v1'

def b64(value):return base64.b64encode(value).decode('ascii')
def un64(value):return base64.b64decode(value,validate=True)
def kek(password,salt):return HKDF(algorithm=hashes.SHA256(),length=32,salt=salt,info=AAD).derive(password.encode())

def seal(plan,recipient,password):
    public=serialization.load_der_public_key(un64(recipient))
    if public.key_size<3072:raise ValueError('recipient')
    key=os.urandom(32);nonce=os.urandom(12);salt=os.urandom(16);wrap_nonce=os.urandom(12)
    raw=json.dumps(plan,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return dict(contract=AAD.decode(),plan_sha256=digest(plan),run_id=plan['run_id'],nonce=b64(nonce),
        ciphertext=b64(AESGCM(key).encrypt(nonce,raw,AAD)),salt=b64(salt),wrap_nonce=b64(wrap_nonce),
        existing_secret_wrap=b64(AESGCM(kek(password,salt)).encrypt(wrap_nonce,key,AAD)),
        recipient_wrap=b64(public.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=AAD))))

def open_plan(envelope,password=None,private_key=None):
    if envelope['contract']!=AAD.decode():raise ValueError('envelope')
    if private_key is not None:
        key=private_key.decrypt(un64(envelope['recipient_wrap']),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=AAD))
    else:key=AESGCM(kek(password,un64(envelope['salt']))).decrypt(un64(envelope['wrap_nonce']),un64(envelope['existing_secret_wrap']),AAD)
    plan=json.loads(AESGCM(key).decrypt(un64(envelope['nonce']),un64(envelope['ciphertext']),AAD))
    if digest(plan)!=envelope['plan_sha256'] or plan['run_id']!=envelope['run_id']:raise ValueError('integrity')
    return plan
