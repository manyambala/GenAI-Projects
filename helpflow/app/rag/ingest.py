"""Build a local Chroma index from the runbook directory."""

from pathlib import Path

from app.config import settings


def ingest_documents() -> int:
    documents_dir = Path(settings.data_dir) / "documents"
    index_dir = Path(settings.rag_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    markdown_files = sorted(documents_dir.glob("*.md"))
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(index_dir))
        collection = client.get_or_create_collection("helpflow_runbooks")
        for path in markdown_files:
            content = path.read_text(encoding="utf-8")
            collection.upsert(ids=[path.name], documents=[content], metadatas=[{"source_name": path.name, "path": str(path)}])
    except Exception as exc:
        (index_dir / "keyword-fallback.txt").write_text(str(exc), encoding="utf-8")
    return len(markdown_files)


if __name__ == "__main__":
    print(f"Indexed {ingest_documents()} runbook document(s)")
