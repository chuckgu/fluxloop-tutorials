from __future__ import annotations

import re
from typing import List

import fluxloop
import numpy as np
import openai
import requests
from langchain_core.tools import tool

FAQ_URL = "https://storage.googleapis.com/benchmarks-artifacts/travel-db/swiss_faq.md"


class VectorStoreRetriever:
    def __init__(self, docs: List[dict], vectors: List[List[float]], oai_client):
        self._arr = np.array(vectors)
        self._docs = docs
        self._client = oai_client

    @classmethod
    def from_docs(cls, docs, oai_client):
        embeddings = oai_client.embeddings.create(
            model="text-embedding-3-small",
            input=[doc["page_content"] for doc in docs],
        )
        vectors = [emb.embedding for emb in embeddings.data]
        return cls(docs, vectors, oai_client)

    @fluxloop.trace(name="policy_vector_query")
    def query(self, query: str, k: int = 5) -> List[dict]:
        embed = self._client.embeddings.create(
            model="text-embedding-3-small",
            input=[query],
        )
        scores = np.array(embed.data[0].embedding) @ self._arr.T
        top_k_idx = np.argpartition(scores, -k)[-k:]
        top_k_idx_sorted = top_k_idx[np.argsort(-scores[top_k_idx])]
        return [
            {**self._docs[idx], "similarity": float(scores[idx])}
            for idx in top_k_idx_sorted
        ]


_retriever: VectorStoreRetriever | None = None


@fluxloop.trace(name="load_policy_retriever")
def _get_retriever() -> VectorStoreRetriever:
    global _retriever
    if _retriever is not None:
        return _retriever

    response = requests.get(FAQ_URL, timeout=30)
    response.raise_for_status()
    faq_text = response.text
    docs = [{"page_content": txt} for txt in re.split(r"(?=\n##)", faq_text)]
    client = openai.Client()
    _retriever = VectorStoreRetriever.from_docs(docs, client)
    return _retriever


@tool
@fluxloop.trace(name="lookup_policy")
def lookup_policy(query: str) -> str:
    """Consult the company policies to check whether certain options are permitted.
    Use this before making any flight changes performing other 'write' events."""
    retriever = _get_retriever()
    docs = retriever.query(query, k=2)
    return "\n\n".join([doc["page_content"] for doc in docs])

