"""Shared pytest fixtures for the Ask My Docs evaluation suite."""

import sys
import os
import json
import pytest
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.pipeline import RAGPipeline
from src.citation_engine import CitationEngine


@pytest.fixture(scope="session")
def pipeline():
    """Create a RAGPipeline, ingest sample docs, and return it for re-use across all tests."""
    p = RAGPipeline()
    docs_dir = project_root / "docs"

    if docs_dir.exists():
        p.ingest(docs_dir)
    else:
        pytest.skip("docs/ directory not found — cannot run evaluation tests")

    return p


@pytest.fixture(scope="session")
def citation_engine():
    """Return a shared CitationEngine instance."""
    return CitationEngine()


@pytest.fixture
def golden_dataset():
    """Load the golden evaluation dataset."""
    dataset_path = Path(__file__).parent / "golden_dataset.json"
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)
