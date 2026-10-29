"""
FastAPI server for the Ask My Docs RAG system.

Endpoints:
  POST /api/ask        — Synchronous query
  GET  /api/health     — Health check & index stats
  POST /api/ingest     — Trigger document re-ingestion
  GET  /               — Serves the chat UI
"""

import logging
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.pipeline import RAGPipeline
from src.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

# ── Global pipeline instance ──────────────────────────────────────────
pipeline: RAGPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the RAG pipeline on startup."""
    global pipeline
    pipeline = RAGPipeline()
    try:
        pipeline.initialize()
        logger.info("Pipeline initialized (loaded persisted indices)")
    except Exception:
        logger.warning("No persisted indices found — ingest documents first via POST /api/ingest or `python scripts/ingest.py`")
    yield


app = FastAPI(
    title="Ask My Docs",
    description="Enterprise RAG system with hybrid retrieval, cross-encoder reranking, and citation enforcement.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────
settings = get_settings()
allowed_origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )


# ── Request / Response Schemas ────────────────────────────────────────
class AskRequest(BaseModel):
    query: str


class CitationResponse(BaseModel):
    citation_id: int
    chunk_id: str
    source_file: str
    page_number: int | None
    text_snippet: str
    confidence: float


class AskResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    citation_validation: dict
    sources: list[dict]
    latency_ms: float
    metadata: dict


class IngestRequest(BaseModel):
    docs_dir: str = "docs"


class IngestResponse(BaseModel):
    status: str
    num_files: int
    num_chunks: int
    index_size: int


# ── API Endpoints ─────────────────────────────────────────────────────

@app.post("/api/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    """Main query endpoint — runs the full RAG pipeline."""
    if not pipeline or not pipeline._initialized:
        raise HTTPException(status_code=503, detail="Pipeline not initialized. Ingest documents first.")

    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        result = await asyncio.to_thread(pipeline.query, request.query)
    except Exception as e:
        logger.exception("Pipeline error")
        raise HTTPException(status_code=500, detail=str(e))

    # Build response
    citations_out = [
        CitationResponse(
            citation_id=c.citation_id,
            source_file=Path(c.source_file).name,
            chunk_id=c.chunk_id,
            page_number=c.page_number,
            text_snippet=c.text_snippet,
            confidence=round(c.confidence, 4),
        )
        for c in result.citations
    ]

    sources_out = [
        {
            "id": str(c.citation_id),
            "title": Path(c.source_file).name,
            "text": c.text_snippet,
            "chunk_id": c.chunk_id,
            "score": round(c.confidence, 4),
        }
        for c in result.citations
    ]

    return AskResponse(
        answer=result.answer,
        citations=citations_out,
        citation_validation=result.citation_validation,
        sources=sources_out,
        latency_ms=round(result.latency_ms, 1),
        metadata=result.metadata,
    )


@app.get("/api/health")
async def health():
    """Health check returning index statistics."""
    if not pipeline:
        return {"status": "not_initialized", "docs": 0, "chunks": 0}

    stats = pipeline.get_stats()
    return {
        "status": "healthy" if stats["initialized"] else "not_initialized",
        "docs": stats.get("total_documents", 0),
        "llm_configured": bool(pipeline._generator.client),
        "chunks": stats.get("total_chunks", 0),
        "faiss_vectors": stats.get("faiss_vectors", 0),
        "embedding_model": stats.get("embedding_model", ""),
        "reranker_model": stats.get("reranker_model", ""),
    }


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest):
    """Trigger document ingestion (or re-ingestion)."""
    if not pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not created.")

    project_root = Path(__file__).resolve().parent.parent
    allowed_root = (project_root / pipeline.settings.ALLOWED_DOCS_ROOT).resolve()
    requested_path = Path(request.docs_dir)
    docs_path = requested_path.resolve() if requested_path.is_absolute() else (project_root / requested_path).resolve()
    try:
        docs_path.relative_to(allowed_root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Ingestion path is outside the allowed documents root.")
    if not docs_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory not found: {request.docs_dir}")

    try:
        stats = pipeline.ingest(docs_path)
    except Exception as e:
        logger.exception("Ingestion error")
        raise HTTPException(status_code=500, detail=str(e))

    return IngestResponse(
        status="success",
        num_files=stats["num_files"],
        num_chunks=stats["num_chunks"],
        index_size=stats["index_size"],
    )


# ── Static files & SPA fallback ──────────────────────────────────────
static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    """Serve the chat UI."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Ask My Docs API is running. Put static/index.html to serve the UI."}
