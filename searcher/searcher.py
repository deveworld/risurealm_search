"""캐릭터 검색 (하이브리드: 벡터 + BM25)"""

import math
import re
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from .embedder import VoyageEmbedder
from .models import SearchQuery, SearchResult, SearchResponse
from .bm25 import BM25Index
from .synonyms import matches_with_synonyms


def tokenize_query(query: str, min_length: int = 1) -> list[str]:
    """검색어를 토큰으로 분리 (한글, 영어, 숫자)

    Args:
        query: 검색어
        min_length: 최소 토큰 길이 (기본 1, 1글자 허용)

    Returns:
        토큰 목록
    """
    query = query.lower()
    tokens = re.findall(r'[가-힣]+|[a-z]+|[0-9]+', query)
    return [t for t in tokens if len(t) >= min_length]


def calculate_keyword_boost(query_tokens: list[str], name: str, document: str) -> float:
    """키워드 매칭 부스트 계산

    이름/요약/설명/태그 위치에 따라 다른 가중치 적용
    """
    if not query_tokens:
        return 0.0

    # 문서에서 이름/요약/설명 분리
    name_lower = name.lower()
    doc_lower = document.lower()

    # 요약과 설명, 태그 추출
    summary = ""
    description = ""
    tags_text = ""
    for line in document.split("\n"):
        if line.startswith("요약:"):
            summary = line[3:].lower()
        elif line.startswith("설명:"):
            description = line[3:].lower()
        elif line.startswith("태그:"):
            tags_text = line[3:].lower()

    total_boost = 0.0
    matched_tokens = 0

    for token in query_tokens:
        token_boost = 0.0
        token_matched = False

        # 위치별 가중치 (중복 적용, elif 제거)
        if matches_with_synonyms(name_lower, token):
            token_boost += 0.4   # 이름 매칭
            token_matched = True
        if matches_with_synonyms(summary, token):
            token_boost += 0.8   # 요약 매칭: 최고 가중치
            token_matched = True
        if matches_with_synonyms(description, token):
            token_boost += 0.3   # 설명 매칭
            token_matched = True
        if matches_with_synonyms(tags_text, token):
            token_boost += 0.5   # 태그 매칭
            token_matched = True

        # 위 어디에도 매칭 안 됐지만 문서 어딘가에 있으면
        if not token_matched and matches_with_synonyms(doc_lower, token):
            token_boost += 0.2   # 기타 영역 매칭
            token_matched = True

        if token_matched:
            matched_tokens += 1

        total_boost += token_boost

    # 토큰 수로 정규화
    normalized_boost = total_boost / len(query_tokens)

    # 키워드 커버리지 보정
    coverage_ratio = matched_tokens / len(query_tokens)
    normalized_boost *= coverage_ratio

    return normalized_boost


def parse_download_count(download_str: str) -> int:
    """다운로드 문자열을 숫자로 변환 (예: '623.9k' -> 623900, '1,234' -> 1234)"""
    if not download_str:
        return 0

    download_str = download_str.strip().lower()
    # 쉼표 제거
    download_str = download_str.replace(',', '')

    try:
        if download_str.endswith('k'):
            return int(float(download_str[:-1]) * 1000)
        elif download_str.endswith('m'):
            return int(float(download_str[:-1]) * 1000000)
        else:
            return int(float(download_str))
    except (ValueError, TypeError):
        return 0


