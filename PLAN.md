# RisuRealm Search 기획서

## 1. 프로젝트 개요

### 1.1 배경
RisuRealm(realm.risuai.net)은 AI 캐릭터 프롬프트 공유 플랫폼으로, 수만 개의 캐릭터가 등록되어 있다. 그러나 현재 검색 기능의 한계로 인해 사용자가 원하는 캐릭터를 찾기 어려운 상황이다.

### 1.2 문제점
- 제작자마다 태그 부여 방식이 상이함 (대소문자 혼용, 동의어 분산)
- 복합 조건 검색 불가 ("판타지 + 얀데레" 등)
- 자연어 기반 검색 미지원
- SFW/NSFW 구분 필터 부재

### 1.3 목표
LLM 기반 메타데이터 자동 추출 및 시맨틱 검색을 통해 사용자가 원하는 캐릭터를 쉽게 찾을 수 있는 검색 엔진 구축

### 1.4 라이센스
MIT License - 전체 소스 코드 공개, 무료 배포

---

## 2. 핵심 기능

### 2.1 검색 기능

| 기능 | 설명 | 예시 |
|------|------|------|
| 자연어 검색 | 문장으로 캐릭터 검색 | "현대 배경 학원물 로맨스" |
| 키워드 검색 | 특정 단어로 검색 | "얀데레", "원신" |
| 태그 필터 | 정규화된 태그로 필터링 | 장르, 설정, 성격 등 |

### 2.2 필터 기능

#### 콘텐츠 등급
| 등급 | 설명 |
|------|------|
| SFW | 전연령 |
| NSFW | 성인 콘텐츠 포함 |
| Unknown | 판별 불가 |

#### 장르 필터
판타지 / 로맨스 / 학원 / SF / 현대 / 역사 / 호러 / 코미디 / 
다크판타지 / 이세계 / 시뮬레이터 / 게임원작 / 애니원작

#### 캐릭터 속성
성별: 여성 / 남성 / 기타 / 다수
성격: 얀데레 / 츤데레 / 쿨데레 / 메스가키 / ...
관계: 연인 / 가족 / 동료 / 주종 / ...

#### 기타 필터
- 언어: 한국어 / 영어 / 일본어 / 다국어
- 에셋 포함 여부
- 로어북 포함 여부

### 2.3 정렬 옵션
- 관련도순 (기본값)
- 다운로드순
- 최신순
- 업데이트순

---

## 3. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Pipeline                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│   │ RisuRealm│───▶│ Scraper  │───▶│   LLM    │───▶│ Database │  │
│   │   API    │    │          │    │  Tagger  │    │          │  │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                         │       │
└─────────────────────────────────────────────────────────│───────┘
                                                          │
┌─────────────────────────────────────────────────────────│───────┐
│                      Search Service                     │       │
├─────────────────────────────────────────────────────────│───────┤
│                                                         ▼       │
│   ┌──────────┐    ┌──────────┐    ┌──────────────────────────┐  │
│   │  Search  │───▶│  Query   │───▶│      Search Engine       │  │
│   │   API    │    │ Processor│    │  ┌────────┐ ┌────────┐   │  │
│   └──────────┘    └──────────┘    │  │Vector  │ │Keyword │   │  │
│                                   │  │Search  │ │Search  │   │  │
│                                   │  └────────┘ └────────┘   │  │
│                                   └──────────────────────────┘  │
│                                                         │       │
└─────────────────────────────────────────────────────────│───────┘
                                                          │
                                                          ▼
                                                   ┌──────────┐
                                                   │  UUID +  │
                                                   │   Link   │
                                                   └──────────┘
