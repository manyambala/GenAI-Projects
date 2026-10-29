# Ask My Docs — Complete Project Guide

This document explains the complete **Ask My Docs** project: its purpose, every important file, document ingestion, hybrid retrieval, FAISS vector storage, BM25 search, reranking, Groq generation, citation enforcement, the web interface, testing, and CI evaluation.

It is written so the project can be understood without reading every source file first.

---

## 1. What the project does

Ask My Docs is a domain-specific Retrieval-Augmented Generation (RAG) application. A user asks a question, and the application searches only the indexed documents before generating an answer.

The application does **not** train Groq on the documents. It retrieves relevant document chunks at question time and sends only those chunks to Groq as context.

At a high level:

```text
Documents → chunks → search indexes

Question → retrieve chunks → rerank chunks → Groq answer → citation validation → UI
```

The current sample knowledge base contains FastAPI, Kubernetes, and information-security documents.

---

## 2. Main technologies

| Requirement | Implementation |
|---|---|
| Backend API | FastAPI |
| Server | Uvicorn |
| Keyword retrieval | BM25 using `rank-bm25` |
| Semantic retrieval | Sentence Transformers + FAISS |
| Vector database | Local FAISS index |
| Hybrid fusion | Reciprocal Rank Fusion (RRF) |
| Reranking | Cross-encoder |
| Answer generation | Groq, OpenAI, or xAI-compatible API |
| Citation enforcement | Custom citation engine |
| Frontend | HTML, CSS, and JavaScript |
| Tests | pytest |
| CI evaluation | GitHub Actions |

FAISS is the vector database in this project. It is embedded in the Python application, so no separate Pinecone, Qdrant, Weaviate, or Milvus server is required.

---

## 3. Project structure

```text
ask-my-docs/
├── .github/workflows/eval-gate.yml
├── data/
│   ├── bm25_index.pkl
│   └── vector_store/
│       ├── chunks.pkl
│       └── faiss.index
├── docs/
│   ├── sample_fastapi.md
│   ├── sample_kubernetes.md
│   └── sample_security.md
├── scripts/
│   ├── evaluate.py
│   └── ingest.py
├── src/
│   ├── __init__.py
│   ├── bm25_index.py
│   ├── chunker.py
│   ├── citation_engine.py
│   ├── config.py
│   ├── embeddings.py
│   ├── generator.py
│   ├── hybrid_retriever.py
│   ├── pipeline.py
│   ├── reranker.py
│   ├── server.py
│   └── vector_store.py
├── static/
│   ├── app.js
│   ├── index.html
│   └── style.css
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── golden_dataset.json
│   ├── test_citation_validation.py
│   ├── test_citations.py
│   ├── test_generator_fallback.py
│   ├── test_out_of_domain.py
│   ├── test_pipeline.py
│   ├── test_pipeline_enforcement.py
│   └── test_retrieval.py
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── requirements.txt
```

---

## 4. Root configuration files

### `.env`

This is the private runtime configuration. It contains the real provider key and settings used on the current computer.

