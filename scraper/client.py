import aiohttp
import asyncio
from urllib.parse import quote
from typing import Optional, Callable, Any
import zipfile
import io
import json
import random


class RateLimitError(Exception):
    """Rate limit 발생"""

    def __init__(self, retry_after: float = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit, retry after {retry_after}s")


class RisuRealmClient:
    PROXY_BASE = "https://sv.risuai.xyz/realm/"
    DOWNLOAD_BASE = "https://realm.risuai.net/api/v1/download"
    CHARACTER_BASE = "https://realm.risuai.net/character"

    def __init__(
        self,
        delay: float = 0.1,
        max_concurrent: int = 10,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.delay = delay
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()

    def _build_list_url(self, page: int, nsfw: bool, sort: str = "downloads") -> str:
        """프록시 API URL 생성"""
        query = f"search== __shared&&page=={page}&&nsfw=={str(nsfw).lower()}&&sort=={sort}&&web==web"
        return self.PROXY_BASE + quote(query, safe="")

    async def _request_with_retry(
        self,
        url: str,
        response_type: str = "json",
    ) -> Optional[Any]:
        """재시도 로직이 포함된 요청 (semaphore 없음)"""
        for attempt in range(self.max_retries):
            try:
                if self._session is None:
                    raise RuntimeError("Session not initialized. Use async with.")
                async with self._session.get(url) as resp:
                    if resp.status == 429:
                        retry_after = float(resp.headers.get("Retry-After", 60))
                        wait_time = retry_after + random.uniform(1, 5)
                        print(f"\n⚠️  Rate limit! {wait_time:.1f}초 대기 중...")
                        await asyncio.sleep(wait_time)
                        continue

                    if resp.status >= 500:
                        wait_time = (2**attempt) + random.uniform(0, 1)
                        await asyncio.sleep(wait_time)
                        continue

                    if resp.status == 200:
                        if response_type == "json":
                            return await resp.json()
                        else:
                            return await resp.read()

                    # 404 등 - 즉시 None 반환 (재시도 안함)
                    return None

            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    await asyncio.sleep(wait_time)

            except aiohttp.ClientError:
                if attempt < self.max_retries - 1:
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    await asyncio.sleep(wait_time)

        return None

    async def fetch_list_page(self, page: int, nsfw: bool, sort: str = "downloads") -> list[dict]:
        """목록 페이지 조회"""
        async with self.semaphore:
            url = self._build_list_url(page, nsfw, sort)
            result = await self._request_with_retry(url, "json")
            await asyncio.sleep(self.delay)
            if not result:
                return []
            # API가 {"cards": [...]} 또는 [...] 형태로 반환
            if isinstance(result, dict) and "cards" in result:
                return result["cards"]
            return result if isinstance(result, list) else []

    async def fetch_all_list(
        self,
        nsfw: bool,
        on_progress: Optional[Callable[[int, int], None]] = None,
        page_workers: int = 5,
    ) -> list[dict]:
        """전체 목록 조회 (병렬 페이지 요청)"""
        all_items = []
        page = 0
        empty_streak = 0
        max_empty_streak = 3

        while empty_streak < max_empty_streak:
            # 여러 페이지 동시 요청
            pages_to_fetch = list(range(page, page + page_workers))
            tasks = [self.fetch_list_page(p, nsfw) for p in pages_to_fetch]
            results = await asyncio.gather(*tasks)

            batch_empty = 0
            for p, items in zip(pages_to_fetch, results):
                if items:
                    all_items.extend(items)
                    empty_streak = 0
                else:
                    batch_empty += 1

            # 모든 페이지가 비어있으면 종료
            if batch_empty == len(pages_to_fetch):
                empty_streak += batch_empty
            else:
                empty_streak = 0

            if on_progress:
                on_progress(page + page_workers - 1, len(all_items))

            page += page_workers

        return all_items

    async def fetch_latest_until_known(
        self,
        nsfw: bool,
        known_uuids: set[str],
        max_pages: int = 50,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> list[dict]:
        """최신순으로 조회하다가 이미 알려진 UUID를 만나면 중단"""
        new_items = []
        page = 0

        while page < max_pages:
            items = await self.fetch_list_page(page, nsfw, sort="")

            if not items:
                break

            found_known = False
            for item in items:
                if item["id"] in known_uuids:
                    found_known = True
                    break
                new_items.append(item)

            if on_progress:
                on_progress(page, len(new_items))

            if found_known:
                break

            page += 1

        return new_items

    async def fetch_character_type(self, uuid: str) -> str:
        """캐릭터 페이지에서 타입 조회 (normal/charx)"""
        url = f"{self.CHARACTER_BASE}/{uuid}/__data.json"
        try:
            data = await self._request_with_retry(url, "json")
            if not data:
                return "normal"

            # __data.json 파싱: nodes[1].data 배열에서 type 찾기
            nodes = data.get("nodes", [])
            if len(nodes) >= 2 and nodes[1]:
                node_data = nodes[1].get("data", [])
                # type은 보통 마지막에서 두 번째 요소
                for item in reversed(node_data):
                    if item in ("normal", "charx"):
                        return item
        except Exception:
            pass
        return "normal"

    async def _fetch_charx_v3(self, uuid: str) -> Optional[dict]:
        """charx-v3 포맷 조회 (내부용, semaphore 없음)"""
        url = f"{self.DOWNLOAD_BASE}/charx-v3/{uuid}"
        try:
            data = await self._request_with_retry(url, "bytes")
            if not data:
                return None
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                if "card.json" in zf.namelist():
                    return json.loads(zf.read("card.json"))
        except Exception:
            pass
        return None

    async def _fetch_json_v3(self, uuid: str) -> Optional[dict]:
        """json-v3 포맷 조회 (내부용, semaphore 없음)"""
        url = f"{self.DOWNLOAD_BASE}/json-v3/{uuid}"
        return await self._request_with_retry(url, "json")

    async def _fetch_json_v2(self, uuid: str) -> Optional[dict]:
        """json-v2 포맷 조회 (내부용, semaphore 없음)"""
        url = f"{self.DOWNLOAD_BASE}/json-v2/{uuid}"
        return await self._request_with_retry(url, "json")

    async def fetch_detail(
        self,
        uuid: str,
        char_type: str = "normal",
    ) -> tuple[Optional[dict], str]:
        """캐릭터 타입에 따라 상세 정보 조회"""
        async with self.semaphore:
            if char_type == "charx":
                # CharX 타입: charx-v3만 시도
                data = await self._fetch_charx_v3(uuid)
                if data:
                    await asyncio.sleep(self.delay)
                    return data, "charx-v3"
            else:
                # Normal 타입: json-v3 → json-v2
                data = await self._fetch_json_v3(uuid)
                if data:
                    await asyncio.sleep(self.delay)
                    return data, "json-v3"

                data = await self._fetch_json_v2(uuid)
                if data:
                    await asyncio.sleep(self.delay)
                    return data, "json-v2"

            await asyncio.sleep(self.delay)
            return None, "list_only"
