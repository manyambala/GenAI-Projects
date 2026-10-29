from typing import List, Tuple
from src.chunker import Chunk

class CrossEncoderReranker:
    def __init__(self, model_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(self, query: str, chunks: List[Tuple[Chunk, float]], top_k: int = 5) -> List[Tuple[Chunk, float]]:
        if not chunks:
            return []

        pairs = [[query, chunk.text] for chunk, _ in chunks]
        scores = self.model.predict(pairs)
        
        scored_chunks = [(chunk, float(score)) for (chunk, _), score in zip(chunks, scores)]
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        return scored_chunks[:top_k]
