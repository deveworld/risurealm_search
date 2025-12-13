"""캐릭터 검색"""

import math
import re
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from .embedder import VoyageEmbedder
from .models import SearchQuery, SearchResult, SearchResponse


def tokenize_query(query: str) -> list[str]:
    """검색어를 토큰으로 분리 (한글, 영어, 숫자)"""
    # 소문자 변환 및 특수문자 제거
    query = query.lower()
    # 한글, 영어, 숫자만 추출
    tokens = re.findall(r'[가-힣]+|[a-z]+|[0-9]+', query)
    # 1글자 토큰 제외 (너무 일반적)
    return [t for t in tokens if len(t) > 1]


def calculate_keyword_boost(query_tokens: list[str], name: str, document: str) -> float:
    """키워드 매칭 부스트 계산"""
    if not query_tokens:
        return 0.0

    name_lower = name.lower()
    doc_lower = document.lower()

    name_matches = 0
    doc_matches = 0

    for token in query_tokens:
        if token in name_lower:
            name_matches += 1
        if token in doc_lower:
            doc_matches += 1

    # 이름 매칭은 더 높은 가중치
    name_ratio = name_matches / len(query_tokens) if query_tokens else 0
    doc_ratio = doc_matches / len(query_tokens) if query_tokens else 0

    # 이름 매칭: 최대 30% 부스트, 문서 매칭: 최대 15% 부스트
    return name_ratio * 0.3 + doc_ratio * 0.15


def parse_download_count(download_str: str) -> int:
    """다운로드 문자열을 숫자로 변환 (예: '623.9k' -> 623900)"""
    if not download_str:
        return 0

    download_str = download_str.strip().lower()

    try:
        if download_str.endswith('k'):
            return int(float(download_str[:-1]) * 1000)
        elif download_str.endswith('m'):
            return int(float(download_str[:-1]) * 1000000)
        else:
            return int(float(download_str))
    except (ValueError, TypeError):
        return 0


class CharacterSearcher:
    """캐릭터 검색 엔진"""

    COLLECTION_NAME = "risurealm_characters"
    REALM_URL = "https://realm.risuai.net/character"

    def __init__(
        self,
        data_dir: Path = Path("data"),
        embedder: Optional[VoyageEmbedder] = None,
    ):
        self.data_dir = data_dir
        self.db_path = data_dir / "chroma_db"

        # Chroma 클라이언트
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(anonymized_telemetry=False),
        )

        self.collection = self.client.get_collection(self.COLLECTION_NAME)

        # 임베딩 생성기
        self._embedder = embedder
        self._own_embedder = False

    @property
    def embedder(self) -> VoyageEmbedder:
        if self._embedder is None:
            self._embedder = VoyageEmbedder()
            self._own_embedder = True
        return self._embedder

    def _build_where_filter(self, query: SearchQuery) -> Optional[dict]:
        """Chroma where 필터 생성"""
        conditions = []

        # 콘텐츠 등급 (여러 개 선택 가능)
        if query.ratings:
            if len(query.ratings) == 1:
                conditions.append({"content_rating": query.ratings[0]})
            else:
                conditions.append({"content_rating": {"$in": query.ratings}})

        # 성별 (여러 개 선택 가능)
        if query.genders:
            if len(query.genders) == 1:
                conditions.append({"character_gender": query.genders[0]})
            else:
                conditions.append({"character_gender": {"$in": query.genders}})

        # 언어 (여러 개 선택 가능)
        if query.languages:
            if len(query.languages) == 1:
                conditions.append({"language": query.languages[0]})
            else:
                conditions.append({"language": {"$in": query.languages}})

        if not conditions:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}

    def _filter_by_genres(self, items: list[SearchResult], genres: list[str]) -> list[SearchResult]:
        """장르 필터링 (포스트 필터링)"""
        if not genres:
            return items
        # 선택된 장르 중 하나라도 포함되어 있으면 통과
        return [item for item in items if any(g in item.genres for g in genres)]

    def _metadata_to_result(self, metadata: dict, document: str, score: float) -> SearchResult:
        """메타데이터를 SearchResult로 변환"""
        # genres는 쉼표로 구분된 문자열
        genres = metadata.get("genres", "")
        genres_list = [g.strip() for g in genres.split(",") if g.strip()]

        return SearchResult(
            uuid=metadata["uuid"],
            name=metadata["name"],
            authorname=metadata.get("authorname", ""),
            desc=document or "",
            download=metadata.get("download", "0"),
            url=f"{self.REALM_URL}/{metadata['uuid']}",
            content_rating=metadata.get("content_rating", "unknown"),
            genres=genres_list,
            character_gender=metadata.get("character_gender", "other"),
            language=metadata.get("language", "english"),
            summary="",  # document에서 추출 가능
            source=metadata.get("source") or None,
            score=score,
        )

    def search(self, query: SearchQuery) -> SearchResponse:
        """검색 실행"""
        where_filter = self._build_where_filter(query)

        # 장르 필터가 있으면 더 많은 결과를 가져와서 포스트 필터링
        fetch_multiplier = 5 if query.genres else 1
        fetch_limit = (query.limit + query.offset) * fetch_multiplier

        # 검색어가 있으면 벡터 검색
        if query.q:
            query_embedding = self.embedder.embed_query(query.q)
            query_tokens = tokenize_query(query.q)

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=fetch_limit,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            # 결과 변환
            items = []
            if results["ids"] and results["ids"][0]:
                for i, uuid in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i]
                    document = results["documents"][0][i] if results["documents"] else ""
                    distance = results["distances"][0][i] if results["distances"] else 0

                    # cosine distance -> similarity score
                    similarity = 1 - distance

                    # download 가중치 적용
                    downloads = parse_download_count(metadata.get("download", "0"))
                    download_boost = math.log10(downloads + 10) / 10  # 0.1 ~ 0.7 범위

                    # 키워드 매칭 부스트
                    name = metadata.get("name", "")
                    keyword_boost = calculate_keyword_boost(query_tokens, name, document)

                    # 최종 점수: 유사도 * (1 + 다운로드 부스트 + 키워드 부스트)
                    score = similarity * (1 + download_boost * 0.3 + keyword_boost)

                    items.append(self._metadata_to_result(metadata, document, score))

            # 장르 포스트 필터링
            items = self._filter_by_genres(items, query.genres)

            # 점수순 재정렬 (download 가중치 반영)
            items.sort(key=lambda x: x.score, reverse=True)

            # offset 적용
            items = items[query.offset:]

        else:
            # 검색어 없으면 필터만 적용
            results = self.collection.get(
                where=where_filter,
                limit=fetch_limit,
                include=["documents", "metadatas"],
            )

            items = []
            if results["ids"]:
                for i, uuid in enumerate(results["ids"]):
                    metadata = results["metadatas"][i]
                    document = results["documents"][i] if results["documents"] else ""
                    items.append(self._metadata_to_result(metadata, document, 0.0))

            # 장르 포스트 필터링
            items = self._filter_by_genres(items, query.genres)
            items = items[query.offset : query.offset + query.limit]

        return SearchResponse(
            total=len(items),
            results=items[:query.limit],
            query=query,
        )

    def search_simple(
        self,
        q: str,
        rating: Optional[str] = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """간단한 검색 인터페이스"""
        ratings = [rating] if rating else []
        query = SearchQuery(q=q, ratings=ratings, limit=limit)
        response = self.search(query)
        return response.results

    def close(self):
        """리소스 정리"""
        if self._own_embedder and self._embedder:
            self._embedder.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
