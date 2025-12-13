"""LLM 모델 비교 테스트"""

import json
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# 테스트할 모델 목록
MODELS = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "moonshotai/kimi-k2-instruct",
    "moonshotai/kimi-k2-instruct-0905",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3-32b",
]

# reasoning_format hidden 적용 모델
REASONING_HIDDEN_MODELS = {"qwen/qwen3-32b"}

# 태깅 프롬프트
SYSTEM_PROMPT = """다음 AI 캐릭터 정보를 분석하여 메타데이터를 JSON으로 추출하세요.

추출할 항목:
- content_rating: "sfw" | "nsfw" | "unknown" (성적 콘텐츠 포함 여부)
- genres: 해당하는 장르 목록 (fantasy, romance, school, scifi, modern, historical, horror, comedy, dark_fantasy, isekai, simulator, game_original, anime_original 중 선택)
- setting: 시대/배경 설정 (modern, medieval, futuristic, contemporary, fantasy_world 등)
- character_gender: 캐릭터 성별 (female, male, multiple, other)
- character_traits: 성격 특성 목록 (yandere, tsundere, kuudere, dandere, mesu_gaki 등)
- source: 원작이 있다면 원작명 (genshin_impact, arknights 등), OC면 null
- language: 주 사용 언어 (korean, english, japanese, multilingual)
- summary: 캐릭터에 대한 한 줄 요약 (한국어)

JSON만 출력하세요. 다른 설명은 필요 없습니다."""


def load_test_characters(n: int = 3) -> list[dict]:
    """테스트용 캐릭터 로드"""
    chars = []
    path = Path("data/characters.jsonl")

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                chars.append(json.loads(line))
        return chars

    # 샘플 데이터 반환 (파일이 없을 경우)
    print("⚠️  데이터 파일이 없어 샘플 데이터로 테스트합니다.")
    return [
        {
            "list_data": {
                "name": "테스트 캐릭터 (Test Char)",
                "authorname": "테스트 제작자",
                "tags": ["fantasy", "rpg", "elf"],
                "download": "12.3k",
                "haslore": True,
                "hasAsset": False,
                "desc": "이것은 테스트용 캐릭터 설명입니다. 숲속에 사는 엘프 전사입니다.",
            },
            "detail_data": {
                "description": "상세 설명: 숲의 수호자로서 오랫동안 살아왔습니다.",
                "personality": "용감하고 정의롭지만 약간 고집이 셉니다.",
                "scenario": "당신은 숲에서 길을 잃고 그녀와 마주칩니다.",
            }
        }
    ]


def format_character_prompt(char: dict) -> str:
    """캐릭터 정보를 프롬프트로 변환"""
    list_data = char["list_data"]
    detail_data = char.get("detail_data") or {}

    parts = [
        f"제목: {list_data['name']}",
        f"제작자: {list_data['authorname']}",
        f"태그: {', '.join(list_data['tags']) if list_data['tags'] else '없음'}",
        f"다운로드: {list_data['download']}",
        f"로어북: {'있음' if list_data['haslore'] else '없음'}",
        f"에셋: {'있음' if list_data['hasAsset'] else '없음'}",
        "",
        f"설명:\n{list_data['desc'][:1000]}",
    ]

    if detail_data:
        if detail_data.get("description"):
            parts.append(f"\n상세 설명:\n{detail_data['description'][:2000]}")
        if detail_data.get("personality"):
            parts.append(f"\n성격:\n{detail_data['personality'][:500]}")
        if detail_data.get("scenario"):
            parts.append(f"\n시나리오:\n{detail_data['scenario'][:500]}")

    return "\n".join(parts)


def test_model(client: Groq, model: str, prompt: str) -> dict:
    """단일 모델 테스트"""
    start = time.time()
    error = None
    response_text = ""

    try:
        # 기본 파라미터
        params = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
        }

        # reasoning_format hidden 적용
        if model in REASONING_HIDDEN_MODELS:
            params["reasoning_format"] = "hidden"

        response = client.chat.completions.create(**params)  # type: ignore
        response_text = response.choices[0].message.content
        elapsed = time.time() - start

        # JSON 파싱 시도
        clean_text = response_text.strip()

        # <think>...</think> 블록 제거
        clean_text = re.sub(r"<think>.*?</think>", "", clean_text, flags=re.DOTALL).strip()

        # ```json ... ``` 블록 제거
        if clean_text.startswith("```"):
            lines = clean_text.split("\n")
            clean_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        parsed = json.loads(clean_text)

    except json.JSONDecodeError as e:
        elapsed = time.time() - start
        error = f"JSON 파싱 실패: {e}"
        parsed = None
    except Exception as e:
        elapsed = time.time() - start
        error = str(e)
        parsed = None

    return {
        "model": model,
        "elapsed": elapsed,
        "error": error,
        "raw_response": response_text[:500] if response_text else None,
        "parsed": parsed,
    }


def print_result(result: dict, char_name: str):
    """결과 출력"""
    print(f"\n{'='*60}")
    print(f"모델: {result['model']}")
    print(f"캐릭터: {char_name}")
    print(f"소요 시간: {result['elapsed']:.2f}초")

    if result["error"]:
        print(f"❌ 오류: {result['error']}")
        if result["raw_response"]:
            print(f"원본 응답: {result['raw_response'][:200]}...")
    else:
        print("✅ 성공")
        if result["parsed"]:
            print(json.dumps(result["parsed"], ensure_ascii=False, indent=2))


