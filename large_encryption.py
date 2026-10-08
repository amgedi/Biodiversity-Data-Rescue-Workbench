"""File-backed AES-GCM portability using the existing backup KDF/cipher choices.

One authenticated message, streamed in bounded chunks. Plaintext is never
returned to a parser before authentication succeeds. No passphrase is stored.
"""
import base64,hashlib,json,os,tempfile
MAGIC=b'BiorescueEncryptedLarge/1\n'
MAX=512*1024*1024-4096
def password_key(password,salt):
 if not isinstance(password,str) or not 12<=len(password)<=1024:raise ValueError('LARGE_CRYPTO_PASSWORD')
 try:
  from cryptography.hazmat.primitives import hashes
  from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
 except ImportError:raise ValueError('LARGE_CRYPTO_UNAVAILABLE') from None
 return PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=600000).derive(password.encode('utf-8'))
def encrypt(source,password):
 try:
  from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
 except ImportError:raise ValueError('LARGE_CRYPTO_UNAVAILABLE') from None
 source.seek(0,2);size=source.tell();source.seek(0)
 if not 0<size<=MAX:raise ValueError('LARGE_CRYPTO_LIMIT')
 salt=os.urandom(16);nonce=os.urandom(12);key=password_key(password,salt)
 header={'cipher':'AES-256-GCM','kdf':'PBKDF2-SHA256','iterations':600000,'salt':base64.b64encode(salt).decode(),'nonce':base64.b64encode(nonce).decode(),'plaintextBytes':size};aad=MAGIC+json.dumps(header,sort_keys=True,separators=(',',':')).encode()+b'\n';output=tempfile.TemporaryFile('w+b')
 try:
  output.write(aad);encryptor=Cipher(algorithms.AES(key),modes.GCM(nonce)).encryptor();encryptor.authenticate_additional_data(aad);read=0
  while chunk:=source.read(65536):read+=len(chunk);output.write(encryptor.update(chunk))
  if read!=size:raise ValueError('LARGE_CRYPTO_LIMIT')
  output.write(encryptor.finalize());output.write(encryptor.tag);output.seek(0);return output
 except Exception:output.close();raise
def encrypted(path):
 with path.open('rb') as source:return source.read(len(MAGIC))==MAGIC
def decrypt(path,password):
 try:
  from cryptography.exceptions import InvalidTag
  from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
 except ImportError:raise ValueError('LARGE_CRYPTO_UNAVAILABLE') from None
 output=tempfile.TemporaryFile('w+b')
 try:
  with path.open('rb') as source:
   magic=source.read(len(MAGIC));line=source.readline(4097)
   if magic!=MAGIC or len(line)>4096 or not line.endswith(b'\n'):raise ValueError('LARGE_CRYPTO_FORMAT')
   try:
    header=json.loads(line)
    if not isinstance(header,dict) or set(header)!={'cipher','kdf','iterations','salt','nonce','plaintextBytes'} or header['cipher']!='AES-256-GCM' or header['kdf']!='PBKDF2-SHA256' or type(header['iterations']) is not int or header['iterations']!=600000 or type(header['plaintextBytes']) is not int or not 0<header['plaintextBytes']<=MAX:raise ValueError('LARGE_CRYPTO_FORMAT')
    salt=base64.b64decode(header['salt'],validate=True);nonce=base64.b64decode(header['nonce'],validate=True)
    if len(salt)!=16 or len(nonce)!=12:raise ValueError('LARGE_CRYPTO_FORMAT')
   except (KeyError,TypeError,json.JSONDecodeError,ValueError):raise ValueError('LARGE_CRYPTO_FORMAT') from None
   start=source.tell();size=path.stat().st_size
   if size!=start+header['plaintextBytes']+16:raise ValueError('LARGE_CRYPTO_FORMAT')
   source.seek(-16,2);tag=source.read(16);source.seek(start);decryptor=Cipher(algorithms.AES(password_key(password,salt)),modes.GCM(nonce,tag)).decryptor();decryptor.authenticate_additional_data(magic+line);remaining=header['plaintextBytes']
   while remaining:
    chunk=source.read(min(65536,remaining))
    if not chunk:raise ValueError('LARGE_CRYPTO_FORMAT')
    output.write(decryptor.update(chunk));remaining-=len(chunk)
   output.write(decryptor.finalize());output.seek(0)
   return output,{'cipher':header['cipher'],'kdf':header['kdf'],'iterations':header['iterations'],'authenticated':True,'policy':'Authenticated before archive parsing; passphrase not retained.'}
 except InvalidTag:output.close();raise ValueError('LARGE_CRYPTO_AUTHENTICATION') from None
 except Exception:output.close();raise
def export_package(store,payload):
 if payload.get('parentId'):
  from large_relationships import package
  source=package(store,payload)
 else:
  from large_preservation import package
  source=package(store,payload['id'])
 with source:return encrypt(source,payload.get('password'))
