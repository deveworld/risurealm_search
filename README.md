# RisuRealm Search Engine Project

RisuRealm(realm.risuai.net)의 캐릭터 데이터를 수집하고, LLM을 활용하여 메타데이터(태그, 장르, 성격 등)를 자동으로 추출하여 고급 검색 기능을 제공하기 위한 프로젝트입니다.

## 기능

- **데이터 수집 (Scraper)**: RisuRealm의 SFW/NSFW 캐릭터 목록 및 상세 정보를 비동기(Async)로 고속 수집합니다.
    - Rate Limit 자동 감지 및 재시도 (Exponential Backoff)
    - 캐릭터 타입(Normal/CharX) 자동 판별 및 최적화된 다운로드 경로 선택
    - 중복 데이터 제거 및 증분 수집 지원
    - 진행 상황 자동 저장 (중단 시 이어서 실행 가능)

- **LLM 태깅 (Tagger)**: 수집된 캐릭터 정보를 LLM(Groq API)에 전송하여 정규화된 태그를 추출합니다.
    - 멀티 모델 폴백 전략: 주 모델 실패 시 예비 모델(Llama 3, Mixtral 등)로 자동 전환하여 성공률 극대화
    - 병렬 처리 및 Rate Limit 관리

## 설치 방법

### 1. 환경 설정

Python 3.11 이상이 필요합니다.

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 Groq API 키를 입력하세요.

```bash
# .env 파일 생성
echo "GROQ_API_KEY=your_api_key_here" > .env
```

## 사용 방법

`main.py`를 통해 모든 기능을 실행할 수 있습니다.

### 1. 캐릭터 데이터 수집 (Scrape)

```bash
# 전체 캐릭터 수집 (기본값)
python main.py scrape

# 옵션 지정 예시
# - 동시 요청 20개, 요청 간 0.1초 딜레이
# - 테스트를 위해 100개만 수집 (-n 100)
python main.py scrape --concurrent 20 --delay 0.1 -n 100
```

수집된 데이터는 `data/` 디렉토리에 저장됩니다:
- `data/characters.jsonl`: 최종 수집된 캐릭터 데이터 (JSONL 형식)
- `data/types.json`: 캐릭터 타입 캐시
- `data/progress.json`: 진행 상황 정보

### 2. LLM 태깅 (Tag)

수집된 `characters.jsonl` 데이터를 바탕으로 태깅을 수행합니다.

```bash
# 전체 태깅 실행
python main.py tag

# 옵션 지정 예시
# - 3개의 스레드로 병렬 처리
# - 50개만 태깅 (-n 50)
python main.py tag --workers 3 -n 50
```

결과는 `data/tagged.jsonl`에 저장됩니다.

## 프로젝트 구조

```
risurealm_search/
├── data/                  # 데이터 저장소 (자동 생성)
├── scraper/               # 스크래퍼 모듈
│   ├── client.py          # API 클라이언트
│   ├── scraper.py         # 메인 로직
│   └── ...
├── tagger/                # 태거 모듈
│   ├── client.py          # LLM 클라이언트 (Groq)
│   ├── tagger.py          # 태깅 로직
│   └── ...
├── main.py                # 실행 진입점
└── PLAN.md                # 기획서
```

## 라이선스

MIT License
