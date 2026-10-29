from src.citation_engine import Citation, CitationEngine


def _citations():
    return [
        Citation(1, "chunk-1", "guide.md", None, "Kubernetes manages workloads.", 0.9),
        Citation(2, "chunk-2", "guide.md", 2, "Pods run containers.", 0.8),
    ]


def test_accepts_valid_cited_claims():
    result = CitationEngine().validate_citations(
        "Kubernetes manages workloads [1]. Pods run containers [2].", _citations()
    )
    assert result["all_valid"]
    assert result["citation_coverage"] == 1.0


def test_rejects_unknown_citation_id():
    result = CitationEngine().validate_citations("Pods run containers [3].", _citations())
    assert not result["all_valid"]
    assert result["citations_invalid"] == [3]


def test_rejects_uncited_substantive_claim():
    result = CitationEngine().validate_citations(
        "Kubernetes manages workloads [1].\n\nPods run containers.", _citations()
    )
    assert not result["all_valid"]
    assert result["unsupported_claims"] == ["Pods run containers."]


def test_accepts_explicit_abstention():
    result = CitationEngine().validate_citations(
        "I don't have enough verified context to answer this question.", _citations()
    )
    assert result["all_valid"]

def test_accepts_citation_immediately_after_sentence():
    result = CitationEngine().validate_citations(
        "Kubernetes manages workloads. [1]", _citations()
    )
    assert result["all_valid"]
    assert result["citation_coverage"] == 1.0


def test_rejects_citation_ranges():
    result = CitationEngine().validate_citations(
        "Kubernetes manages workloads [1-2].", _citations()
    )
    assert not result["all_valid"]
    assert result["malformed_citations"] == ["1-2"]
