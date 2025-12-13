"""FastAPI 애플리케이션"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from searcher import CharacterSearcher, SearchQuery


class SearchResponse(BaseModel):
    """검색 응답"""

    total: int
    results: list[dict]


class CharacterResponse(BaseModel):
    """캐릭터 상세 응답"""

    uuid: str
    name: str
    authorname: str
    desc: str
    url: str
    content_rating: str
    genres: list[str]
    character_gender: str
    language: str
    source: Optional[str] = None


# 전역 검색 엔진 인스턴스
_searcher: Optional[CharacterSearcher] = None


def get_searcher() -> CharacterSearcher:
    """검색 엔진 인스턴스 반환"""
    if _searcher is None:
        raise RuntimeError("Searcher not initialized")
    return _searcher


def create_app(data_dir: Path = Path("data")) -> FastAPI:
    """FastAPI 앱 생성"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """앱 라이프사이클 관리"""
        global _searcher
        _searcher = CharacterSearcher(data_dir=data_dir)
        yield
        _searcher.close()

    app = FastAPI(
        title="RisuRealm Search API",
        description="RisuRealm 캐릭터 검색 API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        """API 상태 확인"""
        return {"status": "ok", "message": "RisuRealm Search API"}

    @app.get("/search", response_model=SearchResponse)
    async def search(
        q: str = Query(..., description="검색어"),
        rating: Optional[str] = Query(None, description="콘텐츠 등급 (sfw/nsfw/all)"),
        gender: Optional[str] = Query(None, description="캐릭터 성별"),
        language: Optional[str] = Query(None, description="언어"),
        source: Optional[str] = Query(None, description="원작"),
        limit: int = Query(10, ge=1, le=100, description="결과 수"),
        offset: int = Query(0, ge=0, description="오프셋"),
    ):
        """캐릭터 검색"""
        searcher = get_searcher()

        query = SearchQuery(
            q=q,
            rating=rating,
            gender=gender,
            language=language,
            source=source,
            limit=limit,
            offset=offset,
        )

        response = searcher.search(query)

        return SearchResponse(
            total=response.total,
            results=[
                {
                    "uuid": r.uuid,
                    "name": r.name,
                    "authorname": r.authorname,
                    "desc": r.desc,
                    "url": r.url,
                    "content_rating": r.content_rating,
                    "genres": r.genres,
                    "character_gender": r.character_gender,
                    "language": r.language,
                    "source": r.source,
                    "score": r.score,
                }
                for r in response.results
            ],
        )

    @app.get("/character/{uuid}", response_model=CharacterResponse)
    async def get_character(uuid: str):
        """캐릭터 상세 정보"""
        searcher = get_searcher()

        # Chroma에서 직접 조회
        try:
            result = searcher.collection.get(
                ids=[uuid],
                include=["documents", "metadatas"],
            )

            if not result["ids"]:
                raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다")

            metadata = result["metadatas"][0]
            document = result["documents"][0] if result["documents"] else ""

            genres = metadata.get("genres", "")
            genres_list = [g.strip() for g in genres.split(",") if g.strip()]

            return CharacterResponse(
                uuid=metadata["uuid"],
                name=metadata["name"],
                authorname=metadata.get("authorname", ""),
                desc=document,
                url=f"{searcher.REALM_URL}/{uuid}",
                content_rating=metadata.get("content_rating", "unknown"),
                genres=genres_list,
                character_gender=metadata.get("character_gender", "other"),
                language=metadata.get("language", "english"),
                source=metadata.get("source") or None,
            )

        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))

    return app
