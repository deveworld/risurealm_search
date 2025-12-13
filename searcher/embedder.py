"""Voyage AI 임베딩 생성"""

import os
import time
from typing import Optional

import httpx


class VoyageEmbedder:
    """Voyage AI 임베딩 클라이언트"""

    BASE_URL = "https://api.voyageai.com/v1/embeddings"
    DEFAULT_MODEL = "voyage-3-lite"  # 빠르고 저렴, 다국어 지원

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        batch_size: int = 128,  # Voyage AI 최대 128
    ):
        self.api_key = api_key or os.getenv("VOYAGE_API_KEY")
        if not self.api_key:
            raise ValueError("VOYAGE_API_KEY 환경변수가 필요합니다")

        self.model = model
        self.batch_size = batch_size
        self._client = httpx.Client(timeout=60.0)

    def embed_single(self, text: str, input_type: str = "document") -> list[float]:
        """단일 텍스트 임베딩"""
        result = self.embed_batch([text], input_type=input_type)
        return result[0]

    def embed_query(self, text: str) -> list[float]:
        """검색 쿼리 임베딩 (input_type=query)"""
        return self.embed_single(text, input_type="query")

    def embed_batch(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        """배치 임베딩 (최대 128개)"""
        if not texts:
            return []

        response = self._client.post(
            self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": texts,
                "input_type": input_type,
            },
        )
        response.raise_for_status()
        data = response.json()

        # 결과를 인덱스 순서대로 정렬
        embeddings = [None] * len(texts)
        for item in data["data"]:
            embeddings[item["index"]] = item["embedding"]

        return embeddings

    def embed_all(
        self,
        texts: list[str],
        on_progress: Optional[callable] = None,
        delay: float = 0.1,
    ) -> list[list[float]]:
        """대량 텍스트 임베딩 (배치 처리)"""
        all_embeddings = []
        total = len(texts)

        for i in range(0, total, self.batch_size):
            batch = texts[i : i + self.batch_size]
            embeddings = self.embed_batch(batch)
            all_embeddings.extend(embeddings)

            if on_progress:
                on_progress(min(i + self.batch_size, total), total)

            if i + self.batch_size < total:
                time.sleep(delay)

        return all_embeddings

    def close(self):
        """클라이언트 종료"""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