```

---

## 4. 데이터 스키마

### 4.1 저장 데이터 (메타데이터만)

### 4.2 저장하지 않는 데이터
- 캐릭터 프롬프트 원문
- 시스템 프롬프트
- 이미지/에셋 파일
- 로어북 내용

---

## 5. 기술 스택

| 구성요소 | 기술 | 선정 이유 |
|---------|------|----------|
| 언어 | Python 3.11+ | LLM/ML 생태계 |
| 데이터 수집 | aiohttp | 비동기 크롤링 |
| LLM 태깅 | Groq + 기타 | 무료, 빠름 |
| 임베딩 | voyage |  무료, 다국어 지원, BYOK 가능 |
| 벡터 DB | 미정 | Chroma DB, SQLite 백엔드 |
| 키워드 검색 | 미정 | 가볍고 빠른 것 |
| API 서버 | FastAPI | 비동기, 자동 문서화 |
| 프론트엔드 | 미정 | Next.js 또는 Gradio |

---

## 6. LLM 태깅 프롬프트

---

## 7. API 설계

### 7.1 검색 엔드포인트

```
GET /api/search
```

**파라미터**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| q | string | 검색어 |
| rating | string | sfw, nsfw, all |
| genres | string[] | 장르 필터 |
| gender | string | 캐릭터 성별 |
| language | string | 언어 |
| source | string | 원작 필터 |
| sort | string | relevance, downloads |
| limit | int | 결과 수 (기본 20) |
| offset | int | 페이지네이션 |

**응답**

```json
{
  "total": 150,
  "results": [
    {
      "uuid": "55090ec1-e50a-4b5c-b832-dd90e03833bd",
      "title": "캐릭터 이름",
      "author": "제작자",
      "url": "https://realm.risuai.net/character/55090ec1-...",
      "rating": "sfw",
      "genres": ["fantasy", "romance"],
      "relevance_score": 0.92
    }
  ]
}
```

### 7.2 필터 옵션 조회

```
GET /api/filters
```

사용 가능한 장르, 태그 목록 반환

---

## 8. 개발 일정

| 단계 | 작업 |
|------|------|
| 1 | API 분석 및 스크래퍼 개발 |
| 2 | LLM 태깅 파이프라인 구축 |
| 3 | 데이터 수집 실행 (~1만건) |
| 4 | 검색 엔진 구현 |
| 5 | API 서버 개발 |
| 6 | 프론트엔드 (MVP) |
| 7 | 테스트 및 배포 |

---

## 9. 향후 확장 가능성

- 사용자 즐겨찾기 / 검색 히스토리
- 유사 캐릭터 추천
- 제작자별 검색
- 커뮤니티 태그 수정 제안
- 브라우저 확장 프로그램

---

## 10. 제약 사항 및 고려사항

### 10.1 저작권
- 원본 프롬프트/콘텐츠 저장하지 않음
- 검색 결과는 RisuRealm 원본 링크로 연결
- robots.txt 준수, rate limiting 적용

### 10.2 데이터 신선도
- 정기 업데이트 (주 1회 또는 일 1회)
- 신규 캐릭터 자동 수집

### 10.3 비용
- LLM API: Groq 무료 티어 사용
- 호스팅: Cloudflare Pages/Workers 또는 개인 서버

---

## 11. API 분석 결과

### 11.1 프록시 API (목록 조회)

**URL 패턴**:
```
https://sv.risuai.xyz/realm/{encoded_query}
```

**쿼리 파라미터** (URL 인코딩):
```
search== __shared&&page=={n}&&nsfw=={true|false}&&sort==downloads&&web==other
```

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| `search` | `__shared` | 검색 타입 |
| `page` | 0, 1, 2... | 페이지 (0-indexed) |
| `nsfw` | true/false | NSFW 필터 |
| `sort` | downloads | 정렬 방식 |
| `web` | other | 웹 타입 |

**응답 필드** (페이지당 30개):

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | UUID |
| `name` | string | 캐릭터명 |
| `desc` | string | 설명 (마크다운) |
| `download` | string | 다운로드 수 ("12.3k" 형식) |
| `img` | string | 이미지 해시 |
| `tags` | array | 태그 목록 |
| `authorname` | string | 제작자명 |
| `creator` | string | 제작자 ID |
| `license` | string | 라이선스 |
| `haslore` | boolean | 로어북 여부 |
| `hasEmotion` | boolean | 감정 에셋 여부 |
| `hasAsset` | boolean | 에셋 여부 |
| `date` | number | 타임스탬프 |
| `type` | string | 타입 ("normal") |

### 11.2 다운로드 API (상세 조회)

```
GET https://realm.risuai.net/api/v1/download/:format/:id
```

**포맷**: `charx-v3`, `json-v3`, `json-v2`, `png-v3`, `png-v2`

**쿼리 파라미터**: `cors`, `non_commercial`, `access_token`

**참고**: 모든 캐릭터가 모든 포맷을 지원하지 않음

### 11.3 캐릭터 카드 구조 (V2/V3)

```python
# 핵심 필드
name: str
description: str
personality: str
scenario: str
first_mes: str
alternate_greetings: list[str]
system_prompt: str
post_history_instructions: str
tags: list[str]
creator: str
creator_notes: str
character_book: Optional[Lorebook]  # 로어북
extensions: dict  # risuai.additionalAssets 등
```

---

## 12. 스크래퍼 구현 계획 (Updated)

### 12.1 프로젝트 구조

```
risurealm_search/
├── scraper/
│   ├── __init__.py
│   ├── client.py          # API 클라이언트 (aiohttp)
│   ├── models.py          # Pydantic 데이터 모델
│   ├── scraper.py         # 메인 스크래퍼 로직 (타입 조회 + 중복 제거 포함)
│   └── utils.py           # 유틸리티 함수
├── data/                  # 수집된 데이터 저장
│   ├── list_sfw.jsonl     # SFW 목록
│   ├── list_nsfw.jsonl    # NSFW 목록 (SFW 중복 제거됨)
│   ├── types.json         # 캐릭터 타입 캐시 (normal/charx)
│   ├── characters.jsonl   # 상세 정보 포함 최종 데이터
│   └── progress.json      # 진행 상황 저장
├── requirements.txt
└── main.py                # 실행 진입점
```

### 12.2 의존성

```
aiohttp>=3.9.0
pydantic>=2.0.0
tqdm>=4.66.0
```

### 12.3 models.py - 데이터 모델

```python
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
    id: str                      # UUID
    name: str
    desc: str                    # 마크다운 설명
    download: str                # "12.3k" 형식
    img: str                     # 이미지 해시
    tags: list[str]
    authorname: Optional[str] = ""
    creator: Optional[str] = ""  # 제작자 ID
    license: Optional[str] = ""
    haslore: bool
    hasEmotion: bool
    hasAsset: bool
    date: int                    # Unix timestamp
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
    asset_list: list[str] = []   # 에셋 이름 목록만

