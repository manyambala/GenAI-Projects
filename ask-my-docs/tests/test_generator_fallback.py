from src.generator import LLMGenerator


def test_fallback_returns_a_cited_retrieved_excerpt():
    context = "[1] Source: fastapi.md\nFastAPI is a modern Python web framework.\n\n[2] Source: other.md\nOther text."

    answer = LLMGenerator().generate("What is FastAPI?", context, "system prompt")

    assert answer.startswith("Based on the retrieved documentation:")
    assert "FastAPI is a modern Python web framework." in answer
    assert answer.endswith("[1]")



