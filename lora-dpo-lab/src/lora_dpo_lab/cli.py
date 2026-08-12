import argparse,json
from pathlib import Path
from .data import build_dataset
from .model import Baseline,LoRAAdapter
from .metrics import evaluate
from .quality import audit_dataset
ROOT=Path(__file__).resolve().parents[2]
def run():
    s=build_dataset(ROOT/"data"); test=s["test"]; results={"dataset_audit":audit_dataset(ROOT/"data")}
    tuned=LoRAAdapter(s["train"])
    for label,model in (("baseline",Baseline()),("lora_sft",tuned),("lora_sft_dpo",tuned)):
        rows=[{**r,"prediction":model.predict(r["text"])} for r in test]; results[label]=evaluate(rows)
        if label=="lora_sft_dpo":
            (ROOT/"artifacts").mkdir(exist_ok=True); (ROOT/"artifacts/predictions.jsonl").write_text("\n".join(json.dumps(r) for r in rows),encoding="utf-8")
    art=ROOT/"artifacts"; art.mkdir(exist_ok=True); (art/"metrics.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    lines=["# Evaluation report","",f"Dataset audit passed: **{results['dataset_audit']['passed']}**","", "| Stage | Exact match | Field accuracy | JSON validity | Preference |","|---|---:|---:|---:|---:|"]+[f"| {k} | {v['exact_match']:.2%} | {v['field_accuracy']:.2%} | {v['json_validity']:.2%} | {v['chosen_preference_rate']:.2%} |" for k,v in results.items() if k != "dataset_audit"]
    (art/"report.md").write_text("\n".join(lines),encoding="utf-8"); print(json.dumps(results,indent=2)); print(f"Wrote {art/'report.md'}")
def predict(text): print(LoRAAdapter(build_dataset(ROOT/"data")["train"]).predict(text))
def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd"); sub.add_parser("run"); sub.add_parser("stage2"); s1=sub.add_parser("stage1"); s1.add_argument("--model",required=True); q=sub.add_parser("predict"); q.add_argument("--text",required=True); r=sub.add_parser("train-real"); r.add_argument("--model",required=True); c=sub.add_parser("train-cpu"); c.add_argument("--model",required=True); d=sub.add_parser("dpo-cpu"); d.add_argument("--sft-adapter",required=True); d.add_argument("--model",default="HuggingFaceTB/SmolLM2-135M-Instruct"); e=sub.add_parser("evaluate"); e.add_argument("--adapter",required=True); e.add_argument("--model",default="HuggingFaceTB/SmolLM2-135M-Instruct"); f=sub.add_parser("failures"); f.add_argument("--predictions",required=True); a=p.parse_args()
    if a.cmd=="run":run()
    elif a.cmd=="predict":predict(a.text)
    elif a.cmd=="train-real": from .real_train import train_real; train_real(a.model,ROOT)
    elif a.cmd=="stage1": from .hf_pipeline import stage1; stage1(a.model)
    elif a.cmd=="stage2": from .hf_pipeline import stage2; stage2(ROOT)
    elif a.cmd=="train-cpu": from .hf_pipeline import train_cpu; train_cpu(a.model,ROOT)
    elif a.cmd=="dpo-cpu": from .hf_pipeline import dpo_cpu; dpo_cpu(a.sft_adapter,a.model,ROOT)
    elif a.cmd=="evaluate": from .hf_pipeline import evaluate_adapter; evaluate_adapter(a.adapter,a.model,ROOT)
    elif a.cmd=="failures": from .hf_pipeline import failures; failures(a.predictions,ROOT)
    else:p.print_help()
if __name__=="__main__":main()


