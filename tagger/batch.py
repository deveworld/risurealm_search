"""Groq Batch API를 이용한 대량 태깅"""

import json
import time
from pathlib import Path
from typing import Optional

from groq import Groq

from .client import SYSTEM_PROMPT
from .models import CharacterTags, TaggedCharacter, ContentRating, CharacterGender, Language
from .tagger import format_character_prompt, load_characters

# 배치용 모델 (gpt-oss-120b: 한국어 품질 우수)
BATCH_MODEL = "openai/gpt-oss-120b"


def parse_response(text: str) -> Optional[dict]:
    """LLM 응답에서 JSON 추출"""
    import re

    clean_text = text.strip()

    # <think>...</think> 블록 제거
    clean_text = re.sub(r"<think>.*?</think>", "", clean_text, flags=re.DOTALL).strip()

    # ```json ... ``` 블록 추출
    if clean_text.startswith("```"):
        lines = clean_text.split("\n")
        clean_text = "\n".join(
            lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        )

    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        return None


class BatchTagger:
    """Groq Batch API를 이용한 대량 태깅"""

    def __init__(
        self,
        data_dir: Path = Path("data"),
        model: str = BATCH_MODEL,
    ):
        self.data_dir = data_dir
        self.model = model
        self.client = Groq()

        self.characters_file = data_dir / "characters.jsonl"
        self.tagged_file = data_dir / "tagged.jsonl"
        self.batch_input_file = data_dir / "batch_input.jsonl"
        self.batch_output_file = data_dir / "batch_output.jsonl"
        self.progress_file = data_dir / "batch_progress.json"

    def _load_progress(self) -> dict:
        """진행 상황 로드"""
        if self.progress_file.exists():
            with open(self.progress_file, "r") as f:
                return json.load(f)
        return {"batch_id": None, "file_id": None, "status": None}

    def _save_progress(self, progress: dict):
        """진행 상황 저장"""
        with open(self.progress_file, "w") as f:
            json.dump(progress, f, indent=2)

    def prepare_batch(self, limit: int = 0, skip_existing: bool = True) -> int:
        """배치 입력 파일 생성

        Args:
            limit: 처리할 최대 캐릭터 수 (0이면 전체)
            skip_existing: 이미 태깅된 캐릭터 건너뛰기

        Returns:
            생성된 요청 수
        """
        if not self.characters_file.exists():
            raise FileNotFoundError(f"캐릭터 파일이 없습니다: {self.characters_file}")

        # 기존 태깅된 UUID 로드
        existing_uuids = set()
        if skip_existing and self.tagged_file.exists():
            with open(self.tagged_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        existing_uuids.add(data["uuid"])
            print(f"기존 태깅: {len(existing_uuids)}개")

        # 배치 입력 파일 생성
        count = 0
        with open(self.batch_input_file, "w") as f:
            for char in load_characters(self.characters_file):
                if char["uuid"] in existing_uuids:
                    continue

                prompt = format_character_prompt(char)

                batch_request = {
                    "custom_id": char["uuid"],
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2048,
                    }
                }

                f.write(json.dumps(batch_request, ensure_ascii=False) + "\n")
                count += 1

                if limit > 0 and count >= limit:
                    break

        print(f"배치 입력 파일 생성: {count}개 요청")
        print(f"파일: {self.batch_input_file}")
        return count

    def upload_and_create_batch(self, completion_window: str = "24h") -> str:
        """배치 파일 업로드 및 배치 작업 생성

        Args:
            completion_window: 완료 기한 ("24h" 등)

        Returns:
            배치 ID
        """
        if not self.batch_input_file.exists():
            raise FileNotFoundError("배치 입력 파일이 없습니다. prepare_batch()를 먼저 실행하세요.")

        # 파일 업로드
        print("배치 파일 업로드 중...")
        with open(self.batch_input_file, "rb") as f:
            file_response = self.client.files.create(file=f, purpose="batch")

        file_id = file_response.id
        if file_id is None:
            raise ValueError("파일 업로드 실패: file_id가 없습니다")
        print(f"업로드 완료: {file_id}")

        # 배치 작업 생성
        print("배치 작업 생성 중...")
        batch_response = self.client.batches.create(
            completion_window=completion_window,
            endpoint="/v1/chat/completions",
            input_file_id=file_id,
        )

        batch_id = batch_response.id
        print(f"배치 작업 생성: {batch_id}")

        # 진행 상황 저장
        self._save_progress({
            "batch_id": batch_id,
            "file_id": file_id,
            "status": "created",
            "created_at": int(time.time()),
        })

        return batch_id

    def check_status(self, batch_id: Optional[str] = None) -> dict:
        """배치 작업 상태 확인

        Returns:
            상태 정보 딕셔너리
        """
        if batch_id is None:
            progress = self._load_progress()
            batch_id = progress.get("batch_id")

        if not batch_id:
            raise ValueError("배치 ID가 없습니다.")

        response = self.client.batches.retrieve(batch_id)

        status = {
            "batch_id": batch_id,
            "status": response.status,
            "created_at": response.created_at,
            "completed_at": response.completed_at,
            "failed_at": response.failed_at,
            "expired_at": response.expired_at,
            "request_counts": {
                "total": response.request_counts.total if response.request_counts else 0,
                "completed": response.request_counts.completed if response.request_counts else 0,
                "failed": response.request_counts.failed if response.request_counts else 0,
            },
            "output_file_id": response.output_file_id,
            "error_file_id": response.error_file_id,
        }

        # 진행 상황 업데이트
        progress = self._load_progress()
        progress["status"] = response.status
        progress["output_file_id"] = response.output_file_id
        progress["error_file_id"] = response.error_file_id
        self._save_progress(progress)

        return status

    def wait_for_completion(
        self,
        batch_id: Optional[str] = None,
        poll_interval: int = 60,
        timeout: int = 86400,  # 24시간
    ) -> dict:
        """배치 작업 완료 대기

        Args:
            batch_id: 배치 ID (없으면 저장된 것 사용)
            poll_interval: 상태 확인 간격 (초)
            timeout: 최대 대기 시간 (초)

        Returns:
            최종 상태
        """
        start_time = time.time()

        while True:
            status = self.check_status(batch_id)

            print(f"[{time.strftime('%H:%M:%S')}] 상태: {status['status']}, "
                  f"완료: {status['request_counts']['completed']}/{status['request_counts']['total']}")

            if status["status"] == "completed":
                print("✅ 배치 작업 완료!")
                return status

            if status["status"] in ("failed", "expired", "cancelled"):
                print(f"❌ 배치 작업 실패: {status['status']}")
                return status

            elapsed = time.time() - start_time
            if elapsed > timeout:
                print(f"⚠️ 타임아웃 ({timeout}초)")
                return status

            time.sleep(poll_interval)

    def download_results(self, output_file_id: Optional[str] = None) -> int:
        """배치 결과 다운로드

        Returns:
            다운로드된 결과 수
        """
        if output_file_id is None:
            progress = self._load_progress()
            output_file_id = progress.get("output_file_id")

        if not output_file_id:
            raise ValueError("출력 파일 ID가 없습니다.")

        print(f"결과 다운로드 중: {output_file_id}")
        response = self.client.files.content(output_file_id)
        response.write_to_file(str(self.batch_output_file))

        # 결과 수 카운트
        count = 0
        with open(self.batch_output_file, "r") as f:
            for line in f:
                if line.strip():
                    count += 1

        print(f"다운로드 완료: {count}개 결과")
        return count

    def process_results(self, replace_existing: bool = False) -> dict:
        """배치 결과를 tagged.jsonl로 변환

        Args:
            replace_existing: True면 기존 데이터 삭제 후 새로 생성

        Returns:
            처리 통계
        """
        if not self.batch_output_file.exists():
            raise FileNotFoundError("배치 출력 파일이 없습니다.")

        # --all 옵션일 때 기존 파일 비우기
        if replace_existing:
            print("기존 태깅 데이터 초기화 중...")
            if self.tagged_file.exists():
                self.tagged_file.unlink()
                print(f"  삭제: {self.tagged_file}")

        # 캐릭터 데이터 로드 (UUID -> 캐릭터 매핑)
        char_map = {}
        for char in load_characters(self.characters_file):
            char_map[char["uuid"]] = char

        # 기존 태깅 결과 로드 (중복 방지)
        existing_uuids = set()
        if self.tagged_file.exists():
            with open(self.tagged_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        existing_uuids.add(data["uuid"])

        stats = {"success": 0, "failed": 0, "skipped": 0}

        with open(self.batch_output_file, "r") as f_in, \
             open(self.tagged_file, "a") as f_out:

            for line in f_in:
                if not line.strip():
                    continue

                result = json.loads(line)
                uuid = result["custom_id"]

                # 이미 처리된 경우 스킵
                if uuid in existing_uuids:
                    stats["skipped"] += 1
                    continue

                # 캐릭터 데이터 가져오기
                char = char_map.get(uuid)
                if not char:
                    stats["failed"] += 1
                    continue

                # 응답 파싱
                response_body = result.get("response", {}).get("body", {})
                choices = response_body.get("choices", [])

                if not choices:
                    stats["failed"] += 1
                    continue

                content = choices[0].get("message", {}).get("content", "")
                parsed = parse_response(content)

                if parsed:
                    # enum 값 안전하게 변환 (유효하지 않은 값은 기본값 사용)
                    try:
                        content_rating = ContentRating(parsed.get("content_rating", "unknown"))
                    except ValueError:
                        content_rating = ContentRating.UNKNOWN

                    try:
                        character_gender = CharacterGender(parsed.get("character_gender", "other"))
                    except ValueError:
                        character_gender = CharacterGender.OTHER

                    try:
                        language = Language(parsed.get("language", "english"))
                    except ValueError:
                        language = Language.OTHER

                    # source 처리: 문자열, 리스트, null 모두 지원
                    raw_source = parsed.get("source")
                    if raw_source is None:
                        source = []
                    elif isinstance(raw_source, str):
                        source = [raw_source] if raw_source else []
                    elif isinstance(raw_source, list):
                        source = [s for s in raw_source if isinstance(s, str) and s]
                    else:
                        source = []

                    tags = CharacterTags(
                        content_rating=content_rating,
                        character_gender=character_gender,
                        source=source,
                        language=language,
                        summary=parsed.get("summary", ""),
                        description=parsed.get("description", ""),
                    )

                    # TaggedCharacter 생성
                    list_data = char["list_data"]
                    tagged = TaggedCharacter(
                        uuid=uuid,
                        nsfw=char["nsfw"],
                        name=list_data["name"],
                        desc=list_data["desc"][:500],
                        download=list_data["download"],
                        authorname=list_data["authorname"] or "",
                        tags=list_data["tags"],
                        haslore=list_data["haslore"],
                        hasAsset=list_data["hasAsset"],
                        img=list_data.get("img", ""),
                        has_detail=char.get("detail_data") is not None,
                        detail_source=char["detail_source"],
                        llm_tags=tags,
                        tagging_model=self.model,
                        tagging_error=None,
                        scraped_at=char["scraped_at"],
                        tagged_at=int(time.time()),
                    )

                    f_out.write(tagged.model_dump_json() + "\n")
                    existing_uuids.add(uuid)
                    stats["success"] += 1
                else:
                    stats["failed"] += 1

        print(f"처리 완료: 성공 {stats['success']}, 실패 {stats['failed']}, 스킵 {stats['skipped']}")
        return stats

    def run_full_batch(
        self,
        limit: int = 0,
        skip_existing: bool = True,
        completion_window: str = "24h",
        poll_interval: int = 60,
    ) -> dict:
        """전체 배치 프로세스 실행

        Args:
            limit: 처리할 최대 캐릭터 수
            skip_existing: 기존 태깅 건너뛰기
            completion_window: 완료 기한
            poll_interval: 상태 확인 간격

        Returns:
            최종 통계
        """
        # --all 옵션일 때 기존 파일 비우기
        if not skip_existing:
            print("기존 태깅 데이터 초기화 중...")
            if self.tagged_file.exists():
                self.tagged_file.unlink()
                print(f"  삭제: {self.tagged_file}")

        # 1. 배치 준비
        count = self.prepare_batch(limit=limit, skip_existing=skip_existing)
        if count == 0:
            print("처리할 캐릭터가 없습니다.")
            return {"prepared": 0}

        # 2. 업로드 및 배치 생성
        batch_id = self.upload_and_create_batch(completion_window=completion_window)

        # 3. 완료 대기
        status = self.wait_for_completion(batch_id, poll_interval=poll_interval)

        if status["status"] != "completed":
            return {"error": status["status"], "batch_id": batch_id}

        # 4. 결과 다운로드
        self.download_results(status["output_file_id"])

        # 5. 결과 처리
        stats = self.process_results()

        return {
            "prepared": count,
            "batch_id": batch_id,
            **stats,
        }
