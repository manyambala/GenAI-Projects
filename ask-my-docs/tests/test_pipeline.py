"""End-to-end pipeline tests — result structure, latency, edge cases, and keyword coverage."""

import pytest

from src.pipeline import PipelineResult


def test_pipeline_returns_result(pipeline):
    """Query returns a PipelineResult with all required fields populated."""
    result = pipeline.query("What is Kubernetes?")
    assert isinstance(result, PipelineResult)
    assert result.answer is not None and len(result.answer) > 0
    assert isinstance(result.citations, list)
    assert isinstance(result.retrieved_chunks, list)
    assert isinstance(result.reranked_chunks, list)
    assert result.latency_ms > 0
    assert isinstance(result.metadata, dict)


def test_pipeline_latency(pipeline):
    """Query completes within 30 seconds (generous for CI with model downloads)."""
    result = pipeline.query("How do Services work in Kubernetes?")
    assert result.latency_ms < 30_000, f"Query latency {result.latency_ms:.0f}ms exceeded 30s"


def test_pipeline_empty_query(pipeline):
    """Rejects an empty query before performing retrieval or generation."""
    with pytest.raises(ValueError, match="cannot be empty"):
        pipeline.query("")


@pytest.mark.parametrize("idx", [0, 5, 10])
def test_answer_contains_expected_keywords(pipeline, golden_dataset, idx):
    """For selected golden questions, the answer should contain at least some expected keywords."""
    if idx >= len(golden_dataset):
        pytest.skip(f"Golden dataset has only {len(golden_dataset)} entries")

    entry = golden_dataset[idx]
    result = pipeline.query(entry["question"])
    answer_lower = result.answer.lower()

    matched = sum(1 for kw in entry["expected_answer_contains"] if kw.lower() in answer_lower)
    total = len(entry["expected_answer_contains"])

    # At least half the expected keywords should appear
    assert matched >= max(1, total // 2), (
        f"Only {matched}/{total} expected keywords found in answer for: {entry['question']}"
    )


def test_ingest_stats(pipeline):
    """After ingestion, stats should report non-zero document and chunk counts."""
    stats = pipeline.get_stats()
    assert isinstance(stats, dict)
    assert stats.get("total_documents", 0) > 0, "No documents in stats"
    assert stats.get("total_chunks", 0) > 0, "No chunks in stats"
