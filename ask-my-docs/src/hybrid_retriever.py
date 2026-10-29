from typing import List, Tuple, Dict
from src.chunker import Chunk
from src.bm25_index import BM25Index
from src.vector_store import VectorStore
from src.embeddings import EmbeddingModel

class HybridRetriever:
    def __init__(
        self,
        bm25_index: BM25Index,
        vector_store: VectorStore,
        embedding_model: EmbeddingModel,
        rrf_k: int = 60,
    ):
        self.bm25_index = bm25_index
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        self.rrf_k = rrf_k

    def _reciprocal_rank_fusion(self, results_list: List[List[Tuple[Chunk, float]]], k: int = 60) -> List[Tuple[Chunk, float]]:
        chunk_map: Dict[str, Chunk] = {}
        rrf_scores: Dict[str, float] = {}

        for results in results_list:
            for rank, (chunk, _score) in enumerate(results, 1):
                chunk_id = chunk.chunk_id
                if chunk_id not in chunk_map:
                    chunk_map[chunk_id] = chunk
                    rrf_scores[chunk_id] = 0.0
                
                rrf_scores[chunk_id] += 1.0 / (k + rank)

        sorted_results = sorted(
            [(chunk_map[chunk_id], score) for chunk_id, score in rrf_scores.items()],
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_results

    def search(
        self,
        query: str,
        bm25_top_k: int = 50,
        vector_top_k: int = 50,
        fusion_top_k: int = 50,
    ) -> List[Tuple[Chunk, float]]:
        bm25_results = self.bm25_index.search(query, top_k=bm25_top_k)
        
        # Do not let dense search fabricate relevance for an out-of-domain query.
        # A vector database always returns nearest neighbours; lexical evidence is
        # required before those neighbours are allowed into the answer pipeline.
        if not bm25_results:
            return []
        query_vector = self.embedding_model.encode_query(query)
        vector_results = self.vector_store.search(query_vector, top_k=vector_top_k)
        
        fused_results = self._reciprocal_rank_fusion(
            [bm25_results, vector_results], k=self.rrf_k
        )
        return fused_results[:fusion_top_k]
