# RisuRealm Search

RisuRealm(realm.risuai.net) 캐릭터 검색 엔진입니다. LLM 기반 메타데이터 추출과 벡터 검색을 통해 자연어로 캐릭터를 검색할 수 있습니다.

## 주요 기능

- **자연어 검색**: "판타지 세계의 얀데레 여자 캐릭터" 같은 자연어 쿼리 지원
- **다중 필터링**: 등급(SFW/NSFW), 성별, 언어별 필터
- **다운로드 가중치**: 인기 캐릭터가 상위에 노출
- **증분 업데이트**: 변경된 캐릭터만 효율적으로 동기화

## 기술 스택

| 구성요소 | 기술 |
|---------|------|
| 임베딩 | Voyage AI (다국어 지원) |
| 벡터 DB | ChromaDB |
| LLM 태깅 | Groq API (Llama 3.3 70B) |
| API 서버 | FastAPI |
| UI | Gradio |
| 배포 | Docker + GitHub Actions |

## 설치

### 요구사항

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (권장) 또는 pip

### 로컬 설치

```bash
# 저장소 클론
git clone https://github.com/deveworld/risurealm_search.git
cd risurealm_search

# 의존성 설치
uv sync

# 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 입력
```

### 환경변수

```bash
VOYAGE_API_KEY=your_voyage_api_key
GROQ_API_KEY=your_groq_api_key  # 태깅용 (선택)
```

## 사용법

### 명령어

```bash
# 웹 UI 실행
python main.py ui --port 7860

# API 서버 실행
python main.py serve --port 8000

# CLI 검색
python main.py search "검색어" --limit 10
```

### 데이터 수집

```bash
# 전체 캐릭터 수집 (초기 설정)
python main.py scrape

# 신규 캐릭터 추가 (일상적 업데이트)
python main.py update

# 전체 동기화 (수정된 캐릭터 감지)
python main.py full-update
```

#### update vs full-update

| | update | full-update |
|---|--------|-------------|
| **목록 조회** | 최신순, 기존 UUID 만나면 중단 | 전체 재조회 |
| **변경 감지** | 새 캐릭터만 | date 비교로 수정된 것도 감지 |
| **기존 캐릭터** | 건드리지 않음 | 메타데이터(download 등) 업데이트 |
| **용도** | 일상적인 업데이트 | 수정된 캐릭터 동기화 |
| **속도** | 빠름 | 느림 (전체 목록 조회) |

### LLM 태깅

```bash
# 실시간 태깅 (태깅 안 된 것만)
python main.py tag

# 배치 태깅 - Groq Batch API (대량 처리, 50% 비용 절감)
python main.py batch-tag run --all    # 전체 자동 실행
python main.py batch-tag prepare      # 배치 파일 준비
python main.py batch-tag start        # 배치 작업 시작
python main.py batch-tag status       # 상태 확인
python main.py batch-tag download     # 결과 다운로드
python main.py batch-tag process      # 결과 처리
python main.py batch-tag process --all # 기존 데이터 교체
```

### 벡터 인덱싱

```bash
# 증분 인덱싱 (새 캐릭터만)
python main.py index

# 전체 재인덱싱
python main.py index --rebuild
```

### Docker 실행

```bash
# GitHub Container Registry에서 이미지 Pull
docker pull ghcr.io/deveworld/risurealm_search:main

# 실행
docker run -d -p 7860:7860 -e VOYAGE_API_KEY="your-key" ghcr.io/deveworld/risurealm_search:main
```

또는 직접 빌드:

```bash
docker build -t risurealm-search .
docker run -d -p 7860:7860 -e VOYAGE_API_KEY="your-key" risurealm-search
```

## 프로젝트 구조

```
risurealm_search/
├── scraper/           # 데이터 수집 모듈
│   ├── client.py      # RisuRealm API 클라이언트
│   ├── scraper.py     # 스크래핑 로직
│   ├── models.py      # 데이터 모델
│   └── utils.py       # 유틸리티
├── tagger/            # LLM 태깅 모듈
│   ├── client.py      # Groq API 클라이언트 (폴백 지원)
│   ├── tagger.py      # 실시간 태깅 로직
│   ├── batch.py       # Groq Batch API 태깅
│   └── models.py      # 태깅 모델
├── searcher/          # 검색 모듈
│   ├── embedder.py    # Voyage AI 임베딩
│   ├── indexer.py     # ChromaDB 인덱싱 (증분/upsert 지원)
│   ├── searcher.py    # 검색 엔진
│   └── models.py      # 검색 모델
├── api/               # FastAPI 서버
├── ui/                # Gradio UI
├── data/              # 데이터 저장소
│   ├── list_sfw.jsonl     # SFW 목록
│   ├── list_nsfw.jsonl    # NSFW 목록
│   ├── characters.jsonl   # 상세 정보
│   ├── tagged.jsonl       # 태깅 결과
│   └── chroma_db/         # 벡터 인덱스
└── main.py            # CLI 진입점
```

## 데이터 흐름

```
RisuRealm API
    ↓ scrape/update/full-update
list_*.jsonl + characters.jsonl
    ↓ tag/batch-tag
tagged.jsonl
    ↓ index
chroma_db/
    ↓ search
검색 결과
```

## LLM 태깅 항목

| 필드 | 설명 | 값 |
|------|------|-----|
| content_rating | 콘텐츠 등급 | sfw, nsfw, unknown |
| character_gender | 캐릭터 성별 | female, male, multiple, other, unknown |
| source | 원작 목록 | ["genshin_impact"], [] (OC) |
| language | 롤플레이 언어 | korean, english, japanese, multilingual, other |
| summary | 한 줄 요약 | 한국어 |
| description | 상세 설명 | 한국어, 100-500자 |

## 필터 옵션

| 필터 | 옵션 |
|------|------|
| 등급 | SFW, NSFW |
| 성별 | Female, Male, Multiple, Other |
| 언어 | Korean, English, Japanese, Multilingual, Other |

## API

### 검색

```
GET /api/search?q=검색어&limit=10
```

### 캐릭터 상세

```
GET /api/character/{uuid}
```

## 라이선스

MIT License
