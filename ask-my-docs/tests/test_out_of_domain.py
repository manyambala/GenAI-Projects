from src.bm25_index import BM25Index
from src.chunker import Chunk
from src.hybrid_retriever import HybridRetriever


class _VectorStore:
    def __init__(self):
        self.called = False

    def search(self, *_args, **_kwargs):
        self.called = True
        return []


class _EmbeddingModel:
    def encode_query(self, _query):
        raise AssertionError("Dense search must not run for an out-of-domain query")


def test_unknown_query_does_not_return_nearest_unrelated_document():
    chunk = Chunk(
        chunk_id="fastapi-1", doc_id="fastapi", text="FastAPI is a Python web framework.",
        source_file="fastapi.md", page_number=None, chunk_index=0,
        char_start=0, char_end=35,
    )
    bm25 = BM25Index()
    bm25.build([chunk])
    vector_store = _VectorStore()
    retriever = HybridRetriever(bm25, vector_store, _EmbeddingModel())

    results = retriever.search("What is Spring Boot?")

    assert results == []
    assert vector_store.called is False