Typical Groq configuration:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_private_key
GROQ_MODEL=llama-3.3-70b-versatile
```

Never upload, commit, or share this file. If a key is exposed, revoke it and create a new one.

### `.env.example`

This is the safe configuration template. It lists the supported variables without containing a real secret. It can be shared with other developers.

Important settings:

| Setting | Purpose |
|---|---|
| `LLM_PROVIDER` | Selects `groq`, `openai`, or `xai` |
| `GROQ_API_KEY` | Groq authentication key |
| `GROQ_MODEL` | Groq generation model |
| `EMBEDDING_MODEL` | Local model used to create vectors |
| `RERANKER_MODEL` | Cross-encoder used to rerank chunks |
| `CHUNK_SIZE` | Maximum chunk length in characters |
| `CHUNK_OVERLAP` | Repeated characters between chunks |
| `BM25_TOP_K` | Maximum keyword-search candidates |
| `VECTOR_TOP_K` | Maximum vector-search candidates |
| `FUSION_TOP_K` | Maximum results kept after RRF |
| `RRF_K` | RRF ranking constant |
| `RERANK_TOP_K` | Final chunks retained after reranking |
| `DATA_DIR` | Saved index directory |
| `DOCS_DIR` | Default document directory |
| `ALLOWED_DOCS_ROOT` | Restricts server-side ingestion paths |
| `ALLOWED_ORIGINS` | Permitted browser origins for CORS |

### `.gitignore`

Prevents private or generated content from entering Git. It ignores `.env`, virtual environments, caches, generated indexes, evaluation output, and compiled Python files.

### `requirements.txt`

Lists the required Python libraries:

- `fastapi` and `uvicorn` for the web server.
- `sentence-transformers` for embeddings and cross-encoder reranking.
- `faiss-cpu` for vector storage and search.
- `rank-bm25` for keyword retrieval.
- `PyMuPDF`, `python-docx`, and `beautifulsoup4` for document parsing.
- `openai` and `httpx` for OpenAI-compatible provider calls.
- `pydantic` and `pydantic-settings` for validation and configuration.
- `pytest` and `pytest-asyncio` for testing.

### `pyproject.toml`

Defines project metadata, the minimum Python version, package dependencies, the build system, optional development dependencies, and pytest settings.

### `README.md`

Provides the shorter quick-start documentation: installation, configuration, ingestion, server startup, evaluation, and project features.

### `PROJECT_GUIDE.md`

This file. It is the detailed architecture and file-by-file explanation intended for reading and sharing.

---

## 5. Source documents

### `docs/sample_fastapi.md`

Contains the FastAPI knowledge used to answer questions about API creation, dependencies, authentication, testing, background tasks, and other FastAPI topics.

### `docs/sample_kubernetes.md`

Contains Kubernetes knowledge such as Pods, Deployments, Services, storage, autoscaling, and deployment strategies.

### `docs/sample_security.md`

Contains information-security policies such as least privilege, employee responsibilities, access control, and incident response.

These files are the current knowledge base. Adding a file does not automatically update the indexes; ingestion must be run again.

Supported source formats are PDF, DOCX, HTML, CSV, Markdown, and plain text.

---

## 6. Source-code files

### `src/__init__.py`

Marks `src` as a Python package so modules can be imported with statements such as:

```python
from src.pipeline import RAGPipeline
```

### `src/config.py`

Defines the `Settings` class and reads `.env` from the project root. Every component receives consistent configuration through this class.

It contains provider settings, retrieval limits, model names, directory paths, CORS settings, and reserved observability/cost settings.

The current pipeline does not yet write `OBSERVABILITY_TRACE_PATH` or calculate the configured token costs; those variables are placeholders for a future observability feature.

### `src/chunker.py`

Reads files and breaks their text into overlapping `Chunk` objects.

Each chunk stores:

- Stable `chunk_id`
- `doc_id`
- Chunk text
- Source filename
- PDF page number when available
- Chunk position
- Character start and end offsets
- Metadata

The default values are 512 characters per chunk and 64 characters of overlap. Splitting prefers paragraph, line, sentence, and word boundaries before using an exact character boundary.

PDFs are processed page by page so citations can retain page provenance. Stable SHA-256 identifiers are derived from the source and content.

### `src/embeddings.py`

Loads the local Sentence Transformer model, by default `all-MiniLM-L6-v2`.

It converts document chunks and user questions into numerical vectors. Vectors representing similar meanings should be near one another even when the wording is different.

The vectors are L2-normalized. FAISS inner-product search can therefore operate like cosine-similarity search.

### `src/bm25_index.py`

Implements sparse keyword retrieval with BM25.

It lowercases text, removes punctuation, removes common stop words, builds the BM25 corpus, searches it, and returns only chunks with positive scores.

BM25 is especially useful for exact names such as `FastAPI`, `Kubernetes`, `JWT`, or policy terminology.

The positive-score requirement also acts as an out-of-domain guard. If the meaningful query terms do not occur in any document, the method returns no result.

### `src/vector_store.py`

Implements the local FAISS vector database.

It uses `faiss.IndexFlatIP` to store normalized vectors and search for nearest semantic matches. It also keeps the `Chunk` objects in the same order as the vectors.

It saves two files:

- `faiss.index` for vectors.
- `chunks.pkl` for vector-to-document mapping.

FAISS is fast and suitable for this single-machine project. A distributed production deployment could replace it with pgvector, Qdrant, Pinecone, Weaviate, Milvus, or another managed vector database.

### `src/hybrid_retriever.py`

Combines BM25 keyword search and FAISS semantic search.

The query flow is:

```text
Question
  ├── BM25 keyword search
  └── FAISS vector search
          ↓
Reciprocal Rank Fusion
          ↓
