from pathlib import Path

from app.config import settings


def _keyword_retrieve(query: str, limit: int) -> list[dict]:
    terms = set(query.lower().split())
    found = []
    documents_dir = Path(settings.data_dir) / "documents"
    for path in documents_dir.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        score = sum(1 for term in terms if len(term) > 3 and term in content.lower())
        if score:
            found.append({"source_name": path.name, "content": content[:4000], "confidence": min(.95, .45 + score * .08), "metadata": {"path": str(path), "retrieval": "keyword-fallback"}})
    return sorted(found, key=lambda item: item["confidence"], reverse=True)[:limit]


def retrieve(query: str, limit: int = 3) -> list[dict]:
    """Use Chroma when indexed; otherwise use a transparent local fallback."""
    try:
        import chromadb
        index_path = Path(settings.rag_dir)
        if index_path.exists() and any(index_path.iterdir()):
            collection = chromadb.PersistentClient(path=str(index_path)).get_or_create_collection("helpflow_runbooks")
            result = collection.query(query_texts=[query], n_results=limit)
            docs = result.get("documents", [[]])[0]
            ids = result.get("ids", [[]])[0]
            distances = result.get("distances", [[]])[0] if result.get("distances") else []
            return [{"source_name": ids[index], "content": docs[index][:4000], "confidence": max(.0, min(.99, 1 - float(distances[index]))) if index < len(distances) else .6, "metadata": {"retrieval": "chroma"}} for index in range(len(docs))]
    except BaseException as exc:
        # Chroma's Rust bindings can raise pyo3 PanicException, which inherits
        # directly from BaseException. RAG is optional, so degrade to keyword
        # retrieval while still allowing process-control exceptions through.
        if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
            raise
    return _keyword_retrieve(query, limit)
