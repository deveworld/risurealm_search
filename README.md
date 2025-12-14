# RisuRealm Search

RisuRealm(realm.risuai.net) 캐릭터 검색 엔진입니다. LLM 기반 메타데이터 추출과 하이브리드 검색(벡터 + BM25)을 통해 자연어로 캐릭터를 검색할 수 있습니다.

## 주요 기능

- **자연어 검색**: "판타지 세계의 얀데레 여자 캐릭터" 같은 쿼리 지원
- **하이브리드 검색**: 벡터 검색 + BM25 + RRF 융합
- **한영 동의어**: "얀데레" ↔ "yandere" 자동 매칭
- **다중 필터**: 등급(SFW/NSFW), 성별, 언어

## 기술 스택

| 구성요소 | 기술 |
|---------|------|
| 임베딩 | Voyage AI (`voyage-3-large`) |
| 벡터 DB | ChromaDB |
| 키워드 검색 | BM25 (rank-bm25) |
| LLM 태깅 | Groq API |
| API/UI | FastAPI / Gradio |

## 설치

```bash
# Git LFS 필수
git lfs install

# 클론 및 설치
git clone https://github.com/deveworld/risurealm_search.git
cd risurealm_search
uv sync

# 환경변수
cp .env.example .env
# VOYAGE_API_KEY, GROQ_API_KEY 설정
```

## 사용법

```bash
# 웹 UI
python main.py ui --port 7860

# API 서버
python main.py serve --port 8000

# CLI 검색
python main.py search "검색어" --limit 10

# 데이터 수집 → 태깅 → 인덱싱
python main.py update        # 신규 캐릭터 추가
python main.py tag           # LLM 태깅
python main.py index         # 벡터 인덱싱
```

## Docker

```bash
docker pull ghcr.io/deveworld/risurealm_search:main
docker run -d -p 7860:7860 -e VOYAGE_API_KEY="your-key" ghcr.io/deveworld/risurealm_search:main
```

## API

```
GET /search?q=검색어&limit=10&rating=sfw&gender=female&language=korean
GET /character/{uuid}
```

## 문서

기술적인 상세 내용은 [DETAILS.md](DETAILS.md)를 참고하세요.

## 라이선스

MIT License
