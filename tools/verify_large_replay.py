"""Verify a preservation package by replaying its original, without restoration."""
import argparse,json,sys
from pathlib import Path
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from large_restore import Recovery
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('package',type=Path);args=parser.parse_args()
 try:
  with closing(Recovery(args.package)) as recovery:print(json.dumps({'verified':True,**recovery.report},ensure_ascii=False,indent=2))
 except (ValueError,OSError,KeyError,TypeError) as error:print(json.dumps({'verified':False,'error':str(error)}));raise SystemExit(1)
