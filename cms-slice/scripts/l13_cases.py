"""Run independent expected synthetic examples; no production consumers."""
from datetime import date
import json,re
from pathlib import Path
import l13_synthetic as math
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/data/l13-enrollment-2026-10-28'
def encode(x):
    if isinstance(x,date):return x.isoformat()
    if isinstance(x,(list,tuple)):return [encode(v) for v in x]
    if isinstance(x,dict):return {k:encode(v) for k,v in x.items()}
    return x
def run_cases():
    results=[]
    for c in json.loads((BASE/'synthetic-cases.json').read_text()):
        args=[date.fromisoformat(x) if isinstance(x,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',x) else x for x in c['args']]
        try:actual=encode(getattr(math,c['function'])(*args,**c.get('kwargs',{})));error=None
        except ValueError:actual=None;error='ValueError'
        passed=(error==c['expected_error']) if 'expected_error' in c else error is None and actual==c['expected']
        results.append(dict(id=c['id'],basis=c['basis'],passed=passed,expected=c.get('expected'),expected_error=c.get('expected_error'),actual=actual,error=error))
    return results
if __name__=='__main__':
    rows=run_cases();print(json.dumps({'cases':len(rows),'passed':sum(r['passed'] for r in rows),'failures':[r for r in rows if not r['passed']]},indent=2))
    if not all(r['passed'] for r in rows):raise SystemExit(1)
