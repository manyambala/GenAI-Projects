import json
from lora_dpo_lab.data import build_dataset
from lora_dpo_lab.metrics import evaluate
from lora_dpo_lab.model import LoRAAdapter
def test_adapter_exact_on_training_examples(tmp_path):
    s=build_dataset(tmp_path); rows=[{**r,"prediction":LoRAAdapter(s["train"]).predict(r["text"])} for r in s["train"]]; assert evaluate(rows)["exact_match"]==1.0
def test_targets_are_valid_json(tmp_path): assert all(isinstance(json.loads(r["chosen"]),dict) for r in build_dataset(tmp_path)["train"])
