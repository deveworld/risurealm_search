"""검색 관련 데이터 모델"""

from typing import Optional
from pydantic import BaseModel


class SearchQuery(BaseModel):
    """검색 쿼리"""

    q: str = ""  # 자연어 검색어
    ratings: list[str] = []  # sfw, nsfw (여러 개 선택 가능)
    genres: list[str] = []  # 장르 필터 (여러 개 선택 가능)
    genders: list[str] = []  # 캐릭터 성별 (여러 개 선택 가능)
    languages: list[str] = []  # 언어 (여러 개 선택 가능)
    limit: int = 20
    offset: int = 0


class SearchResult(BaseModel):
    """검색 결과 항목"""

    uuid: str
    name: str
    authorname: str
    desc: str
    download: str
    url: str  # RisuRealm 링크

    # LLM 태그
    content_rating: str
    genres: list[str]
    character_gender: str
    language: str
    summary: str
    source: Optional[str] = None

    # 검색 메타
    score: float = 0.0  # 관련도 점수


class SearchResponse(BaseModel):
    """검색 응답"""

    total: int
    results: list[SearchResult]
    query: SearchQuery
