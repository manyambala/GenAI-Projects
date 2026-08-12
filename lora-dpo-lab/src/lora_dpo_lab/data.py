from __future__ import annotations
import json
from pathlib import Path

TEMPLATES = [
    "Ship {quantity} {item} to {name} at {email} {date}",
    "Please send {quantity} units of {item} for {name} ({email}), delivery {date}.",
    "Order: {quantity} x {item}; recipient {name}; contact {email}; needed {date}.",
]
NAMES = ["Ana","Ravi","Mina","Omar","Lia","Noah","Zoe","Ishan","Emma","Liam","Maya","Arjun","Nora","Leo","Sara","Eli","Ava","Kai","Ivy","Milo"]
ITEMS = ["red mugs","notebooks","blue pens","tea boxes","cotton shirts","glass bottles","desk lamps","green folders","phone chargers","canvas bags","paper clips","wooden trays","coffee beans","whiteboards","USB cables","winter jackets","steel bottles","sticky notes","travel adapters","wireless mice"]
DATES = ["today","tomorrow","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday","next week"]

def _rows():
    rows=[]
    for i in range(1000):
        name=NAMES[i % len(NAMES)]; item=ITEMS[(i // len(NAMES)) % len(ITEMS)]; quantity=(i % 12)+1; date=DATES[(i // 7) % len(DATES)]
        email=f"{name.lower()}{i}@example.com"; rows.append((name,email,item,quantity,date))
    return rows

def build_dataset(out_dir="data"):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True); records=[]
    for i,(name,email,item,quantity,date) in enumerate(_rows()):
        text=TEMPLATES[i%3].format(name=name,email=email,item=item,quantity=quantity,date=date)
        target={"name":name,"email":email,"item":item,"quantity":quantity,"date":date}
        records.append({"id":f"ex-{i:03d}","prompt":text,"text":text,"target":target,"chosen":json.dumps(target,separators=(",",":")),"rejected":json.dumps({**target,"quantity":str(quantity)},separators=(",",":"))})
    splits={"train":records[:800],"validation":records[800:900],"test":records[900:]}
    for name,rows in splits.items(): (out/f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in rows),encoding="utf-8")
    (out/"preferences.jsonl").write_text("\n".join(json.dumps(r) for r in records),encoding="utf-8")
    return splits