Combined candidates
```

Reciprocal Rank Fusion gives a result a contribution similar to:

```text
1 / (RRF_K + rank)
```

A chunk that ranks well in both systems gets a strong combined score.

This implementation requires at least one BM25 result before performing vector retrieval. A vector database always returns a nearest vector, even for an unrelated query, so this guard prevents an unknown question from receiving the nearest irrelevant document.

The safety trade-off is that a valid semantic question with no overlapping meaningful word may also be rejected.

### `src/reranker.py`

Uses the cross-encoder model `cross-encoder/ms-marco-MiniLM-L-6-v2` by default.

Unlike embeddings, which encode the question and chunk separately, the cross-encoder reads each question/chunk pair together and assigns a relevance score.

Hybrid retrieval prioritizes recall and produces candidates. Reranking prioritizes precision and selects the best final chunks. The default configuration keeps five chunks.

### `src/citation_engine.py`

Builds the context sent to the LLM and enforces citation rules.

After reranking, chunks receive numbers:

```text
[1] Best chunk
[2] Second-best chunk
[3] Third-best chunk
```

Each `Citation` records its number, chunk ID, source file, page number, preview text, and confidence.

The system prompt requires the LLM to use only supplied context, cite factual statements, use single citation identifiers such as `[1]`, avoid ranges such as `[1-5]`, and abstain when context is insufficient.

Validation checks:

- Whether factual output has a citation.
- Whether cited identifiers exist.
- Whether substantive paragraphs are uncited.
- Whether citation syntax is malformed.
- Whether the answer is an explicit safe abstention.

`all_valid=true` can mean either a correctly cited answer or a correctly handled abstention. It does not necessarily mean the abstention itself has a source citation.

### `src/generator.py`

Connects to Groq, OpenAI, or xAI using OpenAI-compatible clients.

For each question it sends:

1. A system prompt containing grounding and citation rules.
2. A user message containing the retrieved context and original question.

It provides synchronous, asynchronous, and streaming generation methods.

If no key is configured or an API call fails, the fallback extracts the highest-ranked retrieved chunk and returns it with `[1]`. If no context exists, it returns the safe abstention.

Groq is used for focused answer writing. It is not used for document parsing, chunking, BM25, embeddings, FAISS search, reranking, or citation validation.

### `src/pipeline.py`

This is the central coordinator.

`RAGPipeline.initialize()` loads saved BM25 and FAISS indexes and connects the retriever.

`RAGPipeline.ingest()` parses documents, creates chunks, builds both indexes, saves them, and records statistics.

`RAGPipeline.query()` performs retrieval, reranking, citation-context creation, LLM generation, citation validation, one repair attempt for invalid citations, and final safe abstention if validation still fails.

`PipelineResult` contains the final answer, citations, validation details, original retrieval results, reranked results, latency, and metadata.

### `src/server.py`

Creates the FastAPI application and initializes the pipeline during server startup.

Endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /` | Returns the web UI |
| `GET /api/health` | Returns readiness, document count, chunk count, and model information |
| `POST /api/ask` | Accepts a question and returns a RAG answer |
| `POST /api/ingest` | Rebuilds indexes for an allowed document directory |

Example request:

```json
{
  "query": "What is FastAPI?"
}
```

The ask endpoint runs synchronous pipeline work in a worker thread so the main FastAPI event loop remains responsive.

The ingestion endpoint restricts paths to `ALLOWED_DOCS_ROOT`, preventing arbitrary server-file ingestion.

---

## 7. Frontend files

### `static/index.html`

Defines the visible page: heading, health status, document statistics, suggested questions, chat area, text input, Ask button, request status, and footer.

It loads versioned local CSS and JavaScript files to reduce stale browser-cache problems.

### `static/style.css`

Defines the self-contained responsive design: layout, chat bubbles, source panels, citation badges, composer, status indicator, loading state, error state, and mobile layout.

No external icon or font service is required.

### `static/app.js`

Connects the browser to FastAPI.

It calls `/api/health`, sends questions to `/api/ask`, shows loading state, renders user and assistant messages, converts `[1]` into a clickable citation badge, displays retrieved source previews, shows latency, and reports errors.

It escapes text before inserting it into HTML to reduce script-injection risk. The provider API key remains on the backend and is never sent to the browser.

---

## 8. Generated data files

### `data/bm25_index.pkl`

Stores the built BM25 keyword index and its associated chunks.

### `data/vector_store/faiss.index`

