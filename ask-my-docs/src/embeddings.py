from typing import List
import numpy as np

class EmbeddingModel:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: List[str], batch_size: int = 32, show_progress: bool = True) -> np.ndarray:
        embeddings = self.model.encode(texts, batch_size=batch_size, show_progress_bar=show_progress)
        # L2-normalize
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return embeddings / norms

    def encode_query(self, query: str) -> np.ndarray:
        embedding = self.model.encode([query])[0]
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding

    @property
    def dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()
