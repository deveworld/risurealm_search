"""스크래퍼 (병렬 처리 + Rate Limit 대응 + Graceful Shutdown)"""

import asyncio
import json
import signal
import sys
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .client import RisuRealmClient
from .models import CharacterListItem, CharacterDetail, ScrapedCharacter, DetailSource
from .utils import extract_detail, save_jsonl, load_jsonl, append_jsonl, Progress


@dataclass
class ScrapeResult:
    """스크래핑 결과"""
    uuid: str
    nsfw: bool
    list_item: dict
    detail_data: Optional[dict]
    source: str


class RisuRealmScraper:
    def __init__(
        self,
        data_dir: Path = Path("data"),
        delay: float = 0.2,
        max_concurrent: int = 10,
    ):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)

        self.delay = delay
        self.max_concurrent = max_concurrent

        # 파일 경로
        self.list_sfw_path = data_dir / "list_sfw.jsonl"
        self.list_nsfw_path = data_dir / "list_nsfw.jsonl"
        self.types_path = data_dir / "types.json"
        self.characters_path = data_dir / "characters.jsonl"

        self.progress = Progress(data_dir)

        # Graceful shutdown
        self._shutdown_requested = False

        # 통계
        self._stats = {"success": 0, "fail": 0}
        self._stats_lock = asyncio.Lock()

    def _setup_signal_handlers(self):
        """시그널 핸들러 설정 (asyncio 호환)"""
        loop = asyncio.get_event_loop()

        def handle_signal():
            if self._shutdown_requested:
                print("\n\n강제 종료...")
                sys.exit(1)
            self._shutdown_requested = True
            print("\n\n⚠️  종료 요청됨. 진행 중인 작업 완료 후 저장 예정...")

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)

    async def _fetch_types_batch(
        self,
        client: RisuRealmClient,
        items: dict[str, dict],
    ) -> dict[str, str]:
        """캐릭터 타입을 배치로 조회"""
        uuids = list(items.keys())
        total = len(uuids)
        types = {}

        print(f"\n캐릭터 타입 조회 중... ({total}개)")

        batch_size = self.max_concurrent
        for i in range(0, total, batch_size):
            if self._shutdown_requested:
                break

            batch = uuids[i:i + batch_size]
            tasks = [client.fetch_character_type(uuid) for uuid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for uuid, result in zip(batch, results):
                if isinstance(result, Exception):
                    types[uuid] = "normal"
                else:
                    types[uuid] = result

            processed = min(i + batch_size, total)
            if processed % 500 < batch_size or processed == total:
                charx_count = sum(1 for t in types.values() if t == "charx")
                print(f"  타입 조회: {processed}/{total} (charx: {charx_count}개)")

        return types

    async def scrape_list(self) -> dict[str, dict]:
        """SFW/NSFW 전체 목록 수집 + 타입 조회"""
        if self.progress.is_list_completed():
            print("목록 수집 이미 완료됨, 기존 데이터 로드")
            sfw_items = load_jsonl(self.list_sfw_path)
            nsfw_items = load_jsonl(self.list_nsfw_path)

            # UUID 기준 중복 제거, SFW 우선 (양쪽에 있으면 nsfw=False)
            all_items = {}
            for item in nsfw_items:
                all_items[item["id"]] = {"item": item, "nsfw": True, "type": "normal"}
            for item in sfw_items:
                all_items[item["id"]] = {"item": item, "nsfw": False, "type": "normal"}

            print(f"중복 제거 후: {len(all_items)}개")

            # 타입 로드
            if self.types_path.exists():
                print("타입 캐시 로드 중...")
                with open(self.types_path, "r") as f:
                    types = json.load(f)
                
                # 기존 캐시 적용
                for uuid, char_type in types.items():
                    if uuid in all_items:
                        all_items[uuid]["type"] = char_type
                
                print("캐시된 타입 적용 완료.")
            else:
                types = {}

            # 캐시에 없는 항목 확인
            # 'normal'이 기본값이므로, types에 명시적으로 없으면 조회 대상이 될 수 있음
            # 하지만 이미 fetch_types_batch는 결과를 types에 저장하므로, 
            # types 키에 없는 것만 조회하면 됨.
            missing_uuids = [uuid for uuid in all_items if uuid not in types]

            if missing_uuids:
                print(f"새로운 캐릭터 {len(missing_uuids)}개 타입 조회 필요")
                async with RisuRealmClient(
                    delay=self.delay,
                    max_concurrent=self.max_concurrent,
                ) as client:
                    # missing_uuids에 해당하는 항목만 dict로 구성
                    target_items = {uuid: all_items[uuid] for uuid in missing_uuids}
                    new_types = await self._fetch_types_batch(client, target_items)
                    
                    # 결과 병합
                    types.update(new_types)
                    for uuid, char_type in new_types.items():
                        if uuid in all_items:
                            all_items[uuid]["type"] = char_type
                    
                    # 타입 캐시 저장
                    with open(self.types_path, "w", encoding="utf-8") as f:
                        json.dump(types, f, ensure_ascii=False, indent=2)
            
            charx_count = sum(1 for d in all_items.values() if d.get("type") == "charx")
            print(f"타입 준비 완료: normal {len(all_items) - charx_count}개, charx {charx_count}개")

            return all_items

        async with RisuRealmClient(
            delay=self.delay,
            max_concurrent=self.max_concurrent,
        ) as client:
            # SFW 수집
            print("SFW 목록 수집 중...")
            sfw_items = await client.fetch_all_list(
                nsfw=False,
                on_progress=lambda p, n: print(f"  페이지 {p}, 총 {n}개"),
            )
            save_jsonl(sfw_items, self.list_sfw_path)
            print(f"  SFW 완료: {len(sfw_items)}개")

            if self._shutdown_requested:
                print("\n목록 수집 중단됨 (SFW만 완료)")
                nsfw_items = []
            else:
                # NSFW 수집
                print("NSFW 목록 수집 중...")
                nsfw_items = await client.fetch_all_list(
                    nsfw=True,
                    on_progress=lambda p, n: print(f"  페이지 {p}, 총 {n}개"),
                )

                # 중복 제거: SFW에 이미 있는 항목은 NSFW 목록에서 제외
                sfw_ids = {item["id"] for item in sfw_items}
                original_count = len(nsfw_items)
                nsfw_items = [item for item in nsfw_items if item["id"] not in sfw_ids]
                filtered_count = original_count - len(nsfw_items)
                if filtered_count > 0:
                    print(f"  중복 제거: {filtered_count}개 항목이 SFW 목록과 중복되어 제외됨")

                save_jsonl(nsfw_items, self.list_nsfw_path)
                print(f"  NSFW 완료: {len(nsfw_items)}개")

            # UUID 기준 중복 제거, SFW 우선 (양쪽에 있으면 nsfw=False)
            all_items = {}
            for item in nsfw_items:
                all_items[item["id"]] = {"item": item, "nsfw": True, "type": "normal"}
            for item in sfw_items:
                all_items[item["id"]] = {"item": item, "nsfw": False, "type": "normal"}

            print(f"중복 제거 후: {len(all_items)}개")

            # 타입 조회
            if not self._shutdown_requested:
                types = await self._fetch_types_batch(client, all_items)
                for uuid, char_type in types.items():
                    if uuid in all_items:
                        all_items[uuid]["type"] = char_type

                # 타입 캐시 저장
                with open(self.types_path, "w", encoding="utf-8") as f:
                    json.dump(types, f, ensure_ascii=False, indent=2)

                charx_count = sum(1 for d in all_items.values() if d["type"] == "charx")
                print(f"타입 조회 완료 (캐시 저장됨): normal {len(all_items) - charx_count}개, charx {charx_count}개")

        return all_items

    async def _fetch_single(
        self,
        client: RisuRealmClient,
        uuid: str,
        item_data: dict,
    ) -> Optional[ScrapeResult]:
        """단일 캐릭터 상세 정보 조회"""
        if self._shutdown_requested:
            return None

        list_item = item_data["item"]
        nsfw = item_data["nsfw"]
        char_type = item_data.get("type", "normal")

        raw_detail, source = await client.fetch_detail(uuid, char_type)

        detail_data = None
        if raw_detail:
            detail_data = extract_detail(raw_detail, source)

        return ScrapeResult(
            uuid=uuid,
            nsfw=nsfw,
            list_item=list_item,
            detail_data=detail_data,
            source=source,
        )

    async def scrape_details(
        self,
        items: dict[str, dict],
        count: Optional[int] = None,
    ):
        """상세 정보 수집 (병렬 처리)"""
        # 이미 완료된 UUID 제외
        pending_uuids = [
            uuid for uuid in items.keys() if not self.progress.is_detail_done(uuid)
        ]

        if count:
            pending_uuids = pending_uuids[:count]

        total = len(pending_uuids)
        completed = self.progress.get_completed_count()

        print(f"상세 정보 수집: {total}개 대기, {completed}개 완료")
        print(f"동시 처리: {self.max_concurrent}개")

        if not pending_uuids:
            print("수집할 항목이 없습니다.")
            return

        start_time = time.time()
        processed = 0
        success_count = 0
        fail_count = 0

        async with RisuRealmClient(
            delay=self.delay,
            max_concurrent=self.max_concurrent,
        ) as client:
            # 배치로 병렬 처리
            batch_size = self.max_concurrent

            for i in range(0, len(pending_uuids), batch_size):
                if self._shutdown_requested:
                    print(f"\n중단됨. {processed}개 처리 완료.")
                    break

                batch = pending_uuids[i:i + batch_size]

                # 배치 내 병렬 실행
                tasks = [
                    self._fetch_single(client, uuid, items[uuid])
                    for uuid in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 결과 처리
                for result in results:
                    if self._shutdown_requested:
                        break

                    if isinstance(result, Exception):
                        fail_count += 1
                        processed += 1
                        continue

                    if result is None or not isinstance(result, ScrapeResult):
                        continue

                    processed += 1
                    name = result.list_item.get("name", "Unknown")

                    if result.detail_data:
                        success_count += 1
                        status = f"OK ({result.source})"
                    else:
                        fail_count += 1
                        status = "FAIL (list_only)"

                    print(f"[{processed}/{total}] {name[:35]:<35} {status}")

                    # 저장
                    character = ScrapedCharacter(
                        uuid=result.uuid,
                        nsfw=result.nsfw,
                        list_data=CharacterListItem(**result.list_item),
                        detail_data=CharacterDetail(**result.detail_data) if result.detail_data else None,
                        detail_source=DetailSource(result.source),
                        scraped_at=int(time.time()),
                    )
                    append_jsonl(character.model_dump(), self.characters_path)
                    self.progress.mark_detail_completed(result.uuid)

                # 배치 완료 후 진행률 출력
                if processed > 0 and processed % 100 < batch_size:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    remaining = (total - processed) / rate if rate > 0 else 0
                    print(
                        f"\n--- 진행: {processed}/{total} ({processed/total*100:.1f}%), "
                        f"성공: {success_count}, 실패: {fail_count}, "
                        f"속도: {rate:.1f}/s, 예상 남은 시간: {remaining/60:.1f}분 ---\n"
                    )

        # 최종 통계
        elapsed_total = time.time() - start_time
        print("\n" + "=" * 60)
        print("상세 수집 완료!" if not self._shutdown_requested else "상세 수집 중단됨 (재개 가능)")
        print(f"  소요 시간: {elapsed_total/60:.1f}분")
        print(f"  처리: {processed}개")
        print(f"  성공: {success_count}개")
        print(f"  실패: {fail_count}개")
        print(f"  속도: {processed/elapsed_total:.1f}개/초" if elapsed_total > 0 else "")
        print(f"  총 완료: {self.progress.get_completed_count()}개")

        if self._shutdown_requested:
            print("\n💡 재개하려면 같은 명령을 다시 실행하세요.")

    async def run(self, count: Optional[int] = None):
        """전체 스크래핑 실행"""
        print("=== RisuRealm 스크래퍼 시작 ===")
        print()

        # 시그널 핸들러 설정
        try:
            self._setup_signal_handlers()
        except NotImplementedError:
            pass  # Windows

        # 1. 목록 수집
        items = await self.scrape_list()

        if self._shutdown_requested:
            print("\n목록 수집 단계에서 중단됨")
            return

        # 2. 상세 정보 수집
        await self.scrape_details(items, count=count)

        if not self._shutdown_requested:
            print("\n=== 스크래핑 완료 ===")

    def _load_existing_uuids(self) -> set[str]:
        """기존 characters.jsonl에서 UUID 목록 로드"""
        uuids = set()
        if self.characters_path.exists():
            for item in load_jsonl(self.characters_path):
                uuids.add(item["uuid"])
        return uuids

    def _load_existing_characters(self) -> dict[str, dict]:
        """기존 characters.jsonl에서 UUID -> 캐릭터 데이터 매핑"""
        characters = {}
        if self.characters_path.exists():
            for item in load_jsonl(self.characters_path):
                characters[item["uuid"]] = item
        return characters

    async def update(self):
        """최신 캐릭터 업데이트"""
        print("=== RisuRealm 업데이트 시작 ===")
        print()

        # 시그널 핸들러 설정
        try:
            self._setup_signal_handlers()
        except NotImplementedError:
            pass  # Windows

        # 기존 UUID 로드
        existing_uuids = self._load_existing_uuids()
        print(f"기존 캐릭터: {len(existing_uuids)}개")

        async with RisuRealmClient(
            delay=self.delay,
            max_concurrent=self.max_concurrent,
        ) as client:
            # 최신순으로 SFW/NSFW 조회
            print("\n최신 SFW 캐릭터 조회 중...")
            new_sfw = await client.fetch_latest_until_known(
                nsfw=False,
                known_uuids=existing_uuids,
                on_progress=lambda p, n: print(f"  페이지 {p}, 새 캐릭터 {n}개"),
            )
            print(f"  새 SFW: {len(new_sfw)}개")

            if self._shutdown_requested:
                return

            print("\n최신 NSFW 캐릭터 조회 중...")
            new_nsfw = await client.fetch_latest_until_known(
                nsfw=True,
                known_uuids=existing_uuids,
                on_progress=lambda p, n: print(f"  페이지 {p}, 새 캐릭터 {n}개"),
            )
            print(f"  새 NSFW: {len(new_nsfw)}개")

            if self._shutdown_requested:
                return

            # 중복 제거 (SFW 우선)
            all_new = {}
            for item in new_nsfw:
                all_new[item["id"]] = {"item": item, "nsfw": True, "type": "normal"}
            for item in new_sfw:
                all_new[item["id"]] = {"item": item, "nsfw": False, "type": "normal"}

            if not all_new:
                print("\n새로운 캐릭터가 없습니다.")
                return

            print(f"\n총 새 캐릭터: {len(all_new)}개")

            # 타입 조회
            types = await self._fetch_types_batch(client, all_new)
            for uuid, char_type in types.items():
                if uuid in all_new:
                    all_new[uuid]["type"] = char_type

            if self._shutdown_requested:
                return

            # 상세 정보 수집
            print("\n상세 정보 수집 중...")
            success_count = 0
            fail_count = 0

            for i, (uuid, item_data) in enumerate(all_new.items(), 1):
                if self._shutdown_requested:
                    break

                result = await self._fetch_single(client, uuid, item_data)

                if result is None:
                    continue

                name = result.list_item.get("name", "Unknown")

                if result.detail_data:
                    success_count += 1
                    status = f"OK ({result.source})"
                else:
                    fail_count += 1
                    status = "FAIL (list_only)"

                print(f"[{i}/{len(all_new)}] {name[:35]:<35} {status}")

                # 저장
                character = ScrapedCharacter(
                    uuid=result.uuid,
                    nsfw=result.nsfw,
                    list_data=CharacterListItem(**result.list_item),
                    detail_data=CharacterDetail(**result.detail_data) if result.detail_data else None,
                    detail_source=DetailSource(result.source),
                    scraped_at=int(time.time()),
                )
                append_jsonl(character.model_dump(), self.characters_path)
                self.progress.mark_detail_completed(result.uuid)

        print("\n" + "=" * 60)
        print("업데이트 완료!" if not self._shutdown_requested else "업데이트 중단됨")
        print(f"  새 캐릭터: {len(all_new)}개")
        print(f"  성공: {success_count}개")
        print(f"  실패: {fail_count}개")

    async def full_update(self) -> list[str]:
        """전체 목록 확인 후 변경된 캐릭터만 재수집

        Returns:
            변경된 캐릭터 UUID 목록
        """
        print("=== RisuRealm 전체 업데이트 시작 ===")
        print()

        # 시그널 핸들러 설정
        try:
            self._setup_signal_handlers()
        except NotImplementedError:
            pass  # Windows

        # 기존 캐릭터 로드
        existing_chars = self._load_existing_characters()
        print(f"기존 캐릭터: {len(existing_chars)}개")

        # 기존 date 매핑
        existing_dates = {
            uuid: char.get("list_data", {}).get("date", 0)
            for uuid, char in existing_chars.items()
        }

        async with RisuRealmClient(
            delay=self.delay,
            max_concurrent=self.max_concurrent,
        ) as client:
            # 전체 목록 재조회
            print("\nSFW 전체 목록 조회 중...")
            sfw_items = await client.fetch_all_list(
                nsfw=False,
                on_progress=lambda p, n: print(f"  페이지 {p}, 총 {n}개"),
            )

            if self._shutdown_requested:
                return []

            print("\nNSFW 전체 목록 조회 중...")
            nsfw_items = await client.fetch_all_list(
                nsfw=True,
                on_progress=lambda p, n: print(f"  페이지 {p}, 총 {n}개"),
            )

            if self._shutdown_requested:
                return []

            # 중복 제거 (SFW 우선)
            all_items = {}
            for item in nsfw_items:
                all_items[item["id"]] = {"item": item, "nsfw": True, "type": "normal"}
            for item in sfw_items:
                all_items[item["id"]] = {"item": item, "nsfw": False, "type": "normal"}

            print(f"\n전체 캐릭터: {len(all_items)}개")

            # 변경 감지: 새 캐릭터 또는 date가 변경된 캐릭터
            changed_uuids = []
            new_count = 0
            updated_count = 0

            for uuid, item_data in all_items.items():
                item = item_data["item"]
                new_date = item.get("date", 0)

                if uuid not in existing_dates:
                    changed_uuids.append(uuid)
                    new_count += 1
                elif new_date != existing_dates[uuid]:
                    changed_uuids.append(uuid)
                    updated_count += 1

            print(f"변경 감지: 신규 {new_count}개, 수정 {updated_count}개")

            # 타입 조회 (변경된 것만)
            success_count = 0
            fail_count = 0
            updated_chars = []

            if changed_uuids:
                changed_items = {uuid: all_items[uuid] for uuid in changed_uuids}
                types = await self._fetch_types_batch(client, changed_items)
                for uuid, char_type in types.items():
                    if uuid in changed_items:
                        changed_items[uuid]["type"] = char_type

                if self._shutdown_requested:
                    return []

                # 상세 정보 수집
                print(f"\n상세 정보 수집 중... ({len(changed_uuids)}개)")

                for i, uuid in enumerate(changed_uuids, 1):
                    if self._shutdown_requested:
                        break

                    item_data = changed_items[uuid]
                    result = await self._fetch_single(client, uuid, item_data)

                    if result is None:
                        continue

                    name = result.list_item.get("name", "Unknown")

                    if result.detail_data:
                        success_count += 1
                        status = f"OK ({result.source})"
                    else:
                        fail_count += 1
                        status = "FAIL (list_only)"

                    print(f"[{i}/{len(changed_uuids)}] {name[:35]:<35} {status}")

                    # 캐릭터 데이터 생성
                    character = ScrapedCharacter(
                        uuid=result.uuid,
                        nsfw=result.nsfw,
                        list_data=CharacterListItem(**result.list_item),
                        detail_data=CharacterDetail(**result.detail_data) if result.detail_data else None,
                        detail_source=DetailSource(result.source),
                        scraped_at=int(time.time()),
                    )
                    updated_chars.append(character.model_dump())

        if self._shutdown_requested:
            return []

        # characters.jsonl 업데이트
        print("\ncharacters.jsonl 업데이트 중...")
        updated_uuids = {char["uuid"] for char in updated_chars}

        # 모든 캐릭터의 list_data 업데이트 (download 등 메타데이터 반영)
        final_chars = []
        metadata_updated = 0

        for uuid, char in existing_chars.items():
            if uuid in updated_uuids:
                # 상세 정보가 재수집된 캐릭터는 건너뜀 (나중에 추가)
                continue
            elif uuid in all_items:
                # list_data만 업데이트 (download 등 메타데이터)
                new_list_data = all_items[uuid]["item"]
                char["list_data"] = new_list_data
                char["nsfw"] = all_items[uuid]["nsfw"]
                metadata_updated += 1
            final_chars.append(char)

        # 새/변경된 캐릭터 추가
        final_chars.extend(updated_chars)

        # 파일 저장
        save_jsonl(final_chars, self.characters_path)
        print(f"  저장 완료: {len(final_chars)}개")
        print(f"  메타데이터 업데이트: {metadata_updated}개")

        print("\n" + "=" * 60)
        print("전체 업데이트 완료!" if not self._shutdown_requested else "전체 업데이트 중단됨")
        print(f"  신규: {new_count}개")
        print(f"  내용 수정: {updated_count}개")
        print(f"  메타데이터 업데이트: {metadata_updated}개")
        print(f"  성공: {success_count}개")
        print(f"  실패: {fail_count}개")

        return changed_uuids
