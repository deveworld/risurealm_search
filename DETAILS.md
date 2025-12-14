# RisuRealm Search - 기술 문서

이 문서는 RisuRealm Search의 기술적인 세부 사항을 설명합니다.

## 목차

- [프로젝트 구조](#프로젝트-구조)
- [데이터 파이프라인](#데이터-파이프라인)
- [검색 랭킹 알고리즘](#검색-랭킹-알고리즘)
- [LLM 태깅](#llm-태깅)
- [CLI 명령어](#cli-명령어)
- [API 상세](#api-상세)

---

## 프로젝트 구조

```
risurealm_search/
├── scraper/               # 데이터 수집 모듈
│   ├── client.py          # RisuRealm API 클라이언트 (Rate limit 대응)
│   ├── scraper.py         # 스크래핑 로직 (병렬 처리, Graceful shutdown)
│   ├── models.py          # Pydantic 데이터 모델
│   └── utils.py           # JSONL 처리, 다운로드 파싱
├── tagger/                # LLM 태깅 모듈
│   ├── client.py          # Groq API 클라이언트 (다중 모델 폴백)
│   ├── tagger.py          # 실시간 태깅 (ThreadPoolExecutor)
│   ├── batch.py           # Groq Batch API 태깅
│   └── models.py          # 태깅 결과 모델
├── searcher/              # 검색 모듈
│   ├── embedder.py        # Voyage AI 임베딩 클라이언트
│   ├── indexer.py         # ChromaDB 인덱싱 (증분/upsert)
│   ├── searcher.py        # 하이브리드 검색 엔진
│   ├── bm25.py            # BM25 키워드 검색
│   ├── synonyms.py        # 한영 동의어 매핑 (공통 모듈)
│   └── models.py          # 검색 쿼리/결과 모델
├── api/                   # FastAPI 서버
│   └── app.py             # REST API 엔드포인트
├── ui/                    # Gradio UI
│   └── app.py             # 웹 인터페이스
├── data/                  # 데이터 저장소
│   ├── list_sfw.jsonl     # SFW 캐릭터 목록
│   ├── list_nsfw.jsonl    # NSFW 캐릭터 목록
│   ├── characters.jsonl   # 캐릭터 상세 정보
│   ├── tagged.jsonl       # LLM 태깅 결과
│   ├── chroma_db/         # 벡터 인덱스 (ChromaDB)
│   └── bm25_index.pkl     # BM25 인덱스 (pickle)
└── main.py                # CLI 진입점 (Typer)
```

---

## 데이터 파이프라인

```
┌─────────────────┐
│  RisuRealm API  │
└────────┬────────┘
         │ scrape / update / full-update
         ▼
┌─────────────────┐
│ list_*.jsonl    │  목록 데이터 (UUID, 이름, 다운로드 수 등)
│ characters.jsonl│  상세 데이터 (설명, 성격, 시나리오 등)
└────────┬────────┘
         │ tag / batch-tag
         ▼
┌─────────────────┐
│ tagged.jsonl    │  LLM 추출 메타데이터 (요약, 등급, 성별 등)
└────────┬────────┘
         │ index
         ▼
┌─────────────────┐
│ chroma_db/      │  벡터 인덱스 (Voyage AI 임베딩)
│ bm25_index.pkl  │  BM25 인덱스 (토큰화된 문서)
└────────┬────────┘
         │ search
         ▼
┌─────────────────┐
│   검색 결과      │  하이브리드 랭킹 (RRF + 부스트)
└─────────────────┘
```

### 데이터 수집 모드 비교

| | `update` | `full-update` |
|---|----------|---------------|
| **목록 조회** | 최신순, 기존 UUID 만나면 중단 | 전체 재조회 |
| **변경 감지** | 새 캐릭터만 | date 비교로 수정된 것도 감지 |
| **기존 캐릭터** | 건드리지 않음 | 메타데이터(download 등) 업데이트 |
| **용도** | 일상적인 업데이트 | 수정된 캐릭터 동기화 |
| **속도** | 빠름 | 느림 (전체 목록 조회) |

---

## 검색 랭킹 알고리즘

### 하이브리드 검색 아키텍처

```
검색어: "판타지 얀데레 여자"
              │
    ┌─────────┴────────┐
    ▼                  ▼
┌─────────┐       ┌─────────┐
│ 벡터검색│       │  BM25   │
│(Voyage) │       │  검색   │
└────┬────┘       └────┬────┘
     │                 │
     │  Top 100        │  Top 100
     │                 │
     └────────┬────────┘
              │
              ▼
     ┌────────────────┐
     │    RRF 융합    │
     │     (k=60)     │
     └───────┬────────┘
              │
              ▼
    ┌───────────────────┐
    │ 키워드 부스트     │
    │ + 다운로드 부스트 │
    └─────────┬─────────┘
              │
              ▼
          최종 랭킹
```

### 최종 점수 계산

```
score = (RRF_score × 10) + (keyword_boost × 0.3) + (download_boost × 0.2)
```

#### RRF (Reciprocal Rank Fusion)

```python
RRF_score = Σ 1/(k + rank)  # k=60
```

| 순위 | 단일 랭킹 점수 | 양쪽 1등일 때 |
|------|--------------|--------------|
| 1등 | 0.0164 | 0.0328 |
| 5등 | 0.0154 | 0.0308 |
| 10등 | 0.0143 | 0.0286 |
| 50등 | 0.0091 | 0.0182 |

#### 키워드 부스트

검색어가 문서의 어느 위치에서 매칭되는지에 따라 가중치를 부여합니다:

| 위치 | 가중치 | 설명 |
|------|--------|------|
| 요약 | 0.8 | LLM이 생성한 한 줄 요약 |
| 태그 | 0.5 | 원본 캐릭터 태그 |
| 이름 | 0.4 | 캐릭터 이름 |
| 설명 | 0.3 | LLM이 생성한 상세 설명 |
| 기타 | 0.2 | 위 영역 외 문서 |

**중복 적용**: 같은 키워드가 여러 위치에 있으면 가중치가 합산됩니다.

**커버리지 패널티**:
```
최종 키워드 점수 = 키워드 부스트 × (매칭된 토큰 수 / 전체 토큰 수)
```

예: "판타지 얀데레 고등학생" 검색 시 2개만 매칭되면 점수가 2/3로 감소

#### 다운로드 부스트

```python
download_boost = log10(downloads + 10) / 10
```

| 다운로드 수 | 부스트 값 | × 0.2 |
|------------|----------|-------|
| 100 | 0.204 | 0.041 |
| 10,000 | 0.400 | 0.080 |
| 100,000 | 0.500 | 0.100 |
| 624,000 | 0.579 | 0.116 |

**영향력**: 624k vs 8k 다운로드 차이 ≈ RRF 순위 약 9등 차이

### 한영 동의어 매핑

`searcher/synonyms.py`에 77개의 양방향 동의어가 정의되어 있습니다:

```python
# 한국어 → 영어
"얀데레" → ["yandere"]
"판타지" → ["fantasy"]
"뱀파이어" → ["vampire"]

# 영어 → 한국어
"yandere" → ["얀데레"]
"fantasy" → ["판타지"]
"vampire" → ["뱀파이어"]
```

동의어는 BM25 검색과 키워드 부스트 계산 시 모두 적용됩니다.

---

## LLM 태깅

### 사용 모델 (폴백 순서)

1. `openai/gpt-oss-120b` - 한국어 품질 우수
2. `meta-llama/llama-4-maverick-17b-128e-instruct`
3. `llama-3.3-70b-versatile`
4. `moonshotai/kimi-k2-instruct`
5. `moonshotai/kimi-k2-instruct-0905`

Rate limit 발생 시 자동으로 다음 모델로 폴백합니다.

### 태깅 항목

| 필드 | 설명 | 값 |
|------|------|-----|
| `content_rating` | 콘텐츠 등급 | `sfw`, `nsfw`, `unknown` |
| `character_gender` | 캐릭터 성별 | `female`, `male`, `multiple`, `other`, `unknown` |
| `source` | 원작 목록 | `["genshin_impact"]`, `[]` (OC) |
| `language` | 롤플레이 언어 | `korean`, `english`, `japanese`, `multilingual`, `other` |
| `summary` | 한 줄 요약 | 한국어, 20-50자 |
| `description` | 상세 설명 | 한국어, 100-500자 |

### 태깅에 사용되는 캐릭터 정보

- 기본 정보: 제목, 제작자, 태그, 다운로드 수
- 플래그: 로어북 유무, 에셋 유무
- 텍스트 필드:
  - `list_data.desc` - 목록 설명
  - `detail_data.description` - 상세 설명
  - `detail_data.personality` - 성격
  - `detail_data.scenario` - 시나리오
  - `detail_data.first_mes` - 첫 메시지
  - `detail_data.post_history_instructions` - 시스템 지시

### 배치 태깅 vs 실시간 태깅

| | 실시간 (`tag`) | 배치 (`batch-tag`) |
|--|---------------|-------------------|
| **처리 방식** | 즉시 처리 | Groq Batch API |
| **비용** | 100% | 50% 할인 |
| **속도** | 빠름 | 느림 (최대 24시간) |
| **용도** | 소량, 즉시 필요 | 대량 처리 |

---

## CLI 명령어

### 데이터 수집

```bash
# 전체 스크래핑 (초기)
python main.py scrape

# 신규 캐릭터 추가
python main.py update

# 전체 동기화 (수정된 캐릭터 포함)
python main.py full-update
```

### LLM 태깅

```bash
# 실시간 태깅
python main.py tag

# 배치 태깅 (전체 프로세스)
python main.py batch-tag run --all

# 배치 태깅 (단계별)
python main.py batch-tag prepare      # 입력 파일 생성
python main.py batch-tag start        # 배치 작업 시작
python main.py batch-tag status       # 상태 확인
python main.py batch-tag download     # 결과 다운로드
python main.py batch-tag process      # 결과 처리

# 모델 지정
python main.py batch-tag run --all --model "openai/gpt-oss-120b"
```

### 인덱싱

```bash
# 증분 인덱싱 (새 캐릭터만)
python main.py index

# 전체 재인덱싱
python main.py index --rebuild

# 메타데이터만 업데이트 (API 비용 절감)
python main.py index --metadata-only

# BM25 인덱스만 재구축
python main.py index --bm25-only
```

### 검색 및 서버

```bash
# CLI 검색
python main.py search "검색어" --limit 10 --rating sfw

# API 서버
python main.py serve --port 8000

# Gradio UI
python main.py ui --port 7860
```

---

## API 상세

### GET /search

캐릭터 검색

**파라미터**:
| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `q` | string | ✓ | 검색어 |
| `rating` | string | | 콘텐츠 등급 (`sfw`, `nsfw`) |
| `gender` | string | | 캐릭터 성별 |
| `language` | string | | 언어 |
| `limit` | int | | 결과 수 (기본 10, 최대 100) |
| `offset` | int | | 페이지네이션 오프셋 |

**응답**:
```json
{
  "total": 10,
  "results": [
    {
      "uuid": "abc123",
      "name": "캐릭터 이름",
      "authorname": "제작자",
      "desc": "설명...",
      "url": "https://realm.risuai.net/character/abc123",
      "content_rating": "sfw",
      "character_gender": "female",
      "language": "korean",
      "tags": ["fantasy", "romance"],
      "source": "original",
      "score": 0.85
    }
  ]
}
```

### GET /character/{uuid}

캐릭터 상세 정보

**응답**:
```json
{
  "uuid": "abc123",
  "name": "캐릭터 이름",
  "authorname": "제작자",
  "desc": "상세 설명...",
  "url": "https://realm.risuai.net/character/abc123",
  "content_rating": "sfw",
  "character_gender": "female",
  "language": "korean",
  "tags": ["fantasy", "romance"],
  "source": null
}
```

---

## 필터 옵션

| 필터 | 옵션 | UI 기본값 |
|------|------|----------|
| 등급 | `sfw`, `nsfw` | 전체 |
| 성별 | `female`, `male`, `multiple`, `other` | 전체 |
| 언어 | `korean`, `english`, `japanese`, `multilingual`, `other` | Korean, Multilingual |

---

## 환경변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `VOYAGE_API_KEY` | ✓ | Voyage AI API 키 (임베딩) |
| `GROQ_API_KEY` | | Groq API 키 (LLM 태깅) |

---

## Git LFS

대용량 파일은 Git LFS로 관리됩니다:

```
*.jsonl filter=lfs diff=lfs merge=lfs -text
data/chroma_db/*.sqlite3 filter=lfs diff=lfs merge=lfs -text
```

클론 전에 `git lfs install`을 실행해야 합니다.
