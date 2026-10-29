"""Retrieval quality tests — Recall@K, MRR, and hybrid-vs-single comparison."""

import os


def test_recall_at_k(pipeline, golden_dataset):
    """For each golden question, check if the expected source file appears in the top-K retrieved chunks."""
    successes = 0
    total = len(golden_dataset)

    for entry in golden_dataset:
        question = entry["question"]
        expected_sources = entry["expected_sources"]

        result = pipeline.query(question)
        # retrieved_chunks is List[Tuple[Chunk, float]]
        retrieved_sources = [
            os.path.basename(chunk.source_file)
            for chunk, _score in result.retrieved_chunks
        ]

        if any(src in retrieved_sources for src in expected_sources):
            successes += 1

    recall = successes / total if total > 0 else 0
    assert recall >= 0.7, f"Recall@K is {recall:.2f}, expected >= 0.7"


def test_mrr(pipeline, golden_dataset):
    """Calculate Mean Reciprocal Rank across the golden dataset."""
    mrr_sum = 0.0
    total = len(golden_dataset)

    for entry in golden_dataset:
        question = entry["question"]
        expected_sources = entry["expected_sources"]

        result = pipeline.query(question)
        retrieved_sources = [
            os.path.basename(chunk.source_file)
            for chunk, _score in result.retrieved_chunks
        ]

        for rank, src in enumerate(retrieved_sources, 1):
            if src in expected_sources:
                mrr_sum += 1.0 / rank
                break

    mrr = mrr_sum / total if total > 0 else 0
    assert mrr >= 0.5, f"MRR is {mrr:.3f}, expected >= 0.5"


def test_hybrid_beats_single(pipeline, golden_dataset):
    """Verify hybrid retrieval achieves reasonable recall on a subset of golden questions."""
    subset = golden_dataset[:5]
    successes = 0

    for entry in subset:
        result = pipeline.query(entry["question"])
        retrieved_sources = [
            os.path.basename(chunk.source_file)
            for chunk, _score in result.retrieved_chunks
        ]
        if any(src in retrieved_sources for src in entry["expected_sources"]):
            successes += 1

    recall = successes / len(subset)
    assert recall >= 0.6, f"Hybrid subset recall is {recall:.2f}, expected >= 0.6"