Stores all document-chunk embeddings in FAISS. This is the local vector database file.

### `data/vector_store/chunks.pkl`

Stores the source chunks corresponding to the FAISS vector positions. When FAISS returns vector position 25, this file identifies the original chunk at position 25.

These files are generated by ingestion and should be rebuilt after changing documents, chunk settings, or the embedding model.

---

## 9. Scripts

### `scripts/ingest.py`

Command-line entry point for indexing documents:

```powershell
python scripts/ingest.py --docs-dir ./docs
```

It validates the directory, creates the pipeline, calls ingestion, and prints file/chunk/index statistics.

Run it after adding, editing, or removing documents. Normal questions do not require re-ingestion.

### `scripts/evaluate.py`

Runs the golden dataset through the pipeline and calculates quality metrics.

Current gates:

| Metric | Gate |
|---|---:|
| Recall@K | 0.70 or higher |
| Mean Reciprocal Rank | 0.50 or higher |
| Citation accuracy | 0.80 or higher |

Recall checks whether the expected source was retrieved. MRR rewards placing the first correct source near the top. Citation accuracy requires a valid cited answer rather than an abstention.

The script writes `eval-results.json` and exits with code 1 if a gate fails, allowing CI to block a change.

---

## 10. Test files

### `tests/__init__.py`

Marks the tests directory as a Python package.

### `tests/conftest.py`

Provides shared pytest fixtures for the initialized pipeline, citation engine, and golden dataset.

### `tests/golden_dataset.json`

Contains evaluation questions, expected source documents, expected answer keywords, categories, and minimum citations.

### `tests/test_retrieval.py`

Tests Recall@K, MRR, and whether hybrid retrieval behaves better than a single retrieval method.

### `tests/test_pipeline.py`

Tests pipeline result structure, latency, empty-query rejection, expected answer content, and ingestion statistics.

### `tests/test_citations.py`

Tests citation presence, accuracy, format, and nonexistent citation prevention.

### `tests/test_citation_validation.py`

Tests valid citations, unknown citation IDs, uncited claims, explicit abstention, citations placed after sentences, and rejection of citation ranges.

### `tests/test_pipeline_enforcement.py`

Uses controlled fake components to verify that invalid uncited generation is replaced by a safe abstention.

### `tests/test_generator_fallback.py`

Verifies that LLM failure produces a cited retrieved excerpt instead of an uncited invented answer.

### `tests/test_out_of_domain.py`

Verifies that an unrelated question cannot receive the nearest unrelated vector result.

---

## 11. CI workflow

### `.github/workflows/eval-gate.yml`

Runs on pushes to `main` and pull requests targeting `main`.

It checks out the repository, configures Python 3.11, installs dependencies, ingests sample documents, runs pytest, runs the evaluation script, and uploads reports.

The current workflow supplies `OPENAI_API_KEY` from GitHub Secrets and defaults to the OpenAI provider in CI. To use Groq in CI instead, the workflow must provide `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and optionally `GROQ_MODEL`.

---

## 12. Complete ingestion flow

```text
1. Read files from docs/
2. Select a parser by file extension
3. Extract plain text
4. Split text into overlapping chunks
5. Attach source and position metadata
6. Build BM25 from tokenized chunk text
7. Create an embedding for every chunk
8. Add normalized embeddings to FAISS
9. Save BM25 to data/bm25_index.pkl
10. Save FAISS to data/vector_store/faiss.index
11. Save chunk mapping to data/vector_store/chunks.pkl
12. Mark the pipeline initialized
```

Detailed view:

```text
docs/sample_fastapi.md
        ↓
DocumentChunker
        ↓
512-character overlapping chunks
        ├───────────────────┐
        ↓                   ↓
BM25Index              EmbeddingModel
        ↓                   ↓
bm25_index.pkl          numeric vectors
                            ↓
                        VectorStore
                            ↓
                    faiss.index + chunks.pkl
```

---

## 13. Complete question-answer flow

```text
1. User enters a question in the browser.
2. app.js sends POST /api/ask with {"query": "..."}.
3. FastAPI validates that the query is not empty.
4. BM25 searches for keyword evidence.
5. If BM25 finds nothing, retrieval stops for safety.
6. If BM25 finds evidence, the question is embedded locally.
7. FAISS retrieves semantically similar chunks.
8. RRF combines BM25 and FAISS rankings.
9. The cross-encoder reranks the combined candidates.
10. The top five chunks receive citation IDs.
11. Groq receives the question, context, and citation instructions.
12. Groq writes a concise grounded answer.
13. CitationEngine validates citations and coverage.
14. Invalid output receives one repair attempt.
15. Output still invalid after repair becomes a safe abstention.
16. FastAPI returns answer, citations, sources, scores, and latency.
17. app.js displays the answer and interactive source badges.
```

Architecture view:

```text
User
  ↓
