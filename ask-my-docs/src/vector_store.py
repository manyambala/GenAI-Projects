import pickle
from pathlib import Path
from typing import List, Tuple

import faiss
import numpy as np
from src.chunker import Chunk

class VectorStore:
    def __init__(self, dimension: int):
        self.dimension = dimension
        self._index = faiss.IndexFlatIP(dimension)
        self._chunks: List[Chunk] = []

    def add(self, chunks: List[Chunk], embeddings: np.ndarray) -> None:
        if embeddings.shape[1] != self.dimension:
            raise ValueError(f"Embedding dimension mismatch. Expected {self.dimension}, got {embeddings.shape[1]}")
        
        self._index.add(np.ascontiguousarray(embeddings, dtype=np.float32))
        self._chunks.extend(chunks)

    def search(self, query_vector: np.ndarray, top_k: int = 50) -> List[Tuple[Chunk, float]]:
        if self._index.ntotal == 0:
            return []
            
        query_vector = np.ascontiguousarray(query_vector.reshape(1, -1), dtype=np.float32)
        scores, indices = self._index.search(query_vector, top_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1:
                results.append((self._chunks[idx], float(score)))
                
        return results

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(directory / "faiss.index"))
        with open(directory / "chunks.pkl", 'wb') as f:
            pickle.dump(self._chunks, f)

    def load(self, directory: Path) -> None:
        index_path = directory / "faiss.index"
        chunks_path = directory / "chunks.pkl"
        
        if not index_path.exists() or not chunks_path.exists():
            raise FileNotFoundError(f"Index or chunks not found in {directory}")
            
        self._index = faiss.read_index(str(index_path))
        with open(chunks_path, 'rb') as f:
            self._chunks = pickle.load(f)