def main():
    client = Groq()

    # 테스트 캐릭터 로드 (더 많이)
    chars = load_test_characters(5)
    print(f"테스트 캐릭터 {len(chars)}개 로드됨")

    # 각 모델 테스트
    results = []

    for char in chars:
        char_name = char["list_data"]["name"]
        prompt = format_character_prompt(char)
        print(f"\n\n{'#'*60}")
        print(f"# 캐릭터: {char_name}")
        print(f"{'#'*60}")

        for model in MODELS:
            print(f"\n테스트 중: {model}...")
            result = test_model(client, model, prompt)
            result["char_name"] = char_name
            results.append(result)
            print_result(result, char_name)

    # 상세 평가
    print("\n\n" + "=" * 80)
    print("## 상세 평가")
    print("=" * 80)

    # 허용된 장르 목록
    VALID_GENRES = {
        "fantasy", "romance", "school", "scifi", "modern", "historical",
        "horror", "comedy", "dark_fantasy", "isekai", "simulator",
        "game_original", "anime_original"
    }

    # 모델별 평가
    model_scores = {}

    for model in MODELS:
        model_results = [r for r in results if r["model"] == model]
        successes = [r for r in model_results if not r["error"]]

        scores = {
            "success_rate": len(successes) / len(model_results) if model_results else 0,
            "avg_time": sum(r["elapsed"] for r in model_results) / len(model_results) if model_results else 0,
            "genre_compliance": 0,  # 유효 장르만 사용했는지
            "traits_extracted": 0,  # character_traits 추출 개수
            "summary_length": 0,    # 요약 평균 길이
            "source_accuracy": 0,   # null 또는 유효한 값 사용
        }

        if successes:
            genre_scores = []
            traits_counts = []
            summary_lengths = []
            source_scores = []

            for r in successes:
                parsed = r.get("parsed", {})
                if not parsed:
                    continue

                # 장르 준수율
                genres = set(parsed.get("genres", []))
                if genres:
                    valid_count = len(genres & VALID_GENRES)
                    genre_scores.append(valid_count / len(genres))
                else:
                    genre_scores.append(1.0)

                # traits 추출
                traits = parsed.get("character_traits", [])
                traits_counts.append(len(traits))

                # 요약 길이
                summary = parsed.get("summary", "")
                summary_lengths.append(len(summary))

                # source 정확도 (null 또는 문자열, "OC"는 부정확)
                source = parsed.get("source")
                if source is None or (isinstance(source, str) and source.lower() != "oc"):
                    source_scores.append(1.0)
                else:
                    source_scores.append(0.5)

            scores["genre_compliance"] = sum(genre_scores) / len(genre_scores) if genre_scores else 0
            scores["traits_extracted"] = sum(traits_counts) / len(traits_counts) if traits_counts else 0
            scores["summary_length"] = sum(summary_lengths) / len(summary_lengths) if summary_lengths else 0
            scores["source_accuracy"] = sum(source_scores) / len(source_scores) if source_scores else 0

        model_scores[model] = scores

    # 점수 출력
    print("\n### 세부 점수")
    print(f"{'모델':<45} {'성공률':<8} {'시간':<8} {'장르준수':<8} {'traits':<8} {'요약길이':<8} {'source':<8}")
    print("-" * 100)

    for model in MODELS:
        s = model_scores[model]
        print(f"{model:<45} {s['success_rate']*100:>5.0f}%   {s['avg_time']:>5.2f}s  {s['genre_compliance']*100:>5.0f}%    {s['traits_extracted']:>5.1f}    {s['summary_length']:>5.0f}    {s['source_accuracy']*100:>5.0f}%")

    # 종합 점수 계산
    print("\n### 종합 점수 (가중치 적용)")
    print("- 성공률: 30%, 속도: 15%, 장르준수: 20%, traits: 15%, 요약: 10%, source: 10%")
    print()

    final_scores = {}
    for model in MODELS:
        s = model_scores[model]
        # 속도 점수: 가장 빠른 모델 기준 정규화 (빠를수록 높음)
        min_time = min(model_scores[m]["avg_time"] for m in MODELS if model_scores[m]["avg_time"] > 0)
        max_time = max(model_scores[m]["avg_time"] for m in MODELS)
        time_score = 1 - (s["avg_time"] - min_time) / (max_time - min_time) if max_time > min_time else 1

        # traits 점수: 최대값 기준 정규화
        max_traits = max(model_scores[m]["traits_extracted"] for m in MODELS)
        traits_score = s["traits_extracted"] / max_traits if max_traits > 0 else 0

        # 요약 점수: 적정 길이(30-80자) 기준
        summary_score = min(s["summary_length"] / 50, 1.0) if s["summary_length"] > 0 else 0

        final = (
            s["success_rate"] * 0.30 +
            time_score * 0.15 +
            s["genre_compliance"] * 0.20 +
            traits_score * 0.15 +
            summary_score * 0.10 +
            s["source_accuracy"] * 0.10
        )
        final_scores[model] = final

    # 순위 정렬
    ranked = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)

    print(f"{'순위':<4} {'모델':<50} {'종합점수':<10}")
    print("-" * 70)
    for rank, (model, score) in enumerate(ranked, 1):
        print(f"{rank:<4} {model:<50} {score*100:>6.1f}점")

    # 최종 추천
    print("\n" + "=" * 80)
    print("## 최종 추천")
    print("=" * 80)
    print(f"\n🥇 1위: {ranked[0][0]} ({ranked[0][1]*100:.1f}점)")
    print(f"🥈 2위: {ranked[1][0]} ({ranked[1][1]*100:.1f}점)")
    print(f"🥉 3위: {ranked[2][0]} ({ranked[2][1]*100:.1f}점)")


if __name__ == "__main__":
    main()
