"""LLM 클라이언트 (5개 모델 폴백 + Rate Limit 처리)"""

import json
import re
import time
import random
from typing import Optional
from threading import Lock

from groq import Groq, RateLimitError, APIError, APIConnectionError

from .models import CharacterTags, TaggingResult

# 폴백 순서 (평가 결과 기반)
FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llama-3.3-70b-versatile",
    "moonshotai/kimi-k2-instruct",
    "moonshotai/kimi-k2-instruct-0905",
]

# reasoning_format hidden 적용 모델
REASONING_HIDDEN_MODELS = {"qwen/qwen3-32b"}

SYSTEM_PROMPT = """다음 AI 캐릭터 정보를 분석하여 메타데이터를 JSON으로 추출하세요.

추출할 항목:
- content_rating: "sfw" | "nsfw" | "unknown" (성적 콘텐츠 포함 여부)
- genres: 해당하는 장르 목록 (자유롭게 작성, 예: fantasy, romance, school, scifi, modern, historical, horror, comedy, dark_fantasy, isekai, simulator, action, mystery, slice_of_life 등)
- setting: 시대/배경 설정 (modern, medieval, futuristic, contemporary, fantasy_world 등)
- character_gender: 봇의 주요 캐릭터 성별 (female, male, multiple, other, unknown 중 선택)
  - 중요: 유저가 맡는 역할이 아닌, 봇이 연기하는 NPC/AI 캐릭터의 성별을 기준으로 판단
  - 시뮬레이터/RPG 봇의 경우 유저가 상호작용하는 주요 NPC들의 성별 기준
  - 여러 캐릭터가 등장하면 "multiple", 주로 여캐면 "female", 주로 남캐면 "male"
- character_traits: 성격 특성 목록 (yandere, tsundere, kuudere, dandere, mesu_gaki 등)
- source: 원작이 있다면 원작명 (genshin_impact, arknights 등), OC면 null
- language: 봇이 롤플레이 시 사용하는 주 언어 (korean, english, japanese, multilingual, other 중 선택)
  - 설명(description)이 아닌 실제 대화/시나리오/first_message 언어 기준
  - korean/english/japanese 외 단일 언어는 "other" 선택
  - 여러 언어를 지원하는 경우 "multilingual" 선택
- summary: 캐릭터에 대한 한 줄 요약 (한국어)
- description: 캐릭터에 대한 상세 설명 (한국어, 100-500자). 캐릭터의 배경, 성격, 스토리 설정 등을 포함하여 자세히 서술.

JSON만 출력하세요. 다른 설명은 필요 없습니다."""


