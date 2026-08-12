# Eight-stage learning path

Run from the project root in PowerShell:

```powershell
$env:PYTHONPATH="$PWD\src"
```

1. **Pretrained model** — `python -m lora_dpo_lab.cli stage1 --model HuggingFaceTB/SmolLM2-135M-Instruct`
2. **Dataset** — `python -m lora_dpo_lab.cli stage2`
3. **Real CPU LoRA SFT** — `python -m lora_dpo_lab.cli train-cpu --model HuggingFaceTB/SmolLM2-135M-Instruct`
4. **Metrics** — `python -m lora_dpo_lab.cli evaluate --adapter models/cpu-sft`
5. **DPO** — `python -m lora_dpo_lab.cli dpo-cpu --sft-adapter models/cpu-sft`
6. **Failure analysis** — `python -m lora_dpo_lab.cli failures --predictions artifacts/model-predictions.jsonl`
7. **Deploy** — `streamlit run app.py`
8. **Document** — inspect `artifacts/report.md`, `artifacts/failures.jsonl`, and `artifacts/metrics.json`.

The generated dataset contains 1,000 unique examples: 800 train, 100 validation, and 100 test. The CPU stages use standard LoRA, not 4-bit QLoRA. QLoRA/DPO with larger models remains available through `train-real` on a CUDA machine.