Browser UI
  ↓ POST /api/ask
FastAPI server
  ↓
RAGPipeline
  ├── BM25 keyword search ─────┐
  └── FAISS vector search ─────┤
                               ↓
                       Reciprocal Rank Fusion
                               ↓
                       Cross-encoder reranker
                               ↓
                       Best document chunks
                               ↓
                       Citation context
                               ↓
                       Groq generation
                               ↓
                       Citation validation
                               ↓
FastAPI JSON response
  ↓
Answer and source badges in UI
```

---

## 14. Known-question example: “What is FastAPI?”

1. The browser sends the question to `/api/ask`.
2. BM25 removes common words such as `what` and `is`; `fastapi` remains.
3. BM25 finds exact FastAPI chunks.
4. FAISS finds semantically related FastAPI chunks.
5. RRF merges the two rankings.
6. The cross-encoder places the FastAPI introduction near the top.
7. CitationEngine labels it `[1]`.
8. Groq receives the selected chunks and returns a concise answer ending in `[1]`.
9. CitationEngine verifies that `[1]` exists and covers the factual response.
10. The UI displays `[1]` as the clickable badge `1`.

---

## 15. Unknown-question example: “What is Spring Boot?”

1. BM25 extracts meaningful terms such as `spring` and `boot`.
2. The indexed documents contain no positive lexical match.
3. HybridRetriever returns an empty result before FAISS can provide an unrelated nearest vector.
4. There is no verified context for Groq.
5. The application returns: `I don't have enough verified context to answer this question.`

This is expected safety behavior, not an application failure.

---

## 16. Why some general questions are rejected

Questions such as `Who are you?` or `What is Spring Boot?` are not answered because the application is intentionally document-only.

`What is security?` may produce a cautious response because the security document describes policies but may not contain a direct dictionary definition. More specific questions work better, such as:

```text
What is the information security policy?
What security rules must employees follow?
What is the principle of least privilege?
```

---

## 17. How to run the project

From PowerShell:

```powershell
cd "C:\Users\Lenovo\Documents\AI Projects\ask-my-docs"
uvicorn src.server:app --reload --port 8001
```

Open:

```text
http://127.0.0.1:8001/
```

Any available port can be used by changing `--port`.

---

## 18. How to add or update documents

1. Copy supported files into `docs/`.
2. Run ingestion:

```powershell
python scripts/ingest.py --docs-dir ./docs
```

3. Restart the server.
4. Ask questions that can be answered by the new documents.

Re-ingestion is required after adding, editing, or removing documents, changing chunk settings, or changing the embedding model.

---

## 19. How to run tests and evaluation

Run tests:

```powershell
pytest tests -v
```

Run the evaluation gates:

```powershell
python scripts/evaluate.py
```

The evaluation script may make provider API calls and therefore requires a configured provider key.

---

## 20. What is production-style and what still needs enterprise hardening

The project demonstrates the standard enterprise RAG pattern: hybrid retrieval, vector storage, reranking, grounding, citation enforcement, evaluation, and CI gating.

Before a real multi-user company deployment, consider adding:

- Authentication and authorization.
- User- and department-level document permissions.
- Managed secret storage instead of a local `.env`.
- Rate limiting and request quotas.
- Structured logging, tracing, and monitoring.
- Persistent query/audit history with privacy controls.
- Malware scanning and stronger document validation.
- A production vector database for distributed scale.
- Background ingestion jobs and incremental updates.
- Provider retry, timeout, and circuit-breaker policies.
- Semantic entailment or human review for higher-stakes answers.
- Containerization and deployment configuration.

---

## 21. Short summary

Ask My Docs is a hybrid RAG system. It indexes documents in both BM25 and FAISS, combines keyword and semantic retrieval with RRF, reranks results using a cross-encoder, sends the best chunks to Groq, validates citations, refuses unsupported questions, and exposes the result through FastAPI and a browser UI. Automated tests and an evaluation script measure retrieval and citation quality.
