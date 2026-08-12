import hashlib, json
from pathlib import Path
from .schema import validate_output

def stable_split(text: str) -> str:
    bucket=int(hashlib.sha256(text.encode()).hexdigest()[:8],16)%100
    return "test" if bucket < 15 else "validation" if bucket < 25 else "train"

def audit_dataset(root="data"):
    root=Path(root); seen=set(); report={"duplicates":[],"invalid_targets":[],"counts":{}}
    for path in [root/"train.jsonl",root/"validation.jsonl",root/"test.jsonl"]:
        if not path.exists(): continue
        rows=[json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        report["counts"][path.name]=len(rows)
        for row in rows:
            if row.get("text") in seen: report["duplicates"].append(row.get("id"))
            seen.add(row.get("text")); ok,errors=validate_output(row.get("target"));
            if not ok: report["invalid_targets"].append({"id":row.get("id"),"errors":errors})
    report["passed"]=not report["duplicates"] and not report["invalid_targets"]
    return report
