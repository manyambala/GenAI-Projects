#!/usr/bin/env python3
"""
CLI Evaluation Script for the Ask My Docs RAG pipeline.

Runs every question from the golden dataset through the pipeline,
calculates aggregate metrics, and prints a formatted report.

Exit code 0 if all gates pass, 1 if any gate fails.

Usage:
    python scripts/evaluate.py
"""

import sys
import os
import json
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.pipeline import RAGPipeline


# ── Quality Gates ─────────────────────────────────────────────────────
GATE_RECALL_AT_5 = 0.7
GATE_MRR = 0.5
GATE_CITATION_ACCURACY = 0.8


def main():
    # Load golden dataset
    dataset_path = project_root / "tests" / "golden_dataset.json"
    with open(dataset_path, "r", encoding="utf-8") as f:
        golden = json.load(f)

    # Initialize pipeline
    print("=" * 60)
    print("  ASK MY DOCS — EVALUATION PIPELINE")
    print("=" * 60)
    print()

    pipeline = RAGPipeline()
    if not pipeline._generator.client:
        print("ERROR: OPENAI_API_KEY is required for the citation evaluation gate.")
        sys.exit(2)

    docs_dir = project_root / "docs"

    # Check if indices exist, otherwise ingest
    data_dir = Path(pipeline.settings.DATA_DIR)
    if not (data_dir / "bm25_index.pkl").exists():
        print("⏳  No persisted indices found. Ingesting sample docs...")
        stats = pipeline.ingest(docs_dir)
        print(f"   ✓ Ingested {stats['num_files']} files → {stats['num_chunks']} chunks\n")
    else:
        pipeline.initialize()
        print(f"   ✓ Loaded persisted indices\n")

    # Run evaluation
    recall_hits = 0
    mrr_sum = 0.0
    citation_accuracy_sum = 0.0
    total_latency = 0.0
    results = []

    print(f"Running {len(golden)} evaluation queries...\n")
    print(f"{'#':<4} {'Category':<12} {'Recall':>8} {'MRR':>8} {'Cit.Acc':>8} {'Latency':>10}  Question")
    print("-" * 100)

    for i, entry in enumerate(golden):
        question = entry["question"]
        expected_sources = entry["expected_sources"]

        start = time.time()
        result = pipeline.query(question)
        elapsed = (time.time() - start) * 1000
        total_latency += elapsed

        # ── Recall@K ──
        retrieved_sources = [
            os.path.basename(chunk.source_file)
            for chunk, _score in result.reranked_chunks
        ]
        hit = any(src in retrieved_sources for src in expected_sources)
        if hit:
            recall_hits += 1

        # ── MRR ──
        rr = 0.0
        for rank, src in enumerate(retrieved_sources, 1):
            if src in expected_sources:
                rr = 1.0 / rank
                break
        mrr_sum += rr

        # ── Citation Accuracy ──
        cit_acc = 1.0 if (
            result.citation_validation.get("all_valid", False) and not result.citation_validation.get("abstained", False)
        ) else 0.0
        citation_accuracy_sum += cit_acc

        results.append({
            "id": entry.get("id", f"q_{i}"),
            "hit": hit,
            "rr": rr,
            "cit_acc": cit_acc,
            "latency_ms": elapsed,
        })

        print(
            f"{i+1:<4} {entry.get('category', '?'):<12} "
            f"{'✓' if hit else '✗':>8} "
            f"{rr:>8.3f} "
            f"{cit_acc:>8.2f} "
            f"{elapsed:>8.0f}ms  "
            f"{question[:50]}"
        )

    # ── Aggregate Metrics ──
    n = len(golden)
    recall = recall_hits / n if n else 0
    mrr = mrr_sum / n if n else 0
    avg_cit_acc = citation_accuracy_sum / n if n else 0
    avg_latency = total_latency / n if n else 0

    print()
    print("=" * 60)
    print("  AGGREGATE RESULTS")
    print("=" * 60)
    print(f"  Recall@K         : {recall:.3f}  (gate ≥ {GATE_RECALL_AT_5})")
    print(f"  MRR              : {mrr:.3f}  (gate ≥ {GATE_MRR})")
    print(f"  Citation Accuracy: {avg_cit_acc:.3f}  (gate ≥ {GATE_CITATION_ACCURACY})")
    print(f"  Avg Latency      : {avg_latency:.0f} ms")
    print("=" * 60)

    # ── Gate Checks ──
    gates_passed = True

    if recall < GATE_RECALL_AT_5:
        print(f"  ❌  FAIL  Recall@K {recall:.3f} < {GATE_RECALL_AT_5}")
        gates_passed = False
    else:
        print(f"  ✅  PASS  Recall@K")

    if mrr < GATE_MRR:
        print(f"  ❌  FAIL  MRR {mrr:.3f} < {GATE_MRR}")
        gates_passed = False
    else:
        print(f"  ✅  PASS  MRR")

    if avg_cit_acc < GATE_CITATION_ACCURACY:
        print(f"  ⚠️  WARN  Citation Accuracy {avg_cit_acc:.3f} < {GATE_CITATION_ACCURACY} (non-blocking without LLM)")
        gates_passed = False
    else:
        print(f"  ✅  PASS  Citation Accuracy")

    with open(project_root / "eval-results.json", "w", encoding="utf-8") as report_file:
        json.dump(results, report_file, indent=2)

    print()
    if gates_passed:
        print("🎉  All quality gates PASSED!")
        sys.exit(0)
    else:
        print("💥  One or more quality gates FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
