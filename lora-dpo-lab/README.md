# LoRA + DPO Lab

End-to-end, reproducible structured JSON extraction fine-tuning lab. It includes synthetic data, a CPU-friendly baseline and LoRA-style adapter, DPO preference scoring, before/after metrics, tests, and an optional real QLoRA + TRL training path.

## Quickstart

```powershell
cd "C:\Users\Lenovo\Documents\AI Projects\lora-dpo-lab"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python -m lora_dpo_lab.cli run
python -m lora_dpo_lab.cli predict --text "Ship 3 red mugs to Ana at ana@example.com tomorrow"
```

The run writes `artifacts/metrics.json`, `artifacts/predictions.jsonl`, and `artifacts/report.md`. The metrics use exact JSON match, field accuracy, JSON validity, and chosen-preference rate.

The built-in generator now creates 1,000 unique examples: 800 train, 100 validation, and 100 test. Replace these synthetic examples with reviewed production data before making deployment claims.

## Real CPU learning path

For a small local model, install `requirements-real.txt`, then follow [STAGES.md](STAGES.md). Use `HuggingFaceTB/SmolLM2-135M-Instruct`; this runs standard LoRA/SFT on CPU and is expected to take substantially longer than the deterministic demo. The generated model predictions are saved before failure analysis. DPO is optional and slower.

## Real QLoRA + DPO

On a CUDA machine, install the commented training dependencies, set a small instruct model, and run `python -m lora_dpo_lab.cli train-real --model Qwen/Qwen2.5-0.5B-Instruct`. The optional path uses 4-bit NF4 loading, LoRA adapters for SFT, then TRL DPO.

## Layout

`data/` generated JSONL; `src/lora_dpo_lab/` pipeline code; `tests/` regression tests; `artifacts/` reports.
