from typing import Iterable

import httpx

from agent.settings import (
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EMBEDDING_SEND_DIMENSIONS,
    EMBEDDING_TIMEOUT,
)


class EmbeddingClient:
    def __init__(
        self,
        base_url: str = EMBEDDING_BASE_URL,
        model: str = EMBEDDING_MODEL,
        dimensions: int = EMBEDDING_DIMENSIONS,
        send_dimensions: bool = EMBEDDING_SEND_DIMENSIONS,
    ):
        self.base_url = base_url
        self.model = model
        self.dimensions = dimensions
        self.send_dimensions = send_dimensions

    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        values = list(texts)
        if not values:
            return []
        payload = {"model": self.model, "input": values, "encoding_format": "float"}
        if self.send_dimensions:
            payload["dimensions"] = self.dimensions
        response = httpx.post(
            f"{self.base_url}/embeddings",
            json=payload,
            headers={"Authorization": f"Bearer {EMBEDDING_API_KEY}"},
            timeout=EMBEDDING_TIMEOUT,
        )
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in data]

    def embed_query(self, text: str) -> list[float]:
        instruction = "Instruct: Retrieve relevant educational courses for the query.\nQuery: "
        return self.embed([instruction + text])[0]


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8g}" for value in values) + "]"
