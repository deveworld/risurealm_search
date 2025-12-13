# RisuRealm Search

RisuRealm(realm.risuai.net) 캐릭터 검색 엔진입니다. LLM 기반 메타데이터 추출과 벡터 검색을 통해 자연어로 캐릭터를 검색할 수 있습니다.

## 주요 기능

- **자연어 검색**: "판타지 세계의 얀데레 여자 캐릭터" 같은 자연어 쿼리 지원
- **다중 필터링**: 등급(SFW/NSFW), 성별, 언어, 장르별 필터
- **다운로드 가중치**: 인기 캐릭터가 상위에 노출
- **실시간 업데이트**: 신규 캐릭터 자동 동기화

## 기술 스택

| 구성요소 | 기술 |
|---------|------|
| 임베딩 | Voyage AI (다국어 지원) |
| 벡터 DB | ChromaDB |
| LLM 태깅 | Groq API (Llama 3) |
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

# 데이터 수집
python main.py scrape              # 전체 캐릭터 수집
python main.py update              # 신규 캐릭터만 추가
python main.py full-update         # 전체 동기화 (변경사항 감지)

# LLM 태깅
python main.py tag                 # 수집된 캐릭터 태깅

# 벡터 인덱싱
python main.py index               # ChromaDB에 인덱싱
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
│   └── models.py      # 데이터 모델
├── tagger/            # LLM 태깅 모듈
│   ├── client.py      # Groq API 클라이언트
│   └── tagger.py      # 태깅 로직
├── searcher/          # 검색 모듈
│   ├── embedder.py    # Voyage AI 임베딩
│   ├── indexer.py     # ChromaDB 인덱싱
│   ├── searcher.py    # 검색 엔진
│   └── models.py      # 검색 모델
├── api/               # FastAPI 서버
├── ui/                # Gradio UI
├── data/              # 데이터 저장소
│   ├── characters.jsonl
│   ├── tagged.jsonl
│   └── chroma_db/
└── main.py            # CLI 진입점
```

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
