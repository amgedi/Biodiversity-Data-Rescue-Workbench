"""Handshake before decoding; local Tesseract runs inside the parent's OS limits."""
import json,os,subprocess,sys,time
from pathlib import Path

def run():
    if sys.stdin.buffer.readline()!=b'go\n':return 2
    if os.name!='nt':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024));resource.setrlimit(resource.RLIMIT_CPU,(18,18))
    from ocr_candidates import parse_tsv,MAX_TSV
    source=Path(sys.argv[1]);provider=Path(sys.argv[2]);output=source.parent/'candidate'
    # Input is already byte-bounded by the parent. First image is selected
    # explicitly through the provider's page-number configuration.
    command=[str(provider),str(source),str(output),'-l','eng','-c','tessedit_page_number=0','tsv']
    process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    try:
        start=time.monotonic();path=output.with_suffix('.tsv')
        while process.poll() is None:
            if time.monotonic()-start>16:raise ValueError('OCR_TIMEOUT')
            if path.exists() and path.stat().st_size>MAX_TSV:raise ValueError('OCR_OUTPUT_LIMIT')
            time.sleep(.05)
        if process.returncode or not path.is_file():raise ValueError('OCR_WORKER_FAILED')
        if path.stat().st_size>MAX_TSV:raise ValueError('OCR_OUTPUT_LIMIT')
        result=parse_tsv(path.read_bytes())
        version=subprocess.run([str(provider),'--version'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=2,check=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0).stdout
        if len(version)>4096:raise ValueError('OCR_WORKER_FAILED')
        result['provider']={'id':'tesseract-local-cli','version':version.decode('utf-8',errors='replace').splitlines()[0][:200],'language':'eng','automatic':False,'network':False}
        print(json.dumps(result,ensure_ascii=False));return 0
    except Exception as exc:print(json.dumps({'error':str(exc) if str(exc) in {'OCR_TIMEOUT','OCR_OUTPUT_LIMIT','OCR_OUTPUT_FORMAT','OCR_INPUT_UNSUPPORTED'} else 'OCR_WORKER_FAILED'}));return 1
    finally:
        if process.poll() is None:process.kill();process.wait()

if __name__=='__main__':raise SystemExit(run())
