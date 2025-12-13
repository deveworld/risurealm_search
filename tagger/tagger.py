"""메인 태깅 로직 (병렬 처리 + Rate Limit 대응 + Graceful Shutdown)"""

import json
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Generator

from .client import LLMClient
from .models import TaggedCharacter, TaggingResult


class TaggingProgress:
    """태깅 진행 상황 추적 (tagged.jsonl 기반, 스레드 안전)"""

    def __init__(self, tagged_file: Path):
        self.tagged_file = tagged_file
        self._lock = Lock()
        self._completed_uuids = self._load()

    def _load(self) -> set:
        """tagged.jsonl에서 완료된 UUID 로드"""
        completed = set()
        if self.tagged_file.exists():
            with open(self.tagged_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        uuid = item.get("uuid")
                        if uuid:
                            completed.add(uuid)
        return completed

    def mark_completed(self, uuid: str):
        """완료 표시 (메모리에만, 파일은 Tagger에서 직접 씀)"""
        with self._lock:
            self._completed_uuids.add(uuid)

    def is_done(self, uuid: str) -> bool:
        with self._lock:
            return uuid in self._completed_uuids

    def get_completed_count(self) -> int:
        with self._lock:
            return len(self._completed_uuids)


def load_characters(path: Path) -> Generator[dict, None, None]:
    """JSONL에서 캐릭터 로드 (제너레이터, UUID 중복 제거)"""
    seen_uuids = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                char = json.loads(line)
                uuid = char.get("uuid")
                if uuid and uuid not in seen_uuids:
                    seen_uuids.add(uuid)
                    yield char


def count_characters(path: Path) -> int:
    """캐릭터 수 카운트 (UUID 중복 제거)"""
    seen_uuids = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                char = json.loads(line)
                uuid = char.get("uuid")
                if uuid:
                    seen_uuids.add(uuid)
    return len(seen_uuids)


def format_character_prompt(char: dict) -> str:
    """캐릭터 정보를 태깅 프롬프트로 변환"""
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
        if detail_data.get("first_mes"):
            parts.append(f"\n첫 메시지:\n{detail_data['first_mes'][:1500]}")

    return "\n".join(parts)


def tag_to_output(char: dict, result: TaggingResult) -> TaggedCharacter:
    """태깅 결과를 최종 출력 형식으로 변환"""
    list_data = char["list_data"]

    return TaggedCharacter(
        uuid=char["uuid"],
        nsfw=char["nsfw"],
        name=list_data["name"],
        desc=list_data["desc"][:500],
        download=list_data["download"],
        authorname=list_data["authorname"] or "",
        tags=list_data["tags"],
        haslore=list_data["haslore"],
        hasAsset=list_data["hasAsset"],
        has_detail=char.get("detail_data") is not None,
        detail_source=char["detail_source"],
        llm_tags=result.tags,
        tagging_model=result.model_used,
        tagging_error=result.error,
        scraped_at=char["scraped_at"],
        tagged_at=result.tagged_at,
    )


class Tagger:
    """캐릭터 태깅 처리 (병렬 처리 + Rate Limit 대응 + Graceful Shutdown)"""

    def __init__(self, data_dir: Path, delay: float = 0.5, max_workers: int = 3):
        self.data_dir = data_dir
        self.delay = delay
        self.max_workers = max_workers

        self.characters_file = data_dir / "characters.jsonl"
        self.tagged_file = data_dir / "tagged.jsonl"

        self.progress = TaggingProgress(self.tagged_file)

        # Graceful shutdown
        self._shutdown_requested = False
        self._original_sigint = None
        self._original_sigterm = None

        # 스레드 안전 파일 쓰기
        self._file_lock = Lock()

        # 통계
        self._stats_lock = Lock()
        self._processed = 0
        self._success = 0
        self._failed = 0

    def _setup_signal_handlers(self):
        """시그널 핸들러 설정"""
        self._original_sigint = signal.signal(signal.SIGINT, self._handle_shutdown)
        self._original_sigterm = signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _restore_signal_handlers(self):
        """원래 시그널 핸들러 복원"""
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm:
            signal.signal(signal.SIGTERM, self._original_sigterm)

    def _handle_shutdown(self, signum, frame):
        """Graceful shutdown 핸들러"""
        if self._shutdown_requested:
            print("\n\n강제 종료...")
            sys.exit(1)

        self._shutdown_requested = True
        print("\n\n⚠️  종료 요청됨. 진행 중인 작업 완료 후 저장 예정...")

    def _append_result(self, tagged: TaggedCharacter):
        """태그 결과를 파일에 추가 (스레드 안전)"""
        with self._file_lock:
            with open(self.tagged_file, "a", encoding="utf-8") as f:
                f.write(tagged.model_dump_json() + "\n")

    def _tag_single(self, client: LLMClient, char: dict) -> tuple[dict, TaggingResult]:
        """단일 캐릭터 태깅 (스레드에서 실행)"""
        uuid = char["uuid"]
        prompt = format_character_prompt(char)
        result = client.tag_character(uuid, prompt)
        return char, result

    def run(self, count: int = 0) -> dict:
        """태깅 실행 (병렬 처리)

        Args:
            count: 처리할 캐릭터 수 (0이면 전체)

        Returns:
            통계 정보
        """
        if not self.characters_file.exists():
            raise FileNotFoundError(f"캐릭터 파일이 없습니다: {self.characters_file}")

        # 시그널 핸들러 설정
        self._setup_signal_handlers()

        total = count_characters(self.characters_file)
        skipped = 0

        # 처리할 캐릭터 수집
        pending_chars = []
        for char in load_characters(self.characters_file):
            if self.progress.is_done(char["uuid"]):
                skipped += 1
                continue
            pending_chars.append(char)
            if count > 0 and len(pending_chars) >= count:
                break

        pending_count = len(pending_chars)

        print(f"총 {total}개 캐릭터, 태깅 시작...")
        print(f"이미 완료: {skipped}개")
        print(f"처리 예정: {pending_count}개")
        print(f"동시 처리: {self.max_workers}개")
        print()

        if not pending_chars:
            print("처리할 캐릭터가 없습니다.")
            return {"completed": skipped, "success": 0, "failed": 0}

        start_time = time.time()

        # 클라이언트 한 번만 생성하여 공유 (Rate Limit 상태 공유를 위해)
        client = LLMClient()

        try:
            # ThreadPoolExecutor로 병렬 처리
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 각 스레드가 자체 LLMClient 인스턴스 사용
                futures = {}

                for char in pending_chars:
                    if self._shutdown_requested:
                        break

                    future = executor.submit(self._tag_single, client, char)
                    futures[future] = char

                # 결과 수집
                for future in as_completed(futures):
                    if self._shutdown_requested:
                        # 남은 작업 취소
                        for f in futures:
                            f.cancel()
                        break

                    try:
                        char, result = future.result()

                        with self._stats_lock:
                            self._processed += 1
                            processed = self._processed

                        name = char["list_data"]["name"]

                        if result.tags:
                            with self._stats_lock:
                                self._success += 1
                            self.progress.mark_completed(char["uuid"])
                            model_short = result.model_used.split("/")[-1][:15]
                            print(f"[{processed}/{pending_count}] {name[:30]:<30} OK ({model_short})")
                        else:
                            with self._stats_lock:
                                self._failed += 1
                            # 실패해도 tagged.jsonl에 기록 (tagging_error 포함)
                            self.progress.mark_completed(char["uuid"])
                            error_short = result.error[:35] if result.error else "unknown"
                            print(f"[{processed}/{pending_count}] {name[:30]:<30} FAIL: {error_short}")

                        # 결과 저장
                        tagged = tag_to_output(char, result)
                        self._append_result(tagged)

                        # 진행률 출력 (50개마다)
                        if processed % 50 == 0:
                            elapsed = time.time() - start_time
                            rate = processed / elapsed if elapsed > 0 else 0
                            remaining = (pending_count - processed) / rate if rate > 0 else 0
                            success_rate = self._success / processed * 100 if processed > 0 else 0
                            print(
                                f"\n--- 진행: {processed}/{pending_count}, "
                                f"성공률: {success_rate:.1f}%, "
                                f"속도: {rate:.1f}/s, "
                                f"남은 시간: {remaining/60:.1f}분 ---\n"
                            )

                    except Exception as e:
                        with self._stats_lock:
                            self._processed += 1
                            self._failed += 1
                        print(f"[ERROR] {e}")

        finally:
            self._restore_signal_handlers()

        # 최종 통계
        elapsed_total = time.time() - start_time
        total_completed = self.progress.get_completed_count()

        print("\n" + "=" * 60)
        print("태깅 완료!" if not self._shutdown_requested else "태깅 중단됨 (재개 가능)")
        print(f"  소요 시간: {elapsed_total/60:.1f}분")
        print(f"  처리: {self._processed}개")
        print(f"  성공: {self._success}개")
        print(f"  실패: {self._failed}개")
        print(f"  속도: {self._processed/elapsed_total:.1f}개/초" if elapsed_total > 0 else "")
        print(f"  총 완료: {total_completed}개")

        if self._shutdown_requested:
            print("\n💡 재개하려면 같은 명령을 다시 실행하세요.")

        return {
            "completed": total_completed,
            "success": self._success,
            "failed": self._failed,
        }
