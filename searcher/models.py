"""검색 관련 데이터 모델"""

from typing import Optional
from pydantic import BaseModel


class SearchQuery(BaseModel):
    """검색 쿼리"""

    q: str = ""  # 자연어 검색어
    ratings: list[str] = []  # sfw, nsfw (여러 개 선택 가능)
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
    img: str = ""  # 이미지 해시

    # 메타데이터
    content_rating: str
    character_gender: str
    language: str
    tags: list[str]  # 원본 태그
    source: Optional[str] = None

    # 검색 메타
    score: float = 0.0  # 관련도 점수

    @property
    def img_url(self) -> str:
        """이미지 URL 반환"""
        if self.img:
            return f"https://sv.risuai.xyz/resource/{self.img}"
        return ""


class SearchResponse(BaseModel):
    """검색 응답"""

    total: int
    results: list[SearchResult]
    query: SearchQuery
