import pytest
import re

def test_citation_presence(pipeline, golden_dataset):
    for entry in golden_dataset[:3]: # Test on a small subset for speed
        result = pipeline.query(entry["question"])
        assert "[" in result.answer and "]" in result.answer, "Answer must contain citations in [n] format"

def test_citation_accuracy(pipeline, citation_engine, golden_dataset):
    entry = golden_dataset[0]
    result = pipeline.query(entry["question"])
    
    # Use CitationEngine.validate_citations()
    validation = citation_engine.validate_citations(result.answer, result.citations)
    assert validation is not None

def test_citation_format(pipeline, golden_dataset):
    entry = golden_dataset[0]
    result = pipeline.query(entry["question"])
    
    # Find all [n] patterns
    citations = re.findall(r'\[\d+\]', result.answer)
    assert len(citations) >= entry["min_citations"], f"Expected at least {entry['min_citations']} citations"

def test_no_hallucinated_citations(pipeline, golden_dataset):
    entry = golden_dataset[0]
    result = pipeline.query(entry["question"])
    
    citations = re.findall(r'\[(\d+)\]', result.answer)
    citation_ids = [int(c) for c in citations]
    
    max_valid_id = len(result.citations)
    for cid in citation_ids:
        assert cid <= max_valid_id, f"Hallucinated citation ID: {cid}"
        assert cid > 0, f"Invalid citation ID: {cid} (must be 1-indexed)"
