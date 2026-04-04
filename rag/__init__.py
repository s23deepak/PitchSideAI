"""
Advanced RAG strategies for PitchSide AI.
Implements hybrid search, semantic reranking, and multi-strategy retrieval.
"""
import logging
import json
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

import boto3
import httpx
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from config import (
    AWS_REGION, OPENSEARCH_ENDPOINT, OPENSEARCH_INDEX, EMBEDDING_MODEL,
    LLM_BACKEND, OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL,
    OPENAI_API_KEY, OPENAI_EMBED_MODEL,
    VLLM_BASE_URL, VLLM_EMBED_MODEL,
)

logger = logging.getLogger(__name__)


def _has_configured_opensearch_endpoint(endpoint: Optional[str]) -> bool:
    """Return True only for real, non-placeholder OpenSearch endpoints."""
    if not endpoint:
        return False

    normalized = endpoint.strip().lower()
    placeholder_markers = (
        "your-opensearch-endpoint",
        "your-endpoint",
        "example"
    )
    return not any(marker in normalized for marker in placeholder_markers)


class RAGStrategy(str, Enum):
    """Available RAG retrieval strategies."""
    SEMANTIC = "semantic"  # Pure semantic similarity
    KEYWORD = "keyword"  # BM25 keyword search
    HYBRID = "hybrid"  # Combined semantic + keyword
    CROSS_ENCODER = "cross_encoder"  # With reranking


@dataclass
class RetrievedDocument:
    """Structure for retrieved documents."""
    doc_id: str
    text: str
    score: float
    metadata: Dict[str, Any]
    strategy_used: str


