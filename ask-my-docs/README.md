# 🚀 Ask My Docs: Enterprise Hybrid RAG

A production-grade, domain-specific Retrieval-Augmented Generation (RAG) system with hybrid retrieval and strict citation enforcement.

## 🏗️ Architecture
The system uses a hybrid approach combining BM25 keyword search and dense vector embeddings, followed by a cross-encoder reranking step to retrieve the most relevant document chunks. The LLM then generates an answer using only the provided context, enforcing strict citations for every factual claim.

## ✨ Features
- [x] **Hybrid Retrieval**: Combines sparse (BM25) and dense (Vector) retrieval for optimal recall.
- [x] **Cross-Encoder Reranking**: Re-scores retrieved chunks for higher precision.
- [x] **Strict Citations**: Enforces verifiable citations linked to source chunks.
- [x] **Automated Evaluation Gate**: CI/CD pipeline blocking PRs if retrieval metrics degrade.
- [x] **Multi-format parsing**: Supports PDF, DOCX, Markdown, and HTML ingestion.

## 🚀 Quick Start

### Prerequisites
- Python >= 3.11
- OpenAI API Key

### Installation
```bash
# Clone the repository
git clone https://github.com/your-org/ask-my-docs.git
cd ask-my-docs

# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration
Copy the `.env.example` to `.env` and configure your API keys:
```bash
cp .env.example .env
```

### Ingestion
Ingest the sample documents:
```bash
python scripts/ingest.py --docs-dir ./docs
```

### Run API
Start the FastAPI server:
```bash
uvicorn src.server:app --reload
```

## 📊 Evaluation
Run the automated evaluation suite locally:
```bash
python scripts/evaluate.py
```

## 🛠️ Tech Stack
The evaluation gate requires `OPENAI_API_KEY`; it fails rather than silently evaluating a fallback response. It measures source-level Recall@5 and MRR on the reranked top five chunks, plus citation ID validity and sentence-level citation coverage.

For production, set `ALLOWED_ORIGINS` to the comma-separated browser origins that may call the API. `/api/ingest` accepts directories only under `ALLOWED_DOCS_ROOT` (default: `docs`) to prevent arbitrary server-file ingestion.

Citation validation rejects uncited factual sentences or invalid citation IDs and returns an abstention when validation fails. It is a provenance/coverage guard; add domain-specific human or NLI judgments to the golden dataset for semantic-entailment evaluation.

| Component | Technology |
| --- | --- |
| Web Framework | FastAPI |
| Embeddings | sentence-transformers |
| Vector Store | FAISS |
| Sparse Search | rank-bm25 |
| LLM | OpenAI (gpt-4o-mini) |
| Testing | pytest |

## 📁 Project Structure
```
ask-my-docs/
├── docs/                # Sample documentation files
├── src/                 # Source code
│   ├── pipeline.py
│   ├── citation_engine.py
│   ├── chunker.py
│   ├── hybrid_retriever.py
│   └── config.py
├── tests/               # Test suite and golden dataset
├── scripts/             # Utility scripts (ingest, evaluate)
├── .github/workflows/   # CI/CD pipelines
├── requirements.txt
├── .env.example
├── pyproject.toml
└── README.md
```

## 🤝 Contributing
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Ensure tests and evaluation script pass
5. Push to the branch
6. Open a Pull Request

## 📄 License
MIT License
