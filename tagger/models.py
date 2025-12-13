"""태깅 결과 모델"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ContentRating(str, Enum):
    SFW = "sfw"
    NSFW = "nsfw"
    UNKNOWN = "unknown"


class Genre(str, Enum):
    FANTASY = "fantasy"
    ROMANCE = "romance"
    SCHOOL = "school"
    SCIFI = "scifi"
    MODERN = "modern"
    HISTORICAL = "historical"
    HORROR = "horror"
    COMEDY = "comedy"
    DARK_FANTASY = "dark_fantasy"
    ISEKAI = "isekai"
    SIMULATOR = "simulator"
    GAME_ORIGINAL = "game_original"
    ANIME_ORIGINAL = "anime_original"


class CharacterGender(str, Enum):
    FEMALE = "female"
    MALE = "male"
    MULTIPLE = "multiple"
    OTHER = "other"
    UNKNOWN = "unknown"

class Language(str, Enum):
    KOREAN = "korean"
    ENGLISH = "english"
    JAPANESE = "japanese"
    CHINESE = "chinese"
    MULTILINGUAL = "multilingual"
    OTHER = "other"


class CharacterTags(BaseModel):
    """LLM이 추출한 캐릭터 태그"""

    content_rating: ContentRating = ContentRating.UNKNOWN
    genres: list[str] = []  # Genre enum 값들
    setting: str = ""  # modern, medieval, futuristic 등
    character_gender: CharacterGender = CharacterGender.OTHER
    character_traits: list[str] = []  # yandere, tsundere 등
    source: Optional[str] = None  # 원작명 (OC면 null)
    language: Language = Language.ENGLISH
    summary: str = ""  # 한 줄 요약 (한국어)
    description: str = ""  # 상세 설명 (한국어, 100-500자)


class TaggingResult(BaseModel):
    """태깅 결과"""

    uuid: str
    tags: Optional[CharacterTags] = None
    model_used: str = ""  # 성공한 모델명
    models_tried: list[str] = []  # 시도한 모델 목록
    error: Optional[str] = None
    raw_response: Optional[str] = None  # 디버깅용
    tagged_at: int = 0  # Unix timestamp


class TaggedCharacter(BaseModel):
    """태그가 포함된 캐릭터 (최종 출력)"""

    uuid: str
    nsfw: bool

    # 기존 목록 데이터에서 필요한 필드
    name: str
    desc: str
    download: str
    authorname: str
    tags: list[str]  # 원본 태그
    haslore: bool
    hasAsset: bool

    # 상세 데이터 요약
    has_detail: bool
    detail_source: str

    # LLM 추출 태그
    llm_tags: Optional[CharacterTags] = None
    tagging_model: str = ""
    tagging_error: Optional[str] = None

    # 메타
    scraped_at: int
    tagged_at: int
