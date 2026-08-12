import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
import streamlit as st
from lora_dpo_lab.data import build_dataset
from lora_dpo_lab.model import LoRAAdapter

st.set_page_config(page_title="LoRA + DPO Lab", page_icon="🧪")
st.title("🧪 LoRA + DPO JSON Extractor")
st.caption("Interactive demonstration of the tuned structured-output adapter")
text = st.text_area("Request", "Ship 3 red mugs to Ana at ana@example.com tomorrow", height=100)
if st.button("Extract JSON", type="primary"):
    model = LoRAAdapter(build_dataset(Path(__file__).parent / "data")["train"])
    st.json(model.predict(text))
st.info("Run `python -m lora_dpo_lab.cli run` to regenerate before/after metrics.")
