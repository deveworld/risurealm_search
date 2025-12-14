"""BM25 키워드 검색 엔진"""

import pickle
import re
from pathlib import Path
from typing import Optional

from rank_bm25 import BM25Okapi

from .synonyms import expand_synonyms


def tokenize(text: str, min_length: int = 2) -> list[str]:
    """텍스트를 토큰으로 분리 (한글, 영어, 숫자)

    Args:
        text: 입력 텍스트
        min_length: 최소 토큰 길이 (기본 2, 1로 설정하면 1글자도 허용)

    Returns:
        토큰 목록
    """
    if not text:
        return []
    text = text.lower()
    # 한글, 영어, 숫자 추출
    tokens = re.findall(r'[가-힣]+|[a-z]+|[0-9]+', text)
    # 최소 길이 필터
    return [t for t in tokens if len(t) >= min_length]


class BM25Index:
    """BM25 인덱스"""

    def __init__(self, data_dir: Path = Path("data")):
        self.data_dir = data_dir
        self.index_path = data_dir / "bm25_index.pkl"

        self.bm25: Optional[BM25Okapi] = None
        self.doc_ids: list[str] = []  # UUID 목록
        self.corpus: list[list[str]] = []  # 토큰화된 문서들

    def build_index(self, documents: list[dict]):
        """인덱스 구축

        Args:
            documents: [{"uuid": str, "text": str}, ...]
        """
        self.doc_ids = []
        self.corpus = []

        for doc in documents:
            self.doc_ids.append(doc["uuid"])
            tokens = tokenize(doc["text"])
            self.corpus.append(tokens)

        self.bm25 = BM25Okapi(self.corpus)
        print(f"BM25 인덱스 구축 완료: {len(self.doc_ids)}개 문서")

    def save(self):
        """인덱스 저장"""
        data = {
            "doc_ids": self.doc_ids,
            "corpus": self.corpus,
        }
        with open(self.index_path, "wb") as f:
            pickle.dump(data, f)
        print(f"BM25 인덱스 저장: {self.index_path}")

    def load(self) -> bool:
        """인덱스 로드"""
        if not self.index_path.exists():
            return False

        with open(self.index_path, "rb") as f:
            data = pickle.load(f)

        self.doc_ids = data["doc_ids"]
        self.corpus = data["corpus"]
        self.bm25 = BM25Okapi(self.corpus)
        print(f"BM25 인덱스 로드: {len(self.doc_ids)}개 문서")
        return True

    def search(self, query: str, top_k: int = 100) -> list[tuple[str, float]]:
        """검색 실행

        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 결과 수

        Returns:
            [(uuid, score), ...] 점수 내림차순
        """
        if self.bm25 is None:
            return []

        # 쿼리 토큰화 + 동의어 확장
        query_tokens = tokenize(query)
        query_tokens = expand_synonyms(query_tokens)

        if not query_tokens:
            return []

        # BM25 점수 계산
        scores = self.bm25.get_scores(query_tokens)

        # 점수와 UUID 매핑
        results = [(self.doc_ids[i], scores[i]) for i in range(len(scores))]

        # 점수 내림차순 정렬
        results.sort(key=lambda x: x[1], reverse=True)

        # 점수가 0보다 큰 결과만 반환
        results = [(uuid, score) for uuid, score in results if score > 0]

        return results[:top_k]


def format_bm25_document(char: dict) -> str:
    """캐릭터 정보를 BM25 검색용 문서로 변환"""
    parts = [
        char.get("name", ""),
        char.get("authorname", ""),
    ]

    # LLM 태그
    llm_tags = char.get("llm_tags") or {}
    if llm_tags.get("summary"):
        # 요약은 중요하므로 반복
        parts.extend([llm_tags["summary"]] * 3)
    if llm_tags.get("description"):
        parts.append(llm_tags["description"])
    if llm_tags.get("source"):
        source_list = llm_tags["source"]
        if isinstance(source_list, list):
            parts.extend(source_list)
        elif source_list:
            parts.append(source_list)

    # 원본 태그 (중요)
    if char.get("tags"):
        parts.extend(char["tags"] * 2)

    # 설명
    if char.get("desc"):
        parts.append(char["desc"][:500])

    return " ".join(parts)
