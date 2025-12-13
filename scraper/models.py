from pydantic import BaseModel
from typing import Optional
from enum import Enum


class DetailSource(str, Enum):
    CHARX_V3 = "charx-v3"
    JSON_V3 = "json-v3"
    JSON_V2 = "json-v2"
    LIST_ONLY = "list_only"


class CharacterListItem(BaseModel):
    """프록시 API 목록 응답 모델"""

    id: str  # UUID
    name: str = ""
    desc: str = ""  # 마크다운 설명
    download: str = "0"  # "12.3k" 형식
    img: str = ""  # 이미지 해시
    tags: list[str] = []
    authorname: Optional[str] = ""
    creator: Optional[str] = ""  # 제작자 ID
    license: Optional[str] = ""
    haslore: bool = False
    hasEmotion: bool = False
    hasAsset: bool = False
    date: int = 0  # Unix timestamp
    type: str = "normal"
    viewScreen: Optional[str] = ""
    hidden: Optional[int] = 0
    commentopen: Optional[int] = 1
    original: Optional[str] = ""


class CharacterDetail(BaseModel):
    """다운로드 API 상세 정보 모델"""

    name: str
    description: str
    personality: str
    scenario: str
    first_mes: str
    alternate_greetings: list[str] = []
    system_prompt: str = ""
    post_history_instructions: str = ""
    tags: list[str] = []
    creator: str = ""
    creator_notes: str = ""
    character_version: str = ""

    # 로어북 메타데이터 (내용은 저장하지 않음)
    has_lorebook: bool = False
    lorebook_entry_count: int = 0

    # 에셋 메타데이터 (파일은 저장하지 않음)
    asset_count: int = 0
    asset_list: list[str] = []  # 에셋 이름 목록만


class ScrapedCharacter(BaseModel):
    """최종 저장 모델"""

    uuid: str
    nsfw: bool  # SFW/NSFW 구분

    # 목록 데이터
    list_data: CharacterListItem

    # 상세 데이터 (폴백 결과)
    detail_data: Optional[CharacterDetail] = None
    detail_source: DetailSource

    # 메타
    scraped_at: int  # 수집 시간 (Unix timestamp)