def reciprocal_rank_fusion(
    rankings: list[list[tuple[str, float]]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """RRF (Reciprocal Rank Fusion)로 여러 랭킹 결과 융합

    Args:
        rankings: 각 검색 방법의 결과 [(uuid, score), ...]
        k: RRF 상수 (기본 60)

    Returns:
        융합된 결과 [(uuid, rrf_score), ...]
    """
    rrf_scores: dict[str, float] = {}

    for ranking in rankings:
        for rank, (uuid, _) in enumerate(ranking, start=1):
            if uuid not in rrf_scores:
                rrf_scores[uuid] = 0.0
            rrf_scores[uuid] += 1.0 / (k + rank)

    # 점수 내림차순 정렬
    results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return results


class CharacterSearcher:
    """캐릭터 검색 엔진 (하이브리드: 벡터 + BM25)"""

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

        # BM25 인덱스
        self.bm25_index = BM25Index(data_dir)
        if not self.bm25_index.load():
            print("⚠️  BM25 인덱스가 없습니다. `python main.py index --rebuild` 실행 필요")

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

    def _metadata_to_result(self, metadata: dict, document: str, score: float) -> SearchResult:
        """메타데이터를 SearchResult로 변환"""
        # tags는 쉼표로 구분된 문자열
        tags = metadata.get("tags", "")
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]

        return SearchResult(
            uuid=metadata["uuid"],
            name=metadata["name"],
            authorname=metadata.get("authorname", ""),
            desc=document or "",
            download=metadata.get("download", "0"),
            url=f"{self.REALM_URL}/{metadata['uuid']}",
            img=metadata.get("img", ""),
            content_rating=metadata.get("content_rating", "unknown"),
            character_gender=metadata.get("character_gender", "other"),
            language=metadata.get("language", "english"),
            tags=tags_list,
            source=metadata.get("source") or None,
            score=score,
        )

    def _vector_search(
        self,
        query: str,
        where_filter: Optional[dict],
        top_k: int = 100,
    ) -> list[tuple[str, float]]:
        """벡터 검색 실행"""
        query_embedding = self.embedder.embed_query(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["distances"],
        )

        ranking = []
        ids = results["ids"]
        distances = results["distances"]
        if ids and ids[0]:
            for i, uuid in enumerate(ids[0]):
                distance = distances[0][i] if distances and distances[0] else 0
                similarity = 1 - distance  # cosine distance -> similarity
                ranking.append((uuid, similarity))

        return ranking

    def _bm25_search(self, query: str, top_k: int = 100) -> list[tuple[str, float]]:
        """BM25 키워드 검색 실행"""
        if self.bm25_index.bm25 is None:
            return []
        return self.bm25_index.search(query, top_k=top_k)

    def search(self, query: SearchQuery) -> SearchResponse:
        """하이브리드 검색 실행 (벡터 + BM25 + RRF)"""
        where_filter = self._build_where_filter(query)
        # 필터링으로 인한 손실을 고려하여 더 많이 가져옴
        fetch_limit = max((query.limit + query.offset) * 3, 100)

        # 검색어가 있으면 하이브리드 검색
        if query.q:
            query_tokens = tokenize_query(query.q)

            # 1. 벡터 검색
            vector_results = self._vector_search(query.q, where_filter, top_k=fetch_limit)

            # 2. BM25 검색
            bm25_results = self._bm25_search(query.q, top_k=fetch_limit)

            # 3. RRF로 융합 (BM25 없어도 단일 랭킹으로 RRF 적용하여 점수 스케일 통일)
            if bm25_results:
                fused_results = reciprocal_rank_fusion([vector_results, bm25_results])
            else:
                # BM25 없어도 RRF 형식으로 변환 (점수 스케일 통일)
                fused_results = reciprocal_rank_fusion([vector_results])

            # 4. 융합된 UUID로 메타데이터 조회
            fused_uuids = [uuid for uuid, _ in fused_results[:fetch_limit]]

            if not fused_uuids:
                return SearchResponse(total=0, results=[], query=query)

            # Chroma에서 메타데이터 조회
            chroma_results = self.collection.get(
                ids=fused_uuids,
                include=["documents", "metadatas"],
            )

            # UUID -> 메타데이터 매핑
            metadata_map: dict[str, dict] = {}
            document_map: dict[str, str] = {}
            chroma_metadatas = chroma_results["metadatas"]
            chroma_documents = chroma_results["documents"]
            for i, uuid in enumerate(chroma_results["ids"]):
                if chroma_metadatas:
                    metadata_map[uuid] = dict(chroma_metadatas[i])
                if chroma_documents:
                    document_map[uuid] = str(chroma_documents[i]) if chroma_documents[i] else ""

            # RRF 점수 매핑
            rrf_score_map = {uuid: score for uuid, score in fused_results}

            # 결과 변환 (필터링 적용)
            items = []
            for uuid in fused_uuids:
                if uuid not in metadata_map:
                    continue

                metadata = metadata_map[uuid]
                document = document_map.get(uuid, "")

                # 필터 조건 확인 (BM25 결과는 필터 미적용이므로 여기서 필터링)
                if where_filter:
                    if not self._check_filter(metadata, where_filter):
                        continue

                # download 가중치 적용 (영향력 강화)
                downloads = parse_download_count(metadata.get("download", "0"))
                # log 스케일로 변환 후 정규화 (0~1 범위)
                # 100 -> 0.2, 10000 -> 0.4, 100000 -> 0.5, 1000000 -> 0.6
                download_boost = math.log10(downloads + 10) / 10

                # 키워드 매칭 부스트
                name = metadata.get("name", "")
                keyword_boost = calculate_keyword_boost(query_tokens, name, document)

                # 최종 점수 계산
                # RRF 점수: 약 0.01~0.03 (단일), 0.02~0.06 (융합)
                # 키워드 부스트: 0~2 (정규화 전)
                # 다운로드 부스트: 0.2~0.6
                rrf_score = rrf_score_map.get(uuid, 0)

                # 가중치 조정: RRF(기본) + 키워드(중요) + 다운로드(적절히 반영)
                score = (
                    rrf_score * 10          # RRF: 0.1~0.6
                    + keyword_boost * 0.3   # 키워드: 0~0.6
                    + download_boost * 0.2  # 다운로드: 0.04~0.12
                )

                items.append(self._metadata_to_result(metadata, document, score))

            # 점수순 재정렬
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
            result_ids = results["ids"]
            result_metadatas = results["metadatas"]
            result_documents = results["documents"]
            if result_ids:
                for i, uuid in enumerate(result_ids):
                    metadata = dict(result_metadatas[i]) if result_metadatas else {}
                    document = str(result_documents[i]) if result_documents and result_documents[i] else ""
                    items.append(self._metadata_to_result(metadata, document, 0.0))

            items = items[query.offset : query.offset + query.limit]

        return SearchResponse(
            total=len(items),
            results=items[:query.limit],
            query=query,
        )

    def _check_filter(self, metadata: dict, where_filter: dict) -> bool:
        """메타데이터가 필터 조건을 만족하는지 확인"""
        if "$and" in where_filter:
            return all(self._check_filter(metadata, cond) for cond in where_filter["$and"])

        for key, value in where_filter.items():
            if key.startswith("$"):
                continue

            meta_value = metadata.get(key)

            if isinstance(value, dict):
                if "$in" in value:
                    if meta_value not in value["$in"]:
                        return False
            else:
                if meta_value != value:
                    return False

        return True

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
