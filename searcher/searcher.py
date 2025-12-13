"""캐릭터 검색"""

from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from .embedder import VoyageEmbedder
from .models import SearchQuery, SearchResult, SearchResponse


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

        # 콘텐츠 등급
        if query.rating and query.rating != "all":
            conditions.append({"content_rating": query.rating})

        # 성별
        if query.gender:
            conditions.append({"character_gender": query.gender})

        # 언어
        if query.language:
            conditions.append({"language": query.language})

        # 원작
        if query.source:
            conditions.append({"source": query.source})

        if not conditions:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}

    def _metadata_to_result(self, metadata: dict, document: str, score: float) -> SearchResult:
        """메타데이터를 SearchResult로 변환"""
        # genres는 쉼표로 구분된 문자열
        genres = metadata.get("genres", "")
        genres_list = [g.strip() for g in genres.split(",") if g.strip()]

        return SearchResult(
            uuid=metadata["uuid"],
            name=metadata["name"],
            authorname=metadata.get("authorname", ""),
            desc=document[:300] if document else "",
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

        # 검색어가 있으면 벡터 검색
        if query.q:
            query_embedding = self.embedder.embed_query(query.q)

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=query.limit + query.offset,
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
                    score = 1 - distance

                    items.append(self._metadata_to_result(metadata, document, score))

            # offset 적용
            items = items[query.offset:]

        else:
            # 검색어 없으면 필터만 적용
            results = self.collection.get(
                where=where_filter,
                limit=query.limit + query.offset,
                include=["documents", "metadatas"],
            )

            items = []
            if results["ids"]:
                for i, uuid in enumerate(results["ids"]):
                    metadata = results["metadatas"][i]
                    document = results["documents"][i] if results["documents"] else ""
                    items.append(self._metadata_to_result(metadata, document, 0.0))

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
        query = SearchQuery(q=q, rating=rating, limit=limit)
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