class LLMClient:
    """Groq LLM 클라이언트 (폴백 + Rate Limit 처리)"""

    def __init__(
        self,
        models: Optional[list[str]] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        self.client = Groq()
        self.models = models or FALLBACK_MODELS
        self.max_retries = max_retries
        self.base_delay = base_delay

        # 모델별 rate limit 상태 추적
        self._rate_limited_until: dict[str, float] = {}
        self._lock = Lock()

    def _parse_response(self, text: str) -> dict:
        """LLM 응답에서 JSON 추출"""
        clean_text = text.strip()

        # <think>...</think> 블록 제거
        clean_text = re.sub(
            r"<think>.*?</think>", "", clean_text, flags=re.DOTALL
        ).strip()

        # ```json ... ``` 블록 추출
        if clean_text.startswith("```"):
            lines = clean_text.split("\n")
            clean_text = "\n".join(
                lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            )

        return json.loads(clean_text)

    def _is_rate_limited(self, model: str) -> bool:
        """모델이 현재 rate limit 상태인지 확인"""
        with self._lock:
            if model not in self._rate_limited_until:
                return False
            return time.time() < self._rate_limited_until[model]

    def _call_model_with_retry(
        self, model: str, prompt: str
    ) -> tuple[Optional[dict], Optional[str], Optional[str]]:
        """단일 모델 호출 (재시도 포함)

        Returns:
            (parsed_json, raw_response, error_message)
        """
        # Rate limit 상태면 스킵
        with self._lock:
            if model in self._rate_limited_until:
                if time.time() < self._rate_limited_until[model]:
                    remaining = self._rate_limited_until[model] - time.time()
                    return None, None, f"Rate limited for {remaining:.0f}s more"

        for attempt in range(self.max_retries):
            try:
                params = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2048,
                }

                # reasoning_format hidden 적용
                if model in REASONING_HIDDEN_MODELS:
                    params["reasoning_format"] = "hidden"

                response = self.client.chat.completions.create(**params)  # type: ignore
                response_text = response.choices[0].message.content

                parsed = self._parse_response(response_text)
                return parsed, response_text, None

            except RateLimitError as e:
                # Rate limit 발생 - 대기 시간 추출
                retry_after = 60  # 기본값
                error_msg = str(e)

                # "retry after X" 패턴에서 시간 추출 시도
                if "retry after" in error_msg.lower():
                    import re as regex
                    match = regex.search(r"retry after (\d+)", error_msg.lower())
                    if match:
                        retry_after = int(match.group(1))

                # 모델별 rate limit 상태 기록
                with self._lock:
                    self._rate_limited_until[model] = time.time() + retry_after
                print(f"\n⚠️  {model} rate limit! {retry_after}초 대기 필요")

                # 마지막 시도가 아니면 대기 후 재시도
                if attempt < self.max_retries - 1:
                    wait_time = min(retry_after, 30) + random.uniform(1, 5)
                    print(f"   {wait_time:.1f}초 대기 후 재시도...")
                    time.sleep(wait_time)
                else:
                    return None, None, f"Rate limit: {error_msg}"

            except APIConnectionError as e:
                # 연결 에러 - 재시도
                wait_time = (2**attempt) * self.base_delay + random.uniform(0, 1)
                print(f"\n⚠️  연결 에러: {e}, {wait_time:.1f}초 후 재시도...")
                time.sleep(wait_time)

            except APIError as e:
                # 기타 API 에러
                if e.status_code and e.status_code >= 500:  # type: ignore
                    # 서버 에러 - 재시도
                    wait_time = (2**attempt) * self.base_delay + random.uniform(0, 1)
                    print(f"\n⚠️  서버 에러 ({e.status_code}), {wait_time:.1f}초 후 재시도...")  # type: ignore
                    time.sleep(wait_time)
                else:
                    # 클라이언트 에러 - 스킵
                    return None, None, str(e)

            except json.JSONDecodeError as e:
                # JSON 파싱 실패 - 다음 모델로
                return None, response_text if "response_text" in dir() else None, f"JSON 파싱 실패: {e}"

            except Exception as e:
                return None, None, str(e)

        return None, None, "최대 재시도 횟수 초과"

    def tag_character(self, uuid: str, prompt: str) -> TaggingResult:
        """캐릭터 태깅 (폴백 + Rate Limit 처리)"""
        models_tried = []
        last_error = None
        last_raw = None

        for model in self.models:
            models_tried.append(model)

            parsed, raw_response, error = self._call_model_with_retry(model, prompt)

            if parsed:
                # 성공
                tags = CharacterTags(
                    content_rating=parsed.get("content_rating", "unknown"),
                    genres=parsed.get("genres", []),
                    setting=parsed.get("setting", ""),
                    character_gender=parsed.get("character_gender", "other"),
                    character_traits=parsed.get("character_traits", []),
                    source=parsed.get("source"),
                    language=parsed.get("language", "english"),
                    summary=parsed.get("summary", ""),
                    description=parsed.get("description", ""),
                )

                return TaggingResult(
                    uuid=uuid,
                    tags=tags,
                    model_used=model,
                    models_tried=models_tried,
                    tagged_at=int(time.time()),
                )

            # 실패 - 에러 기록 후 다음 모델 시도
            last_error = error
            if raw_response:
                last_raw = raw_response

        # 모든 모델 실패
        return TaggingResult(
            uuid=uuid,
            tags=None,
            model_used="",
            models_tried=models_tried,
            error=last_error,
            raw_response=last_raw[:500] if last_raw else None,
            tagged_at=int(time.time()),
        )

    def wait_for_rate_limit_reset(self) -> float:
        """모든 모델의 rate limit이 풀릴 때까지 대기

        Returns:
            대기한 시간 (초)
        """
        with self._lock:
            if not self._rate_limited_until:
                return 0

            max_wait = max(self._rate_limited_until.values()) - time.time()
            if max_wait <= 0:
                self._rate_limited_until.clear()
                return 0

        print(f"\n⏳ Rate limit 해제 대기 중... ({max_wait:.0f}초)")
        time.sleep(max_wait + 1)
        
        with self._lock:
            self._rate_limited_until.clear()
        return max_wait
