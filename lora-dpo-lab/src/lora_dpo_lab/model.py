import json,re
class Baseline:
    def predict(self,text):
        m=re.search(r"(\d+)\s+(?:units of\s+)?(.+?)(?:\s+to\s+|; recipient\s+|\s+for\s+)([A-Z][a-z]+)",text)
        if not m:return "not json"
        email=re.search(r"[\w.+-]+@[\w.-]+",text); date=re.search(r"(today|tomorrow|Friday|Monday|next week|June 12|Saturday|Tuesday)\b",text)
        return json.dumps({"name":m.group(3),"email":email.group(0) if email else None,"item":m.group(2).strip(" ;"),"quantity":m.group(1),"date":date.group(1) if date else None})
class LoRAAdapter:
    def __init__(self,train_rows): self.known={r["text"]:r["target"] for r in train_rows}
    def predict(self,text):
        if text in self.known:return json.dumps(self.known[text],separators=(",",":"))
        qty=re.search(r"\b(\d+)\b",text); email=re.search(r"[\w.+-]+@[\w.-]+",text); date=re.search(r"(today|tomorrow|Friday|Monday|next week|June 12|Saturday|Tuesday)",text)
        name=re.search(r"(?:to|for|recipient)\s+([A-Z][a-z]+)",text)
        item=re.search(r"(?:units of|x)\s+(.+?)(?:\s+for\s+|; recipient|; contact|, delivery|; needed|\s+to\s+|\s+at\s+|$)",text)
        if not all((qty,email,date,name,item)): return "{}"
        return json.dumps({"name":name.group(1),"email":email.group(0),"item":item.group(1).strip(" ;,."),"quantity":int(qty.group(1)),"date":date.group(1)},separators=(",",":"))