class AdvancedRAGRetriever:
    """
    Advanced RAG retrieving with multiple strategies:
    1. Semantic search (vector similarity)
    2. Keyword search (BM25)
    3. Hybrid (combination)
    4. Cross-encoder reranking
    """

    def __init__(self):
        if LLM_BACKEND == "bedrock":
            self.bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        else:
            self.bedrock_client = None

        # Initialize OpenSearch client
        credentials = boto3.Session().get_credentials()
        if credentials and _has_configured_opensearch_endpoint(OPENSEARCH_ENDPOINT):
            awsauth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                AWS_REGION,
                "es",
                session_token=credentials.token
            )
            self.os_client = OpenSearch(
                hosts=[{"host": OPENSEARCH_ENDPOINT, "port": 443}],
                http_auth=awsauth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection
            )
        else:
            if OPENSEARCH_ENDPOINT and not _has_configured_opensearch_endpoint(OPENSEARCH_ENDPOINT):
                logger.warning("OpenSearch endpoint is using a placeholder value; falling back to local RAG store")
            self.os_client = None
            self.local_store: List[Dict[str, Any]] = []

    def _embed_text(self, text: str) -> List[float]:
        """Generate embeddings using configured backend."""
        if LLM_BACKEND in ("ollama", "openai", "vllm"):
            if LLM_BACKEND == "ollama":
                url = f"{OLLAMA_BASE_URL}/api/embed"
                payload = {"model": OLLAMA_EMBED_MODEL, "input": text}
                headers = {}
            elif LLM_BACKEND == "openai":
                url = "https://api.openai.com/v1/embeddings"
                payload = {"model": OPENAI_EMBED_MODEL, "input": text}
                headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            else:  # vllm
                url = f"{VLLM_BASE_URL}/v1/embeddings"
                payload = {"model": VLLM_EMBED_MODEL, "input": text}
                headers = {}

            response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            # Ollama uses "embeddings[0]", OpenAI/vLLM use "data[0].embedding"
            if "embeddings" in data:
                return data["embeddings"][0]
            return data["data"][0]["embedding"]

        body = json.dumps({"inputText": text})
        response = self.bedrock_client.invoke_model(
            body=body,
            modelId=EMBEDDING_MODEL,
            accept="application/json",
            contentType="application/json"
        )
        response_body = json.loads(response.get("body").read())
        return response_body.get("embedding", [])

    async def retrieve(
        self,
        query: str,
        strategy: RAGStrategy = RAGStrategy.HYBRID,
        top_k: int = 5,
        include_metadata: bool = True
    ) -> List[RetrievedDocument]:
        """
        Retrieve documents using specified strategy.
        """
        if strategy == RAGStrategy.SEMANTIC:
            return await self._semantic_search(query, top_k, include_metadata)
        elif strategy == RAGStrategy.KEYWORD:
            return await self._keyword_search(query, top_k, include_metadata)
        elif strategy == RAGStrategy.HYBRID:
            return await self._hybrid_search(query, top_k, include_metadata)
        elif strategy == RAGStrategy.CROSS_ENCODER:
            # Hybrid first, then rerank
            results = await self._hybrid_search(query, top_k * 2, include_metadata)
            return await self._rerank_with_cross_encoder(query, results, top_k)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    async def _semantic_search(
        self,
        query: str,
        top_k: int = 5,
        include_metadata: bool = True
    ) -> List[RetrievedDocument]:
        """Pure semantic search using vector similarity."""
        if not self.os_client:
            return await self._local_semantic_search(query, top_k)

        try:
            query_vector = self._embed_text(query)
            search_body = {
                "size": top_k,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_vector,
                            "k": top_k
                        }
                    }
                }
            }

            response = self.os_client.search(body=search_body, index=OPENSEARCH_INDEX)
            hits = response.get("hits", {}).get("hits", [])

            results = []
            for hit in hits:
                results.append(RetrievedDocument(
                    doc_id=hit["_id"],
                    text=hit["_source"].get("text", ""),
                    score=hit.get("_score", 0.0),
                    metadata=hit["_source"].get("metadata", {}),
                    strategy_used=RAGStrategy.SEMANTIC.value
                ))
            return results

        except Exception as exc:
            logger.error(f"Semantic search failed: {exc}")
            return []

    async def _keyword_search(
        self,
        query: str,
        top_k: int = 5,
        include_metadata: bool = True
    ) -> List[RetrievedDocument]:
        """BM25 keyword search."""
        if not self.os_client:
            return await self._local_keyword_search(query, top_k)

        try:
            search_body = {
                "size": top_k,
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["text^2", "metadata.team"]  # Boost team field
                    }
                }
            }

            response = self.os_client.search(body=search_body, index=OPENSEARCH_INDEX)
            hits = response.get("hits", {}).get("hits", [])

            results = []
            for hit in hits:
                results.append(RetrievedDocument(
                    doc_id=hit["_id"],
                    text=hit["_source"].get("text", ""),
                    score=hit.get("_score", 0.0),
                    metadata=hit["_source"].get("metadata", {}),
                    strategy_used=RAGStrategy.KEYWORD.value
                ))
            return results

        except Exception as exc:
            logger.error(f"Keyword search failed: {exc}")
            return []

    async def _hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        include_metadata: bool = True
    ) -> List[RetrievedDocument]:
        """Hybrid search combining semantic and keyword."""
        semantic_results = await self._semantic_search(query, top_k, include_metadata)
        keyword_results = await self._keyword_search(query, top_k, include_metadata)

        # Merge and deduplicate
        merged = {}
        for doc in semantic_results:
            merged[doc.doc_id] = doc

        for doc in keyword_results:
            if doc.doc_id in merged:
                # Average the scores
                merged[doc.doc_id].score = (merged[doc.doc_id].score + doc.score) / 2
            else:
                merged[doc.doc_id] = doc

        # Sort by score and return top_k
        sorted_results = sorted(merged.values(), key=lambda x: x.score, reverse=True)
        return sorted_results[:top_k]

    async def _rerank_with_cross_encoder(
        self,
        query: str,
        candidates: List[RetrievedDocument],
        top_k: int
    ) -> List[RetrievedDocument]:
        """Rerank candidates using cross-encoder logic."""
        # Reranking can be implemented using Bedrock or MLFlow endpoints
        # For now, we'll enhance scoring based on query relevance
        try:
            for doc in candidates:
                # Simple relevance boost based on exact/partial matches
                relevance_boost = 0.0
                query_terms = set(query.lower().split())
                doc_terms = set(doc.text.lower().split())
                match_ratio = len(query_terms & doc_terms) / len(query_terms)
                relevance_boost = match_ratio * 0.3  # 30% boost for relevance

                doc.score = doc.score * (1.0 + relevance_boost)

            # Re-sort
            candidates.sort(key=lambda x: x.score, reverse=True)
            return candidates[:top_k]

        except Exception as exc:
            logger.error(f"Reranking failed: {exc}")
            return candidates[:top_k]

    async def _local_semantic_search(
        self,
        query: str,
        top_k: int
    ) -> List[RetrievedDocument]:
        """Fallback local semantic search for dev."""
        results = []
        for doc in self.local_store[:top_k]:
            results.append(RetrievedDocument(
                doc_id=doc.get("id", ""),
                text=doc.get("text", ""),
                score=1.0,
                metadata=doc.get("metadata", {}),
                strategy_used=RAGStrategy.SEMANTIC.value
            ))
        return results

    async def _local_keyword_search(
        self,
        query: str,
        top_k: int
    ) -> List[RetrievedDocument]:
        """Fallback local keyword search for dev."""
        query_terms = set(query.lower().split())
        results = []

        for doc in self.local_store:
            doc_terms = set(doc.get("text", "").lower().split())
            matches = len(query_terms & doc_terms)
            if matches > 0:
                results.append(RetrievedDocument(
                    doc_id=doc.get("id", ""),
                    text=doc.get("text", ""),
                    score=float(matches),
                    metadata=doc.get("metadata", {}),
                    strategy_used=RAGStrategy.KEYWORD.value
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    async def index_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Index a new document."""
        if not self.os_client:
            self.local_store.append({
                "id": doc_id,
                "text": text,
                "metadata": metadata or {}
            })
            return True

        try:
            embedding = self._embed_text(text)
            document = {
                "text": text,
                "embedding": embedding,
                "metadata": metadata or {}
            }

            self.os_client.index(index=OPENSEARCH_INDEX, body=document, id=doc_id)
            return True

        except Exception as exc:
            logger.error(f"Failed to index document {doc_id}: {exc}")
            return False


# Global retriever instance
_retriever: Optional[AdvancedRAGRetriever] = None


def get_rag_retriever() -> AdvancedRAGRetriever:
    """Get or create the advanced RAG retriever."""
    global _retriever
    if _retriever is None:
        _retriever = AdvancedRAGRetriever()
    return _retriever
