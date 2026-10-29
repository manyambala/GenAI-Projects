"""
End-to-end RAG Pipeline Orchestrator.

Ties together: chunker → embeddings → BM25 + FAISS → hybrid retriever → reranker → citation engine → LLM generator.
"""

import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional

from src.config import get_settings
from src.chunker import DocumentChunker, Chunk
from src.embeddings import EmbeddingModel
from src.bm25_index import BM25Index
from src.vector_store import VectorStore
from src.hybrid_retriever import HybridRetriever
from src.reranker import CrossEncoderReranker
from src.citation_engine import CitationEngine, Citation
from src.generator import LLMGenerator

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Structured result from a RAG pipeline query."""
    answer: str
    citations: List[Citation]
    citation_validation: dict
    retrieved_chunks: List[Tuple[Chunk, float]]
    reranked_chunks: List[Tuple[Chunk, float]]
    latency_ms: float
    metadata: dict


class RAGPipeline:
    """End-to-end RAG pipeline with hybrid retrieval, cross-encoder reranking, and citation enforcement."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self._initialized = False

        # Core models (lazy-loaded internally)
        self._embedding_model = EmbeddingModel(model_name=self.settings.EMBEDDING_MODEL)
        self._reranker = CrossEncoderReranker(model_name=self.settings.RERANKER_MODEL)
        self._citation_engine = CitationEngine()

        # Indices — created during ingest or loaded during initialize
        self._bm25_index: Optional[BM25Index] = None
        self._vector_store: Optional[VectorStore] = None
        self._hybrid_retriever: Optional[HybridRetriever] = None

        # Generator. xAI exposes an OpenAI-compatible API surface.
        provider = self.settings.LLM_PROVIDER.lower()
        if provider == "xai":
            api_key = self.settings.XAI_API_KEY or self.settings.GROK_API_KEY
            model = self.settings.XAI_MODEL
            base_url = "https://api.x.ai/v1"
        elif provider == "groq":
            api_key = self.settings.GROQ_API_KEY
            model = self.settings.GROQ_MODEL
            base_url = "https://api.groq.com/openai/v1"
        elif provider == "openai":
            api_key = self.settings.OPENAI_API_KEY
            model = self.settings.OPENAI_MODEL
            base_url = None
        else:
            raise ValueError("LLM_PROVIDER must be 'openai', 'xai', or 'groq'.")

        self._generator = LLMGenerator(
            api_key=api_key,
            model=model,
            use_env_proxy=self.settings.OPENAI_USE_ENV_PROXY,
            base_url=base_url,
        )

        # Stats
        self._num_documents = 0
        self._num_chunks = 0

    @property
    def _data_dir(self) -> Path:
        p = Path(self.settings.DATA_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ------------------------------------------------------------------
    # Initialization (load persisted indices)
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Load persisted BM25 and FAISS indices from disk."""
        bm25_path = self._data_dir / "bm25_index.pkl"
        vector_dir = self._data_dir / "vector_store"

        self._bm25_index = BM25Index()
        try:
            self._bm25_index.load(bm25_path)
            self._num_chunks = len(self._bm25_index._chunks)
            self._num_documents = len(set(c.source_file for c in self._bm25_index._chunks))
            logger.info("Loaded BM25 index with %d chunks", self._num_chunks)
        except FileNotFoundError:
            logger.warning("BM25 index not found at %s — run ingest first", bm25_path)

        # VectorStore needs dimension; get it from the embedding model
        dim = self._embedding_model.dimension
        self._vector_store = VectorStore(dimension=dim)
        try:
            self._vector_store.load(vector_dir)
            logger.info("Loaded FAISS vector store (%d vectors)", self._vector_store._index.ntotal)
        except FileNotFoundError:
            logger.warning("FAISS vector store not found at %s — run ingest first", vector_dir)

        self._hybrid_retriever = HybridRetriever(
            self._bm25_index, self._vector_store, self._embedding_model,
            rrf_k=self.settings.RRF_K,
        )
        self._initialized = bool(self._bm25_index._index) and self._vector_store._index.ntotal > 0

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(self, docs_dir: Path = None) -> dict:
        """Parse → chunk → embed → build indices → save to disk."""
        if docs_dir is None:
            docs_dir = Path(self.settings.DOCS_DIR)
        docs_dir = Path(docs_dir)  # ensure Path

        logger.info("Starting ingestion from %s …", docs_dir)

        # 1. Parse & chunk
        chunker = DocumentChunker(
            chunk_size=self.settings.CHUNK_SIZE,
            chunk_overlap=self.settings.CHUNK_OVERLAP,
        )
        chunks = chunker.process_directory(docs_dir)
        if not chunks:
            raise RuntimeError(f"No chunks produced from {docs_dir}")

        logger.info("Created %d chunks from %d files",
                     len(chunks), len(set(c.source_file for c in chunks)))

        # 2. Build BM25 index
        self._bm25_index = BM25Index()
        self._bm25_index.build(chunks)

        # 3. Embed all chunks (batch)
        texts = [c.text for c in chunks]
        embeddings = self._embedding_model.encode(texts, batch_size=64, show_progress=True)

        # 4. Build FAISS vector store
        dim = embeddings.shape[1]
        self._vector_store = VectorStore(dimension=dim)
        self._vector_store.add(chunks, embeddings)

        # 5. Persist
        self._bm25_index.save(self._data_dir / "bm25_index.pkl")
        self._vector_store.save(self._data_dir / "vector_store")

        # 6. Wire up hybrid retriever
        self._hybrid_retriever = HybridRetriever(
            self._bm25_index, self._vector_store, self._embedding_model,
            rrf_k=self.settings.RRF_K,
        )
        self._initialized = True

        self._num_documents = len(set(c.source_file for c in chunks))
        self._num_chunks = len(chunks)

        stats = {
            "num_files": self._num_documents,
            "num_chunks": self._num_chunks,
            "index_size": self._vector_store._index.ntotal,
        }
        logger.info("Ingestion complete: %s", stats)
        return stats

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(self, question: str) -> PipelineResult:
        """Full pipeline: retrieve → rerank → cite → generate → validate."""
        if not question or not question.strip():
            raise ValueError("Query cannot be empty.")
        if not self._initialized:
            self.initialize()
        if not self._initialized:
            raise RuntimeError("Pipeline is not initialized. Ingest documents first.")

        start = time.time()

        # Hybrid retrieval (BM25 + FAISS fused via RRF)
        retrieved = self._hybrid_retriever.search(
            question,
            bm25_top_k=self.settings.BM25_TOP_K,
            vector_top_k=self.settings.VECTOR_TOP_K,
            fusion_top_k=self.settings.FUSION_TOP_K,
        )

        # Cross-encoder reranking
        reranked = self._reranker.rerank(
            question, retrieved, top_k=self.settings.RERANK_TOP_K,
        )

        # Citation-enforced generation
        context_str, citations = self._citation_engine.build_citation_context(reranked)
        system_prompt = self._citation_engine.get_system_prompt()
        answer = self._generator.generate(question, context_str, system_prompt)

        # Validate citations
        validation = self._citation_engine.validate_citations(answer, citations)
        if not validation["all_valid"]:
            repair_prompt = (
                f"{system_prompt}\n"
                "Return a corrected answer now. Use only single citations like [1]; "
                "never use citation ranges such as [1-5]."
            )
            answer = self._generator.generate(question, context_str, repair_prompt)
            validation = self._citation_engine.validate_citations(answer, citations)
        if not validation["all_valid"]:
            logger.warning("Citation validation failed after one repair attempt; returning an abstention")
            answer = "I don't have enough verified context to answer this question."
            validation = self._citation_engine.validate_citations(answer, citations)
            validation["enforced"] = True
        else:
            validation["enforced"] = False


        latency_ms = (time.time() - start) * 1000

        return PipelineResult(
            answer=answer,
            citations=citations,
            citation_validation=validation,
            retrieved_chunks=retrieved,
            reranked_chunks=reranked,
            latency_ms=latency_ms,
            metadata={
                "bm25_top_k": self.settings.BM25_TOP_K,
                "vector_top_k": self.settings.VECTOR_TOP_K,
                "rerank_top_k": self.settings.RERANK_TOP_K,
                "num_retrieved": len(retrieved),
                "num_reranked": len(reranked),
            },
        )

    async def aquery(self, question: str) -> PipelineResult:
        """Async version of query — generation step is awaited."""
        if not question or not question.strip():
            raise ValueError("Query cannot be empty.")
        if not self._initialized:
            self.initialize()
        if not self._initialized:
            raise RuntimeError("Pipeline is not initialized. Ingest documents first.")

        start = time.time()

        retrieved = self._hybrid_retriever.search(
            question,
            bm25_top_k=self.settings.BM25_TOP_K,
            vector_top_k=self.settings.VECTOR_TOP_K,
            fusion_top_k=self.settings.FUSION_TOP_K,
        )

        reranked = self._reranker.rerank(
            question, retrieved, top_k=self.settings.RERANK_TOP_K,
        )

        context_str, citations = self._citation_engine.build_citation_context(reranked)
        system_prompt = self._citation_engine.get_system_prompt()
        answer = await self._generator.agenerate(question, context_str, system_prompt)

        validation = self._citation_engine.validate_citations(answer, citations)
        if not validation["all_valid"]:
            repair_prompt = (
                f"{system_prompt}\n"
                "Return a corrected answer now. Use only single citations like [1]; "
                "never use citation ranges such as [1-5]."
            )
            answer = await self._generator.agenerate(question, context_str, repair_prompt)
            validation = self._citation_engine.validate_citations(answer, citations)
        if not validation["all_valid"]:
            logger.warning("Citation validation failed after one repair attempt; returning an abstention")
            answer = "I don't have enough verified context to answer this question."
            validation = self._citation_engine.validate_citations(answer, citations)
            validation["enforced"] = True
        else:
            validation["enforced"] = False

        latency_ms = (time.time() - start) * 1000

        return PipelineResult(
            answer=answer,
            citations=citations,
            citation_validation=validation,
            retrieved_chunks=retrieved,
            reranked_chunks=reranked,
            latency_ms=latency_ms,
            metadata={
                "bm25_top_k": self.settings.BM25_TOP_K,
                "vector_top_k": self.settings.VECTOR_TOP_K,
                "rerank_top_k": self.settings.RERANK_TOP_K,
                "num_retrieved": len(retrieved),
                "num_reranked": len(reranked),
            },
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return current index statistics."""
        return {
            "initialized": self._initialized,
            "total_documents": self._num_documents,
            "total_chunks": self._num_chunks,
            "faiss_vectors": self._vector_store._index.ntotal if self._vector_store else 0,
            "embedding_model": self.settings.EMBEDDING_MODEL,
            "reranker_model": self.settings.RERANKER_MODEL,
        }
