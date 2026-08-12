import json
from .schema import validate_output
FIELDS=["name","email","item","quantity","date"]
def parse(value):
    try: return json.loads(value) if isinstance(value,str) else value
    except (TypeError,json.JSONDecodeError): return None
def evaluate(rows):
    n=len(rows); valid=exact=hits=pref=0
    for r in rows:
        p=parse(r["prediction"]); t=r["target"]; valid+=validate_output(p)[0]; exact+=p==t; hits+=sum(isinstance(p,dict) and p.get(k)==t[k] for k in FIELDS); pref+=int(p==parse(r.get("chosen","{}")))
    return {"examples":n,"json_validity":round(valid/n,4),"exact_match":round(exact/n,4),"field_accuracy":round(hits/(n*len(FIELDS)),4),"chosen_preference_rate":round(pref/n,4)}