class ScrapedCharacter(BaseModel):
    """최종 저장 모델"""
    uuid: str
    nsfw: bool                   # SFW/NSFW 구분

    # 목록 데이터
    list_data: CharacterListItem

    # 상세 데이터 (폴백 결과)
    detail_data: Optional[CharacterDetail] = None
    detail_source: DetailSource

    # 메타
    scraped_at: int              # 수집 시간 (Unix timestamp)
```

### 12.4 client.py - API 클라이언트 (주요 변경점)

- `fetch_character_type(uuid)`: 캐릭터 상세 페이지의 `__data.json`을 조회하여 `charx` 여부를 판별하는 기능 추가.
- `fetch_detail(uuid, char_type)`: 미리 파악된 타입에 따라 효율적으로 다운로드 포맷(`charx-v3` vs `json-v3/v2`)을 요청.

### 12.5 scraper.py - 메인 로직 개선

**A. 캐릭터 타입 사전 조회 (Optimization)**
- 목록 수집 후 상세 정보를 받기 전에 전체 캐릭터의 타입(`normal` vs `charx`)을 병렬로 조회합니다.
- 조회된 타입은 `types.json`에 캐싱되어 재실행 시 시간을 단축합니다.
- `charx` 타입인 경우 즉시 ZIP 포맷을 요청하여 불필요한 요청을 줄입니다.

**B. 중복 제거 강화**
- **SFW 우선 원칙**: NSFW 목록 수집 시, 이미 수집된 SFW 목록에 존재하는 ID는 **즉시 필터링하여 제외**합니다.
- 이로 인해 `list_nsfw.jsonl`에는 순수 NSFW(또는 SFW에 포함되지 않은) 항목만 저장됩니다.

```python
# 중복 제거 로직 예시
sfw_ids = {item["id"] for item in sfw_items}
nsfw_items = [item for item in nsfw_items if item["id"] not in sfw_ids]
```

### 12.6 다중 폴백 및 최적화 전략

1. **타입 확인**: `fetch_character_type`으로 타입 확인 (`charx` or `normal`)
2. **다운로드 시도**:
    - `charx` 타입 -> `charx-v3` (ZIP) 요청
    - `normal` 타입 -> `json-v3` -> 실패 시 `json-v2` 요청
3. **최종 폴백**: 모든 다운로드 실패 시 목록의 메타데이터(`list_only`)만 저장

### 12.7 실행 방법

```bash
# 전체 수집 (scrape 명령)
python main.py scrape

# 옵션 예시
python main.py scrape --count 100 --concurrent 20
```

### 12.8 출력 파일

| 파일 | 설명 |
|------|------|
| `data/list_sfw.jsonl` | SFW 목록 원본 |
| `data/list_nsfw.jsonl` | NSFW 목록 원본 (SFW 중복 제거됨) |
| `data/types.json` | 캐릭터 타입 캐시 |
| `data/characters.jsonl` | 상세 정보 포함 최종 데이터 |
| `data/progress.json` | 진행 상황 (재개용) |

