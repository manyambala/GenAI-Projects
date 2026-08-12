"""Real Transformers/PEFT pipeline for small CPU LoRA and optional DPO."""
import json
import re
from pathlib import Path
from .data import build_dataset
from .metrics import evaluate
from .schema import validate_output

def _imports():
    try:
        import torch
        from datasets import Dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, set_seed
        from peft import LoraConfig, PeftModel
        from trl import SFTTrainer, DPOTrainer
        return torch, Dataset, AutoModelForCausalLM, AutoTokenizer, TrainingArguments, set_seed, LoraConfig, PeftModel, SFTTrainer, DPOTrainer
    except ImportError as e:
        raise SystemExit("Install requirements-real.txt first: " + str(e))

def _rows(root):
    return build_dataset(Path(root)/"data")

def _prompt(text):
    return f"System: Return only valid JSON with name, email, item, quantity, date.\nUser: {text}\nAssistant:"

def _extract_json(text):
    match=re.search(r"\{.*?\}",text,re.DOTALL)
    return match.group(0) if match else text.strip()

def stage1(model_name):
    _,_,AutoModel,Tok,*_= _imports(); tok=Tok.from_pretrained(model_name); model=AutoModel.from_pretrained(model_name)
    print(f"Loaded {model_name}: {sum(p.numel() for p in model.parameters()):,} parameters; tokenizer vocab={len(tok):,}")

def stage2(root):
    from .quality import audit_dataset
    result=audit_dataset(Path(root)/"data"); print(json.dumps(result,indent=2)); return result

def train_cpu(model_name, root):
    torch,Dataset,AutoModel,Tok,TrainingArgs,set_seed,LoraConfig,_,SFTTrainer,_=_imports(); set_seed(42)
    root=Path(root); splits=_rows(root); tok=Tok.from_pretrained(model_name); tok.pad_token=tok.eos_token
    train=Dataset.from_list([{"prompt":_prompt(r["text"]),"completion":r["chosen"]} for r in splits["train"]]); valid=Dataset.from_list([{"prompt":_prompt(r["text"]),"completion":r["chosen"]} for r in splits["validation"]])
    model=AutoModel.from_pretrained(model_name); lora=LoraConfig(r=8,lora_alpha=16,lora_dropout=.05,target_modules=["q_proj","k_proj","v_proj","o_proj"],task_type="CAUSAL_LM")
    args=TrainingArgs(output_dir=str(root/"models/cpu-sft"),num_train_epochs=1,per_device_train_batch_size=1,gradient_accumulation_steps=4,learning_rate=2e-4,logging_steps=1,save_strategy="epoch",report_to="none",use_cpu=True)
    trainer=SFTTrainer(model=model,args=args,train_dataset=train,eval_dataset=valid,processing_class=tok,peft_config=lora); trainer.train(); trainer.save_model(str(root/"models/cpu-sft")); tok.save_pretrained(str(root/"models/cpu-sft")); print("Saved real CPU LoRA adapter to models/cpu-sft")

def evaluate_adapter(adapter, model_name, root):
    adapter_path=Path(adapter)
    if not adapter_path.exists() or not (adapter_path/"adapter_config.json").exists():
        raise SystemExit(f"Adapter not found or incomplete: {adapter_path}. Run the training command successfully before evaluating it.")
    torch,_,AutoModel,Tok,_,_,_,PeftModel,*_=_imports(); root=Path(root); s=_rows(root); tok=Tok.from_pretrained(model_name); base=AutoModel.from_pretrained(model_name); model=PeftModel.from_pretrained(base,str(adapter_path)).eval()
    rows=[]
    for r in s["test"]:
        prompt=_prompt(r["text"])
        inputs=tok(prompt,return_tensors="pt"); out=model.generate(**inputs,max_new_tokens=100,do_sample=False,pad_token_id=tok.eos_token_id); text=_extract_json(tok.decode(out[0][inputs["input_ids"].shape[1]:],skip_special_tokens=True)); rows.append({**r,"prediction":text})
    art=root/"artifacts"; art.mkdir(exist_ok=True)
    stage=adapter_path.name
    metrics=evaluate(rows)
    predictions_text="\n".join(json.dumps(r) for r in rows)
    (art/"model-predictions.jsonl").write_text(predictions_text,encoding="utf-8")
    (art/f"predictions-{stage}.jsonl").write_text(predictions_text,encoding="utf-8")
    (art/f"metrics-{stage}.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8")
    print(json.dumps(metrics,indent=2)); return rows

def failures(predictions, root):
    rows=[json.loads(x) for x in Path(predictions).read_text(encoding="utf-8").splitlines() if x.strip()]; bad=[]
    for r in rows:
        ok,errors=validate_output(r["prediction"])
        try: exact=json.loads(r["prediction"]) == r["target"]
        except json.JSONDecodeError: exact=False
        if not ok or not exact: bad.append({"id":r["id"],"input":r["text"],"prediction":r["prediction"],"target":r["target"],"errors":errors})
    out=Path(root)/"artifacts/failures.jsonl"; out.write_text("\n".join(json.dumps(x) for x in bad),encoding="utf-8"); print(f"Found {len(bad)} failures; wrote {out}")

def dpo_cpu(sft_adapter, model_name, root):
    _,Dataset,AutoModel,Tok,_,set_seed,_,PeftModel,_,DPOTrainer=_imports(); from trl import DPOConfig; set_seed(42); root=Path(root); s=_rows(root); tok=Tok.from_pretrained(model_name); tok.pad_token=tok.eos_token
    model=PeftModel.from_pretrained(AutoModel.from_pretrained(model_name),sft_adapter,is_trainable=True)
    model.gradient_checkpointing_disable()
    model.config.use_cache=True
    args=DPOConfig(output_dir=str(root/"models/cpu-dpo"),num_train_epochs=1,per_device_train_batch_size=1,gradient_accumulation_steps=4,learning_rate=5e-5,logging_steps=1,report_to="none",use_cpu=True,beta=.1,gradient_checkpointing=False)
    preferences=Dataset.from_list([{"prompt":_prompt(r["text"]),"chosen":r["chosen"],"rejected":r["rejected"]} for r in s["train"]])
    dpo=DPOTrainer(model=model,ref_model=None,args=args,train_dataset=preferences,processing_class=tok); dpo.train(); dpo.save_model(str(root/"models/cpu-dpo")); tok.save_pretrained(str(root/"models/cpu-dpo")); print("Saved real CPU DPO adapter to models/cpu-dpo")
