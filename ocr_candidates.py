"""Optional local OCR; candidates only, never a scientific project mutation."""
import csv,hashlib,io,json,os,shutil,subprocess,tempfile,threading
from pathlib import Path
from rescue import source_bytes
from worker_runtime import worker_command
from pdf_limits import WindowsJob
MAX_IMAGE=10*1024*1024
MAX_TSV=1024*1024
_slots=threading.BoundedSemaphore(1)

def provider_path():
    configured=os.environ.get('WORKBENCH_TESSERACT')
    candidates=[configured] if configured else [shutil.which('tesseract'),r'C:\Program Files\Tesseract-OCR\tesseract.exe',r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']
    return next((Path(p).resolve() for p in candidates if p and Path(p).is_file()),None)

def capability():
    path=provider_path()
    return {'provider':'Tesseract local CLI','available':bool(path),'installedByWorkbench':False,'network':False,'inputs':['PNG','JPEG','TIFF first image'],'scannedPdfRendering':False,'automatic':False,'maximumInputBytes':MAX_IMAGE,'maximumWords':2000,'maximumSeconds':20,'scientificConfirmation':False,'missingReason':None if path else 'No local Tesseract executable found. Original images remain preserved; OCR is optional and no provider is installed automatically.'}

def parse_tsv(raw):
    if len(raw)>MAX_TSV:raise ValueError('OCR_OUTPUT_LIMIT')
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8'),newline=''),delimiter='\t')
    required={'level','page_num','block_num','par_num','line_num','word_num','left','top','width','height','conf','text'}
    if not reader.fieldnames or set(reader.fieldnames)!=required or len(reader.fieldnames)!=len(required):raise ValueError('OCR_OUTPUT_FORMAT')
    words=[];characters=0;omitted=0
    for record in reader:
        if None in record or any(v is None for v in record.values()):raise ValueError('OCR_OUTPUT_FORMAT')
        if record['page_num']!='1':raise ValueError('OCR_INPUT_UNSUPPORTED')
        if record['level']!='5':continue
        text=record['text']
        if not text:continue
        try:
            confidence=float(record['conf']);box=[int(record[k]) for k in ['left','top','width','height']];page=int(record['page_num']);line=[int(record[k]) for k in ['block_num','par_num','line_num','word_num']]
        except (ValueError,OverflowError):raise ValueError('OCR_OUTPUT_FORMAT') from None
        if not 0<=confidence<=100 or any(v<0 or v>10000000 for v in box) or page<1 or page>10000 or any(v<0 or v>10000000 for v in line):raise ValueError('OCR_OUTPUT_FORMAT')
        if len(text)>2000 or len(words)>=2000 or characters+len(text)>100000:omitted+=1;continue
        words.append({'text':text,'providerConfidence':confidence,'boxPixels':box,'providerPage':page,'providerLocation':line,'status':'Candidate','scientificConfirmation':False});characters+=len(text)
    return {'words':words,'omittedWords':omitted,'bounded':True,'confidenceMeaning':'Raw provider word score, not a calibrated scientific confidence or field review status.'}

def preview(resource,opt_in=False):
    if opt_in is not True:raise ValueError('OCR_OPT_IN_REQUIRED')
    raw=source_bytes(resource)
    if hashlib.sha256(raw).hexdigest()!=resource.get('sha256'):raise ValueError('OCR_SOURCE_INTEGRITY')
    if not 0<len(raw)<=MAX_IMAGE:raise ValueError('OCR_INPUT_LIMIT')
    if not raw.startswith((b'\x89PNG\r\n\x1a\n',b'\xff\xd8\xff',b'II*\x00',b'MM\x00*')):raise ValueError('OCR_INPUT_UNSUPPORTED')
    provider=provider_path()
    if not provider:raise ValueError('OCR_PROVIDER_UNAVAILABLE')
    if not _slots.acquire(blocking=False):raise ValueError('OCR_BUSY')
    process=job=None
    try:
        with tempfile.TemporaryDirectory(prefix='biorescue-ocr-') as folder:
            path=Path(folder)/'original.image';path.write_bytes(raw)
            process=subprocess.Popen(worker_command('ocr_worker',path)+[str(provider)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            if os.name=='nt':
                try:job=WindowsJob(process,memory=512*1024*1024,active=2,job_memory=True)
                except OSError:process.kill();process.communicate();raise ValueError('OCR_LIMIT_UNAVAILABLE') from None
            try:output,_=process.communicate(input=b'go\n',timeout=20)
            except subprocess.TimeoutExpired:process.kill();process.communicate();raise ValueError('OCR_TIMEOUT') from None
            if len(output)>MAX_TSV:raise ValueError('OCR_WORKER_FAILED')
            result=json.loads(output)
            if not isinstance(result,dict) or result.get('error'):raise ValueError(result.get('error','OCR_WORKER_FAILED') if isinstance(result,dict) else 'OCR_WORKER_FAILED')
            if process.returncode:raise ValueError('OCR_WORKER_FAILED')
            return {**result,'sourceId':resource['id'],'sourceSha256':resource['sha256'],'sourceBytes':len(raw),'imageReference':1,'at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'scientificConfirmation':False,'storedInProject':False,'policy':'Read-only optional candidate preview. First image only; TIFF additional frames and scanned PDFs are not processed. No meaning, name, date, unit or location is confirmed. Record reviewed evidence separately with an exact locator.'}
    finally:
        if process and process.poll() is None:process.kill();process.communicate()
        if job:job.close()
        _slots.release()
