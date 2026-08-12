"""Production-oriented QLoRA SFT followed by DPO. Execute on CUDA, not CPU."""
import json, random
from pathlib import Path

def train_real(model_name, root, config_path=None):
    try:
        import torch
        from datasets import load_dataset
        from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                                  TrainingArguments, set_seed)
        from peft import LoraConfig
        from trl import SFTTrainer, DPOTrainer
    except ImportError as exc:
        raise SystemExit("Install optional stack: torch transformers datasets peft trl bitsandbytes. "+str(exc))
    if not torch.cuda.is_available():
        raise SystemExit("Real QLoRA training requires CUDA. The CPU evaluation path remains available with: python -m lora_dpo_lab.cli run")
    root=Path(root); cfg=json.loads(Path(config_path).read_text()) if config_path else json.loads((root/"configs/default.json").read_text())
    set_seed(cfg["seed"]); random.seed(cfg["seed"])
    ds=load_dataset("json",data_files={"train":str(root/"data/train.jsonl"),"validation":str(root/"data/validation.jsonl")})
    prefs=load_dataset("json",data_files=str(root/"data/preferences.jsonl"),split="train")
    tok=AutoTokenizer.from_pretrained(model_name,use_fast=True); tok.pad_token=tok.eos_token; tok.padding_side="right"
    quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type="nf4",bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
    model=AutoModelForCausalLM.from_pretrained(model_name,quantization_config=quant,device_map="auto",torch_dtype=torch.bfloat16)
    lora=LoraConfig(r=cfg["lora_r"],lora_alpha=cfg["lora_alpha"],lora_dropout=cfg["lora_dropout"],target_modules=["q_proj","k_proj","v_proj","o_proj"],task_type="CAUSAL_LM")
    out=root/cfg["output_dir"]; sft_args=TrainingArguments(output_dir=str(out/"sft"),num_train_epochs=cfg["sft_epochs"],per_device_train_batch_size=2,gradient_accumulation_steps=8,learning_rate=cfg["learning_rate"],bf16=True,gradient_checkpointing=True,logging_steps=5,eval_strategy="epoch",save_strategy="epoch",load_best_model_at_end=True,metric_for_best_model="eval_loss",report_to="none",warmup_ratio=.05)
    def format_row(row): return f"System: Return only JSON matching name, email, item, quantity, date.\nUser: {row['text']}\nAssistant: {row['chosen']}"
    trainer=SFTTrainer(model=model,args=sft_args,train_dataset=ds["train"],eval_dataset=ds["validation"],processing_class=tok,formatting_func=format_row,peft_config=lora,max_seq_length=cfg["max_seq_length"])
    trainer.train(); trainer.save_model(str(out/"sft-final")); tok.save_pretrained(str(out/"sft-final"))
    dpo_args=TrainingArguments(output_dir=str(out/"dpo"),num_train_epochs=cfg["dpo_epochs"],per_device_train_batch_size=2,gradient_accumulation_steps=8,learning_rate=cfg["learning_rate"]/2,bf16=True,logging_steps=5,save_strategy="epoch",report_to="none")
    dpo=DPOTrainer(model=trainer.model,ref_model=None,args=dpo_args,train_dataset=prefs,processing_class=tok,beta=.1,max_length=cfg["max_seq_length"])
    dpo.train(); dpo.save_model(str(out/"dpo-final")); tok.save_pretrained(str(out/"dpo-final")); print(f"Saved production adapters under {out}")
