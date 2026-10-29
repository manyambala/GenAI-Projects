import re
from dataclasses import dataclass
from typing import List, Tuple

from src.chunker import Chunk

@dataclass
class Citation:
    citation_id: int
    chunk_id: str
    source_file: str
    page_number: int | None
    text_snippet: str
    confidence: float

class CitationEngine:
    def build_citation_context(self, chunks: List[Tuple[Chunk, float]]) -> Tuple[str, List[Citation]]:
        context_parts = []
        citations = []
        for i, (chunk, score) in enumerate(chunks):
            citation_id = i + 1
            citation = Citation(
                citation_id=citation_id,
                chunk_id=chunk.chunk_id,
                source_file=chunk.source_file,
                page_number=chunk.page_number,
                text_snippet=chunk.text[:200],
                confidence=score
            )
            citations.append(citation)
            
            context_part = f"[{citation_id}] Source: {chunk.source_file}"
            if chunk.page_number is not None:
                context_part += f" (Page {chunk.page_number})"
            context_part += f"\n{chunk.text}\n"
            context_parts.append(context_part)
            
        context_string = "\n".join(context_parts)
        return context_string, citations
        
    def get_system_prompt(self) -> str:
        return (
            "Answer the user's question directly and concisely, using only the provided context.\n"
            "For each factual sentence, cite only the source chunks that directly support it.\n"
            "A citation must be exactly one identifier such as [1], placed at the end of its sentence.\n"
            "Never use citation ranges (for example [1-5]), citation lists, or cite every provided chunk by default.\n"
            "Do not add a general definition or recommend external sources unless the user asks for them.\n"
            "If the context does not contain the answer, state that briefly.\n"
            "NEVER fabricate information not present in the provided sources."
        )
        
    def extract_citations(self, answer_text: str) -> List[int]:
        matches = re.findall(r'\[(\d+)\]', answer_text)
        return [int(m) for m in matches]
        
    def validate_citations(self, answer_text: str, available_citations: List[Citation]) -> dict:
        """Verify citation identifiers and coverage for each substantive paragraph or bullet."""
        found = self.extract_citations(answer_text)
        available_ids = [c.citation_id for c in available_citations]
        citation_tokens = re.findall(r"\[([^\]]*)\]", answer_text)
        malformed_citations = [token for token in citation_tokens if not re.fullmatch(r"\d+", token.strip())]
        valid = [c for c in found if c in available_ids]
        invalid = [c for c in found if c not in available_ids]

        citation_attached_text = re.sub(r"([.!?])\s*((?:\[\d+\]\s*)+)", r"\1\2", answer_text.strip())
        normalized = " ".join(citation_attached_text.lower().split())
        abstained = any(marker in normalized for marker in (
            "i don't have enough", "i do not have enough",
            "cannot answer from the provided", "can't answer from the provided",
            "context does not contain", "unable to answer from the provided",
        ))
        claims = re.split(r"\n\s*\n|(?:^|\n)\s*[-*]\s+", citation_attached_text)
        unsupported_claims = [
            claim.strip() for claim in claims
            if len(re.sub(r"\[\d+\]", "", claim).strip()) >= 12
            and re.search(r"[A-Za-z]", claim)
            and not re.search(r"\[\d+\]", claim)
            and not re.search(r"\b(i don't have enough|i do not have enough|cannot answer|can't answer|unable to answer)\b", claim, re.I)
        ]
        citation_coverage = 1.0 if abstained or not unsupported_claims else 0.0
        all_valid = (
            not invalid
            and citation_coverage == 1.0
            and not malformed_citations
            and (bool(found) or abstained)
        )

        return {
            "citation_present": len(found) > 0,
            "citations_found": found,
            "citations_valid": valid,
            "citations_invalid": invalid,
            "citation_accuracy": len(valid) / len(found) if found else 0.0,
            "citation_coverage": citation_coverage,
            "unsupported_claims": unsupported_claims,
            "malformed_citations": malformed_citations,
            "abstained": abstained,
            "all_valid": all_valid,
        }
