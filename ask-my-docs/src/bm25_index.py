import pickle
import string
from pathlib import Path
from typing import List, Tuple, Optional

from rank_bm25 import BM25Okapi
import numpy as np
from src.chunker import Chunk

STOP_WORDS = frozenset({
    "a", "an", "and", "are", "about", "can", "do", "does", "for", "how", "i", "in", "is", "it", "of", "on", "the", "to", "what", "when", "where", "which", "who", "why", "with", "you", "your",
})


class BM25Index:
    def __init__(self):
        self._index: Optional[BM25Okapi] = None
        self._chunks: List[Chunk] = []

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        text = text.translate(str.maketrans('', '', string.punctuation))
        return [token for token in text.split() if token not in STOP_WORDS]

    def build(self, chunks: List[Chunk]) -> None:
        self._chunks = chunks
        tokenized_corpus = [self._tokenize(chunk.text) for chunk in chunks]
        self._index = BM25Okapi(tokenized_corpus)

    def search(self, query: str, top_k: int = 50) -> List[Tuple[Chunk, float]]:
        if not self._index:
            raise RuntimeError("BM25 index not built yet.")
        
        tokenized_query = self._tokenize(query)
        scores = self._index.get_scores(tokenized_query)
        
        top_n_idx = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_n_idx:
            if scores[idx] > 0:
                results.append((self._chunks[idx], float(scores[idx])))
                
        return results

    def save(self, path: Path) -> None:
        with open(path, 'wb') as f:
            pickle.dump({'index': self._index, 'chunks': self._chunks}, f)

    def load(self, path: Path) -> None:
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self._index = data['index']
            self._chunks = data['chunks']
