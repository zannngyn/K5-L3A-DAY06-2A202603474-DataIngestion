"""Real embedding provider adapter (OpenRouter). Never falls back to mock vectors."""
import json
import logging
import os
import random
import time
import urllib.error
import urllib.request
from typing import Protocol

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/embeddings"
# Qwen3-Embedding: queries carry a one-sentence instruction, documents none (model card).
QUERY_INSTRUCTION = (
    "Given a question about an introductory sociology textbook, "
    "retrieve passages that answer the question"
)
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504, 529}


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class EmbeddingError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.retryable = retryable


class OpenRouterEmbedder:
    def __init__(self, model_name: str | None = None, dimensions: int = 4096, batch_size: int = 32,
                 max_retries: int = 5, timeout: float = 60.0) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.model_name = (model_name or os.getenv("EMBEDDING_MODEL", "")).strip()
        if not self.api_key:
            raise EmbeddingError("CONFIG_MISSING", "OPENROUTER_API_KEY is not set (starter/.env)")
        if not self.model_name:
            raise EmbeddingError("CONFIG_MISSING", "EMBEDDING_MODEL is not set (starter/.env)")
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.timeout = timeout
        self.usage = {"requests": 0, "prompt_tokens": 0, "cost": 0.0}

    def _post(self, inputs: list[str]) -> dict:
        body = json.dumps({
            "model": self.model_name,
            "input": inputs,
            "encoding_format": "float",
            "provider": {"data_collection": "deny"},
        }).encode()
        request = urllib.request.Request(OPENROUTER_URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode(errors="replace")
            raise EmbeddingError(f"HTTP_{exc.code}", detail, exc.code in _RETRYABLE_STATUS) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise EmbeddingError("NETWORK", str(exc), retryable=True) from exc
        except json.JSONDecodeError as exc:
            raise EmbeddingError("BAD_RESPONSE", "response is not JSON", retryable=True) from exc

    def _post_with_retry(self, inputs: list[str]) -> dict:
        for attempt in range(self.max_retries + 1):
            try:
                return self._post(inputs)
            except EmbeddingError as exc:
                if not exc.retryable or attempt == self.max_retries:
                    raise
                delay = min(30.0, 2 ** attempt) + random.uniform(0, 1)
                logger.warning("embedding attempt %d failed (%s); retrying in %.1fs", attempt + 1, exc.code, delay)
                time.sleep(delay)
        raise AssertionError("unreachable")

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(inputs), self.batch_size):
            batch = inputs[start:start + self.batch_size]
            payload = self._post_with_retry(batch)
            data = payload.get("data")
            if not isinstance(data, list) or len(data) != len(batch):
                raise EmbeddingError("BAD_RESPONSE",
                                     f"expected {len(batch)} embeddings, got {payload.get('error') or len(data or [])}")
            for item in sorted(data, key=lambda d: d["index"]):
                vec = item.get("embedding")
                if not isinstance(vec, list) or len(vec) != self.dimensions:
                    raise EmbeddingError("DIMENSION_MISMATCH",
                                         f"expected {self.dimensions} dims, got {len(vec) if isinstance(vec, list) else type(vec).__name__}")
                vectors.append(vec)
            usage = payload.get("usage") or {}
            self.usage["requests"] += 1
            self.usage["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            self.usage["cost"] += float(usage.get("cost") or 0.0)
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if any(not t.strip() for t in texts):
            raise EmbeddingError("EMPTY_INPUT", "cannot embed empty text")
        return self._embed(texts)

    def embed_query(self, question: str) -> list[float]:
        if not question.strip():
            raise EmbeddingError("EMPTY_INPUT", "empty question")
        return self._embed([f"Instruct: {QUERY_INSTRUCTION}\nQuery:{question}"])[0]
