from types import SimpleNamespace

from src.chunker import Chunk
from src.citation_engine import CitationEngine
from src.pipeline import RAGPipeline


class _Retriever:
    def __init__(self, chunk):
        self.chunk = chunk

    def search(self, *_args, **_kwargs):
        return [(self.chunk, 0.8)]


class _Reranker:
    def rerank(self, _question, chunks, top_k):
        return chunks[:top_k]


class _Generator:
    def generate(self, *_args):
        return "An uncited factual claim is returned here."


def test_pipeline_replaces_invalid_generation_with_abstention():
    pipeline = object.__new__(RAGPipeline)
    pipeline.settings = SimpleNamespace(
        BM25_TOP_K=5, VECTOR_TOP_K=5, FUSION_TOP_K=5, RERANK_TOP_K=1,
    )
    pipeline._initialized = True
    chunk = Chunk(
        chunk_id="chunk-1", doc_id="doc-1", text="Verified source text.",
        source_file="guide.md", page_number=None, chunk_index=0,
        char_start=0, char_end=21,
    )
    pipeline._hybrid_retriever = _Retriever(chunk)
    pipeline._reranker = _Reranker()
    pipeline._citation_engine = CitationEngine()
    pipeline._generator = _Generator()

    result = pipeline.query("What does the guide say?")

    assert result.citation_validation["enforced"] is True
    assert result.citation_validation["abstained"] is True
    assert result.answer == "I don't have enough verified context to answer this question."
