import json
from typing import Any

REQUIRED = {"name": str, "email": str, "item": str, "quantity": int, "date": str}

def validate_output(value: Any) -> tuple[bool, list[str]]:
    if isinstance(value, str):
        try: value = json.loads(value)
        except json.JSONDecodeError: return False, ["invalid_json"]
    if not isinstance(value, dict): return False, ["not_object"]
    errors=[]
    for key, kind in REQUIRED.items():
        if key not in value: errors.append(f"missing:{key}")
        elif type(value[key]) is not kind: errors.append(f"type:{key}")
    extra=set(value)-set(REQUIRED)
    errors.extend(f"extra:{k}" for k in sorted(extra))
    return not errors, errors

def canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
